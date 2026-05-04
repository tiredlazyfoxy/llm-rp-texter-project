import { createRef, type RefObject } from "react";
import { makeAutoObservable } from "mobx";
import type { PlaceholderInfo } from "../../../types/pipeline";

export interface AutocompletePosition {
  top: number;
  left: number;
}

/**
 * Internal state for `PlaceholderTextarea`. One instance per component
 * mount, created via `useState(() => new PlaceholderAutocompleteState())`.
 */
export class PlaceholderAutocompleteState {
  visible = false;
  suggestions: PlaceholderInfo[] = [];
  selectedIndex = 0;
  position: AutocompletePosition = { top: 0, left: 0 };

  // Stable ref bound to the underlying <textarea>.
  readonly textareaRef: RefObject<HTMLTextAreaElement | null> = createRef<HTMLTextAreaElement | null>();

  constructor() {
    makeAutoObservable(this, { textareaRef: false });
  }
}

/**
 * Get the pixel coordinates of the caret inside a textarea using a
 * mirror div. Returns coordinates relative to the viewport (for
 * `position: fixed`).
 */
function getCaretPixelPosition(
  ta: HTMLTextAreaElement,
  caretPos: number,
): { top: number; left: number } {
  const mirror = document.createElement("div");
  const style = getComputedStyle(ta);

  for (const prop of [
    "fontFamily", "fontSize", "fontWeight", "fontStyle", "letterSpacing",
    "textTransform", "wordSpacing", "lineHeight", "paddingTop", "paddingLeft",
    "paddingRight", "paddingBottom", "borderTopWidth", "borderLeftWidth",
    "borderRightWidth", "borderBottomWidth", "boxSizing", "whiteSpace",
    "wordWrap", "overflowWrap", "tabSize", "textIndent",
  ] as const) {
    mirror.style[prop] = style[prop];
  }

  mirror.style.position = "absolute";
  mirror.style.top = "-9999px";
  mirror.style.left = "-9999px";
  mirror.style.visibility = "hidden";
  mirror.style.overflow = "hidden";
  mirror.style.width = `${ta.clientWidth}px`;

  const textBefore = ta.value.substring(0, caretPos);
  const textNode = document.createTextNode(textBefore);
  mirror.appendChild(textNode);

  const marker = document.createElement("span");
  marker.textContent = "|";
  mirror.appendChild(marker);

  document.body.appendChild(mirror);

  const markerRect = marker.getBoundingClientRect();
  const taRect = ta.getBoundingClientRect();

  const top = taRect.top + (markerRect.top - mirror.getBoundingClientRect().top) - ta.scrollTop;
  const left = taRect.left + (markerRect.left - mirror.getBoundingClientRect().left) - ta.scrollLeft;

  document.body.removeChild(mirror);

  return { top, left };
}

/** Find the partial placeholder text after the last unclosed `{`. */
function getPartial(text: string, cursorPos: number): string | null {
  const before = text.substring(0, cursorPos);
  const lastOpen = before.lastIndexOf("{");
  if (lastOpen === -1) return null;
  const afterBrace = before.substring(lastOpen + 1);
  if (afterBrace.includes("}")) return null;
  if (!/^[A-Z_]*$/.test(afterBrace)) return null;
  return afterBrace;
}

/** Dismiss the dropdown without selecting. */
export function dismiss(state: PlaceholderAutocompleteState): void {
  state.visible = false;
  state.suggestions = [];
  state.selectedIndex = 0;
}

/**
 * Update suggestions/visibility/position based on the textarea caret
 * position and detected `{PARTIAL` token.
 */
export function onTextChange(
  state: PlaceholderAutocompleteState,
  placeholders: PlaceholderInfo[],
  value: string,
  ta: HTMLTextAreaElement,
): void {
  const cursorPos = ta.selectionStart;
  const partial = getPartial(value, cursorPos);
  if (partial === null) {
    dismiss(state);
    return;
  }

  const upper = partial.toUpperCase();
  const filtered = placeholders.filter((p) => p.name.startsWith(upper));
  state.suggestions = filtered;
  state.selectedIndex = 0;
  if (filtered.length > 0) {
    const lineHeight = parseFloat(getComputedStyle(ta).lineHeight) || 20;
    const coords = getCaretPixelPosition(ta, cursorPos);
    state.position = { top: coords.top + lineHeight, left: coords.left };
    state.visible = true;
  } else {
    state.visible = false;
  }
}

/**
 * Replace the partial `{PARTIAL` with the full `{NAME}` and dismiss.
 * Cursor position is preserved via `requestAnimationFrame`.
 */
export function applySelection(
  state: PlaceholderAutocompleteState,
  index: number,
  value: string,
  setValue: (v: string) => void,
): void {
  const ta = state.textareaRef.current;
  if (!ta || index < 0 || index >= state.suggestions.length) return;

  const name = state.suggestions[index].name;
  const cursorPos = ta.selectionStart;
  const before = value.substring(0, cursorPos);
  const lastOpen = before.lastIndexOf("{");
  if (lastOpen === -1) return;

  const replacement = `{${name}}`;
  const newValue = value.substring(0, lastOpen) + replacement + value.substring(cursorPos);
  setValue(newValue);

  const newCursorPos = lastOpen + replacement.length;
  requestAnimationFrame(() => {
    ta.selectionStart = ta.selectionEnd = newCursorPos;
    ta.focus();
  });

  dismiss(state);
}

/** Arrow up/down navigate, Enter/Tab apply, Escape dismiss. */
export function handleKeyDown(
  state: PlaceholderAutocompleteState,
  event: React.KeyboardEvent<HTMLTextAreaElement>,
  value: string,
  setValue: (v: string) => void,
): void {
  if (!state.visible) return;

  if (event.key === "ArrowDown") {
    event.preventDefault();
    state.selectedIndex = (state.selectedIndex + 1) % state.suggestions.length;
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    state.selectedIndex =
      (state.selectedIndex - 1 + state.suggestions.length) % state.suggestions.length;
  } else if (event.key === "Enter" || event.key === "Tab") {
    if (state.suggestions.length > 0) {
      event.preventDefault();
      applySelection(state, state.selectedIndex, value, setValue);
    }
  } else if (event.key === "Escape") {
    event.preventDefault();
    dismiss(state);
  }
}
