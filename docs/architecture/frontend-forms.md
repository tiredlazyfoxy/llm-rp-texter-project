# Frontend — Forms

Form drafts, validation as computed derivations, dirty/valid/canSubmit, server vs client errors, and the submit flow.

## Where the draft lives

| Form kind | Draft location |
|-----------|---------------|
| Page-level form (page editor, large forms) | **Page state** — observable fields on `<Page>State` |
| Modal dialog form (create-X, quick edits) | **Component-local state** — small class held via `useState(() => ...)` |

Reasons:

- Page-level forms often need to share state with other parts of the page (preview, validation badges in headers). Putting the draft on page state is the path of least resistance.
- Modal drafts are short-lived and self-contained. Component-local state is enough; lifting them to page state pollutes the page surface for no benefit.

## Draft shape

For a page-level form, the draft is a separate observable field on page state, distinct from the loaded server-side data:

```ts
export class WorldPageState {
  world: World | null = null;             // server snapshot
  worldStatus: AsyncStatus = 'idle';
  worldError: string | null = null;

  draft: WorldDraft = emptyDraft();       // editable copy
  serverErrors: Partial<DraftErrors> = {};

  constructor(public id: string) { makeAutoObservable(this); }

  /* computed validation — see below */
}
```

The draft is initialized from the loaded `world` after the load completes (in the load function, via `runInAction`). On reset / cancel, the draft is replaced with a fresh clone of `world`.

Keeping the server snapshot and the draft separate is what makes `isDirty` cheap and reliable.

## Validation as computed derivations

Validation is **`get` computed derivations on state** — pure functions of observable fields. No `validate()` method, no separate validation pass run at submit time.

```ts
get errors(): DraftErrors {
  const e: DraftErrors = {};
  if (!this.draft.name.trim()) e.name = 'Name is required';
  if (this.draft.name.length > 100) e.name = 'Name too long';
  if (!this.draft.description.trim()) e.description = 'Description is required';
  // merge server-side field errors
  return { ...e, ...this.serverErrors };
}

get isValid(): boolean {
  return Object.keys(this.errors).length === 0;
}

get isDirty(): boolean {
  return !shallowEqual(this.draft, this.world);
}

get canSubmit(): boolean {
  return this.isValid && this.isDirty && this.saveStatus !== 'loading';
}
```

Components read these directly:

```tsx
<Input
  value={state.draft.name}
  onChange={(v) => { state.draft.name = v; }}
  error={state.errors.name}
/>
<Button disabled={!state.canSubmit} onClick={onSubmit}>Save</Button>
```

Because they are MobX computeds, they update precisely when their inputs change — no manual triggers, no dependency arrays.

## Reusable validators

Pure validator functions (used by `get errors`) live as **top-level functions**, colocated with the state file or in a `validators` section if they are shared:

```ts
// in worldPageState.ts (or a colocated validators.ts)
export function validateWorldName(name: string): string | null {
  if (!name.trim()) return 'Name is required';
  if (name.length > 100) return 'Name too long';
  return null;
}

// then in the computed
get errors(): DraftErrors {
  const e: DraftErrors = {};
  const nameErr = validateWorldName(this.draft.name);
  if (nameErr) e.name = nameErr;
  // ...
  return { ...e, ...this.serverErrors };
}
```

Validators are pure — input → string-or-null. They never read state, they never call APIs, they never have side effects.

## Server-side errors merge in

Server-side field validation errors are stored in a separate observable field on state, **distinct from client-derived errors**:

```ts
serverErrors: Partial<DraftErrors> = {};
```

The `errors` computed unions both:

```ts
get errors(): DraftErrors {
  const clientErrors = computeClientErrors(this.draft);
  return { ...clientErrors, ...this.serverErrors };
}
```

This separation matters:

- **Client errors update reactively** as the user types.
- **Server errors persist until the user changes the relevant field**, at which point the submit handler clears the corresponding `serverErrors[field]` (or clears the whole object on next submit).

Pattern for clearing server errors on edit:

```tsx
<Input
  value={state.draft.name}
  onChange={(v) => {
    state.draft.name = v;
    if (state.serverErrors.name) {
      runInAction(() => { delete state.serverErrors.name; });
    }
  }}
  error={state.errors.name}
/>
```

## Submit flow

The submit handler is **an inner closure on the form component**. It guards on `canSubmit` and calls the external save function:

```tsx
export const WorldEditForm = observer(({ state }: { state: WorldPageState }) => {
  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!state.canSubmit) return;
    const controller = new AbortController();
    await saveWorld(state, controller.signal);
  };

  return <form onSubmit={onSubmit}>{/* ... */}</form>;
});
```

The external `saveWorld` function:

1. Sets `state.saveStatus = 'loading'`.
2. Calls `worldsApi.update(state.id, state.draft, signal)`.
3. On success: updates `state.world`, resets the draft from `state.world`, clears `serverErrors`, sets `saveStatus = 'ready'`.
4. On 422 (server validation): merges the response into `state.serverErrors`, sets `saveStatus = 'ready'`.
5. On other error: sets `saveStatus = 'error'`, sets `state.saveError`.

```ts
// in worldPageState.ts
export async function saveWorld(state: WorldPageState, signal: AbortSignal): Promise<void> {
  state.saveStatus = 'loading';
  state.saveError = null;
  try {
    const updated = await worldsApi.update(state.id, toUpdateRequest(state.draft), signal);
    runInAction(() => {
      state.world = updated;
      state.draft = cloneFromWorld(updated);
      state.serverErrors = {};
      state.saveStatus = 'ready';
    });
  } catch (err) {
    if (signal.aborted) return;
    if (err instanceof ApiError && err.status === 422 && err.details) {
      runInAction(() => {
        state.serverErrors = mapServerErrors(err.details);
        state.saveStatus = 'ready';
      });
    } else {
      runInAction(() => {
        state.saveStatus = 'error';
        state.saveError = String(err);
      });
    }
  }
}
```

Note: `saveStatus` is its own async-trio member — distinct from the load trio (`worldStatus`). A page can have several trios at once.

## Cancel / reset

Cancel discards the draft and any server errors:

```tsx
const onCancel = () => {
  runInAction(() => {
    state.draft = cloneFromWorld(state.world!);
    state.serverErrors = {};
  });
};
```

After a successful save, the same operation runs as part of the save flow (re-cloning from the freshly returned `state.world`). This keeps `isDirty` honest after save.

## Large forms — per-section computed derivations

For large pages with multiple form sections (e.g., a world editor with general info, NPCs, lore, rules), validation can be split into **per-section computeds**, all on page state:

```ts
get generalSectionErrors(): GeneralErrors { /* ... */ }
get npcSectionErrors(): NpcErrors[] { /* per-NPC errors */ }
get loreSectionErrors(): LoreErrors[] { /* ... */ }

get isGeneralValid(): boolean { return isEmpty(this.generalSectionErrors); }
get isNpcsValid(): boolean { return this.npcSectionErrors.every(isEmpty); }
get isLoreValid(): boolean { return this.loreSectionErrors.every(isEmpty); }

get isFullyValid(): boolean {
  return this.isGeneralValid && this.isNpcsValid && this.isLoreValid;
}

get canSubmit(): boolean {
  return this.isFullyValid && this.isDirty && this.saveStatus !== 'loading';
}
```

Sub-components read their slice (`state.npcSectionErrors`); the page header reads the aggregate (`state.isFullyValid`) to enable/disable the global save button.

This keeps the validation logic colocated with state and free of duplication. Each section is just a different aggregation of the same observable draft.

## Modal-form drafts (component-local)

For small modal forms (create-X dialogs), the draft can live in component-local state to keep page state clean:

```tsx
class CreateWorldDraft {
  name = '';
  description = '';
  serverErrors: Partial<{ name: string; description: string }> = {};

  constructor() { makeAutoObservable(this); }

  get errors() { /* ... */ }
  get isValid() { return Object.keys(this.errors).length === 0; }
}

export const CreateWorldModal = observer(({ onClose, onCreated }: Props) => {
  const [draft] = useState(() => new CreateWorldDraft());

  const onSubmit = async () => {
    if (!draft.isValid) return;
    const controller = new AbortController();
    try {
      const w = await worldsApi.create({ name: draft.name, description: draft.description }, controller.signal);
      onCreated(w);
      onClose();
    } catch (err) { /* set draft.serverErrors or show toast */ }
  };

  return <Modal>{/* ... */}</Modal>;
});
```

The modal is the one place where component-local class state is normal. The page that opens it doesn't carry the draft.

After the modal saves, the standard pattern is: navigate to the new resource (which remounts that page and refetches), or close and let the parent list refetch on its next load. **No upward callback chain** to "refresh the parent list" — that's the cross-page rule from `frontend-pages.md`.

When the draft class has only one consumer, declare it in the same file as the modal (the `WorldEditPage` `StatDraft`/`RuleDraft` precedent) — sibling `*Draft.ts` files only when the draft is shared across multiple consumers.

Documented exceptions to the draft+observer pattern (cross-SPA shared modals on plain `useState`): see `frontend-components.md` § "Cross-SPA shared modals".

## Anti-patterns

- A `validate()` method on state. Use `get errors`.
- Calling `validate()` at submit time. The computed is always current.
- Mixing client and server errors into one observable field. Keep them separate, union in the computed.
- A draft that mutates `state.world` directly (no separate draft). You lose `isDirty` and reset becomes ugly.
- A submit handler that does its own try/catch and updates state directly. Use the external `saveX(state, signal)` function pattern.
- `useEffect` watching the draft to validate. Computeds replace this entirely.
