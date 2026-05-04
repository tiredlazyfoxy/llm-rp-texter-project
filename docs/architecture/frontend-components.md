# Frontend — Components

How components are shaped, when to split them, and where event handlers and orchestration live.

## Pure props, no React context

Stores and slices flow down the tree as **explicit props**. React Context is **not used** for state, dependency injection, or anything else that is otherwise expressible as a prop.

```tsx
// Page passes its state down
<WorldEditor state={state} />
<WorldList state={state} onSelect={(id) => navigate(`/worlds/${id}`)} />

// Subcomponents take a slice
const NpcSection = observer(({ npcs, onAdd }: NpcSectionProps) => { /* ... */ });
```

Reasons:

- Explicit dependencies. You can read a component file top-to-bottom and know what it needs.
- No "where does this come from?" archaeology.
- Trivially testable — pass mock state.
- Refactoring is grep-driven: rename a prop, see every call site.

The cost — some prop-drilling — is real but small in this app. Pages are not deep, and the tree shape is the most honest representation of dependencies. **If a future need is real**, React Context will be added as a documented amendment, not assumed today.

## Observer everywhere

Repeating from `frontend-state.md` because it is non-negotiable: **every component is wrapped in `observer`.** No exceptions, no leaf-only carve-outs, no "container only" rule.

```tsx
import { observer } from 'mobx-react-lite';

export const WorldRow = observer(({ world }: WorldRowProps) => {
  return <tr><td>{world.name}</td></tr>;
});
```

A missing `observer` produces silent staleness rather than a loud error, so it must be enforced at code review.

## Generic vs page-aware components

Two clearly distinct kinds of components, kept in separate folders:

### Generic components — `components/common/`

- `Button`, `Modal`, `Input`, `Select`, `Spinner`, `ErrorBanner`, `Tabs`.
- **Take primitives + callbacks only.** No domain types, no MobX state, no awareness of `World` / `NPC` / `ChatMessage`.
- Reusable across User SPA and Admin SPA.
- Still wrapped in `observer` (in case a parent passes an observable through a callback or prop).

```tsx
interface InputProps {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  error?: string;
}
export const Input = observer((props: InputProps) => { /* ... */ });
```

### Page-aware components — `components/<domain>/`

- `WorldRow`, `WorldEditForm`, `WorldList`, `NpcSection`, `ChatMessageBubble`.
- **Take state slices** — usually a slice of page state, sometimes a domain object plus callbacks.
- Live under a domain folder (`components/worlds/`, `components/chats/`).
- Composable inside their own page; not designed for re-use across unrelated domains.

```tsx
interface WorldEditFormProps {
  state: WorldPageState;
}
export const WorldEditForm = observer(({ state }: WorldEditFormProps) => {
  return <form>{/* reads state.draft, mutates state.draft.* directly */}</form>;
});
```

The split is enforced by folder. If a generic component needs to know what a `World` is, it's not generic — move it.

## Event handlers and orchestration live inside the component

This is one of the more counter-intuitive rules: **page-specific orchestration and event handlers are inner functions inside the component**, closing over `state` and props. They are **not** extracted to top-level `function handleSave(state, ...)` "to keep the component small."

```tsx
export const WorldEditForm = observer(({ state }: WorldEditFormProps) => {
  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!state.canSubmit) return;
    const controller = new AbortController();
    await saveWorld(state, controller.signal);
  };

  const onCancel = () => {
    runInAction(() => {
      state.draft = cloneWorld(state.world!);
      state.serverErrors = {};
    });
  };

  return (
    <form onSubmit={onSubmit}>
      {/* ... */}
      <Button onClick={onCancel}>Cancel</Button>
      <Button type="submit" disabled={!state.canSubmit}>Save</Button>
    </form>
  );
});
```

Reasons:

- Inner closures capture `state` and props naturally — no need to thread arguments through.
- They are not reusable, so giving them a top-level home pollutes the module surface.
- Reading the JSX and the handler that wires it sits in one place — top-down.
- We aren't worried about "stable callback references" because of `observer`. (See `frontend-state.md` on `useCallback`.)

**External top-level functions are reserved for genuinely reusable code:**

- API calls (`api/worlds.ts`).
- Effectful state operations (`loadWorld`, `saveWorld`, `deleteWorld` in `worldPageState.ts`).
- Pure helpers and validators (`validateWorldName`, `formatTurn`).
- Generic components.

If the inner handler is doing more than wiring, the right move is usually to call an existing external function (e.g., `saveWorld(state, signal)`), not to extract the handler.

## Splitting growing components

A component that is getting large is **not** refactored by extracting top-level handler functions. It is refactored by **splitting into smaller observer subcomponents**.

```tsx
// Page-level — small, orchestrates
export const WorldPage = observer(({ id }: { id: string }) => {
  const [state] = useState(() => new WorldPageState(id, /* ... */));
  useEffect(/* ... */, []);

  return (
    <PageLayout>
      <WorldHeader state={state} />
      <WorldEditForm state={state} />
      <NpcSection state={state} />
      <LoreSection state={state} />
    </PageLayout>
  );
});

// Subcomponents — each owns its slice of JSX and its own inner handlers
export const NpcSection = observer(({ state }: { state: WorldPageState }) => {
  const onAdd = () => runInAction(() => { state.draft.npcs.push(emptyNpc()); });
  const onRemove = (i: number) => runInAction(() => { state.draft.npcs.splice(i, 1); });

  return (/* JSX reading state.draft.npcs */);
});
```

Each subcomponent:

- Is wrapped in `observer`.
- Receives the state (or a sub-slice) as a prop.
- Owns its own inner event handlers.
- Renders its own slice of JSX.

State **stays in the page** — the subcomponent does not own its own page-scoped state. (Genuinely component-local UI state, e.g., a popover open flag, is the only exception, and it's rare.)

## Reusable stateful UI components (no custom hooks)

When a piece of UI behavior is reusable and stateful — a translate-with-revert input, an autocomplete dropdown, a controllable preview pane — it is **a wrapper component owning a `<Component>State` class instance**, not a custom hook.

```tsx
// components/common/llmInputState.ts
export class LlmInputState {
  value = '';
  isTranslating = false;
  canRevert = false;
  translateError: string | null = null;
  // ... internal buffers ...
  constructor() { makeAutoObservable(this); }
}

// External effectful functions in the same file:
export function startTranslate(state: LlmInputState, fn: TranslateFn): void { /* ... */ }
export function revertTranslate(state: LlmInputState): void { /* ... */ }

// components/common/LlmInputBar.tsx
export const LlmInputBar = observer(({ state, translateFn, busy, onSend, onStop, before, extras }: Props) => {
  // textarea + translate + revert + send/stop, reading state.* and props
});

// Caller (page or another component):
const [inputState] = useState(() => new LlmInputState());
const onSend = () => sendMessage(inputState.value);
return <LlmInputBar state={inputState} translateFn={translateChat} busy={chatBusy} onSend={onSend} onStop={stop} />;
```

Key shape rules:

- **Caller owns the state instance** via `useState(() => new XState())` — same memoization primitive as page state.
- **State-class methods are not API-effectful.** API/streaming work goes in external `(state, ...args)` functions in the same file.
- **Slot props** (`before`, `extras`) handle page-specific variation cleanly. Don't add a flag prop for every minor visual tweak — slots compose.
- **`busy` from outside the component** decouples external concerns (chat is streaming) from the component's internal state (translation in flight). Both can disable the input independently.
- **No React Context** — state is passed as a prop. The component reads `state.value`, mutates `state.value` from `onChange`, and the caller reads `state.value` in its own handlers.

This replaces every custom hook in the codebase. A `useTranslation` returning `{ isTranslating, handleTranslate, ... }` is the same data with worse ergonomics — you can't inspect it, can't pass it down, can't test it without a renderer.

**Imperative API escape valve.** When a wrapper component must expose a small named imperative API to its parent (e.g. `PlaceholderTextarea` → `insertAtCursor`), prefer a typed `controllerRef?: RefObject<XController | null>` published via mount/unmount `useEffect` over re-exposing internal DOM refs. Two- or three-method ceiling — anything wider is a sign the behavior should be lifted into observable state instead.

**Disabled-state composition.** `LlmInputBar` derives the textarea-disabled state as `disabled || busy || isTranslating` — the textarea is greyed out in any of those conditions; callers don't get to enable it while sending is busy. If a future caller needs split control (textarea enabled while send is disabled, or vice versa), introduce separate `inputDisabled` / `sendDisabled` props rather than working around the combined check.

## Cross-SPA shared modals — `useState` exception

A tiny single-screen modal with no reactive interaction outside its own form (today: `ChangePasswordModal`, `TranslationSettingsModal` under `frontend/src/components/`) may stay on plain `useState` form fields and skip the `Draft` + `observer` pattern. The bar is: one screen, no shared state with the page, no cross-form validation. Migration trigger: if either grows new fields, cross-form validation, or shared state with the page, lift it to a draft class per `frontend-forms.md`.

## Slice props vs whole-state props

Two patterns, both fine:

```tsx
// Whole state — convenient, common for tightly-coupled subcomponents
<NpcSection state={state} />

// Sliced — appropriate when the subcomponent only needs a narrow shape
<NpcList npcs={state.draft.npcs} onRemove={(i) => /* ... */} />
```

Prefer whole-state when the subcomponent reads many fields and lives in the same page; prefer slicing when the subcomponent is more generic or you want to make its dependencies explicit.

A sliced subcomponent is a step toward making it page-aware-but-not-page-coupled. If you find yourself slicing aggressively to push a component toward `components/common/`, that's fine — but rename and move the file when it gets there.

## Composition rules

- **Subcomponents may render other subcomponents**, all wrapped in `observer`.
- **Subcomponents do not own loading.** Loading happens at the page; subcomponents read status flags off page state and render accordingly:

  ```tsx
  if (state.npcsStatus === 'loading') return <Spinner />;
  if (state.npcsStatus === 'error') return <ErrorBanner message={state.npcsError} />;
  // render
  ```
- **Subcomponents do not navigate.** Navigation is a page-level concern. If a subcomponent needs to navigate, accept an `onNavigate` callback and let the page do it.

## Anti-patterns

- A component that is **not** wrapped in `observer`. Wrap it.
- Top-level `function handleClick(state, e) { ... }` extracted from a component "for size." Inline it; if the component is too big, split into subcomponents instead.
- React Context for state. Pass props.
- A subcomponent fetching its own data via `useEffect`. Move the fetch to the page.
- A "container component" / "presentational component" split as a rule. Components are just observers; orchestration sits at the page.
- `useCallback` wrapping inner handlers. Delete it.
- A custom `useX` hook that owns reactive state and returns handlers. Convert to a wrapper component owning a `<Component>State` class.
