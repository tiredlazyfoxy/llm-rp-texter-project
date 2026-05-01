import { useCallback, useState } from "react";
import type { PlaceholderInfo } from "../../types/pipeline";

export interface AutocompletePosition {
  top: number;
  left: number;
}

export interface PlaceholderAutocomplete {
  /** Whether the suggestion dropdown is visible. */
  visible: boolean;
  /** Filtered placeholder suggestions. */
  suggestions: PlaceholderInfo[];
  /** Currently highlighted index. */
  selectedIndex: number;
  /** Fixed position for the dropdown (viewport coordinates). */
  position: AutocompletePosition;
  /** Attach to textarea onKeyDown. */
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  /** Call from textarea onChange with the new value + textarea element. */
  onTextChange: (value: string, ta: HTMLTextAreaElement) => void;
  /** Select a suggestion by index (e.g. on click). */
  onSelect: (index: number) => void;
  /** Dismiss without selecting. */
  dismiss: () => void;
}

/**
 * Get the pixel coordinates of the caret inside a textarea using a mirror div.
 * Returns coordinates relative to the viewport (for `position: fixed`).
 */
function getCaretPixelPosition(ta: HTMLTextAreaElement, caretPos: number): { top: number; left: number } {
  const mirror = document.createElement("div");
  const style = getComputedStyle(ta);

  // Copy all relevant styles to the mirror
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

  // Text before caret
  const textBefore = ta.value.substring(0, caretPos);
  const textNode = document.createTextNode(textBefore);
  mirror.appendChild(textNode);

  // Marker span at caret position
  const marker = document.createElement("span");
  marker.textContent = "|";
  mirror.appendChild(marker);

  document.body.appendChild(mirror);

  const markerRect = marker.getBoundingClientRect();
  const taRect = ta.getBoundingClientRect();

  // Calculate position relative to viewport, accounting for scroll
  const top = taRect.top + (markerRect.top - mirror.getBoundingClientRect().top) - ta.scrollTop;
  const left = taRect.left + (markerRect.left - mirror.getBoundingClientRect().left) - ta.scrollLeft;

  document.body.removeChild(mirror);

  return { top, left };
}

/**
 * Hook for inline placeholder autocomplete in a textarea.
 *
 * Detects `{` character, filters placeholders as user types, and replaces
 * the partial `{PARTIAL` with `{PLACEHOLDER_NAME}` on selection.
 */
export function usePlaceholderAutocomplete(
  placeholders: PlaceholderInfo[],
  textareaRef: React.RefObject<HTMLTextAreaElement | null>,
  content: string,
  setContent: (value: string) => void,
): PlaceholderAutocomplete {
  const [visible, setVisible] = useState(false);
  const [suggestions, setSuggestions] = useState<PlaceholderInfo[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [position, setPosition] = useState<AutocompletePosition>({ top: 0, left: 0 });

  const dismiss = useCallback(() => {
    setVisible(false);
    setSuggestions([]);
    setSelectedIndex(0);
  }, []);

  /** Find the partial placeholder text after the last unclosed `{`. */
  const getPartial = useCallback((text: string, cursorPos: number): string | null => {
    const before = text.substring(0, cursorPos);
    const lastOpen = before.lastIndexOf("{");
    if (lastOpen === -1) return null;
    // If there's a closing `}` after the last `{`, no active placeholder
    const afterBrace = before.substring(lastOpen + 1);
    if (afterBrace.includes("}")) return null;
    // Only uppercase letters and underscores are valid in placeholder names
    if (!/^[A-Z_]*$/.test(afterBrace)) return null;
    return afterBrace;
  }, []);

  /** Replace the partial `{PARTIAL` with the full `{NAME}` and close. */
  const applySelection = useCallback((index: number) => {
    const ta = textareaRef.current;
    if (!ta || index < 0 || index >= suggestions.length) return;

    const name = suggestions[index].name;
    const cursorPos = ta.selectionStart;
    const before = content.substring(0, cursorPos);
    const lastOpen = before.lastIndexOf("{");
    if (lastOpen === -1) return;

    const replacement = `{${name}}`;
    const newContent = content.substring(0, lastOpen) + replacement + content.substring(cursorPos);
    setContent(newContent);

    const newCursorPos = lastOpen + replacement.length;
    requestAnimationFrame(() => {
      ta.selectionStart = ta.selectionEnd = newCursorPos;
      ta.focus();
    });

    dismiss();
  }, [content, suggestions, textareaRef, setContent, dismiss]);

  const updatePosition = useCallback((ta: HTMLTextAreaElement, cursorPos: number) => {
    const lineHeight = parseFloat(getComputedStyle(ta).lineHeight) || 20;
    const coords = getCaretPixelPosition(ta, cursorPos);
    setPosition({ top: coords.top + lineHeight, left: coords.left });
  }, []);

  const filterSuggestions = useCallback((partial: string, ta: HTMLTextAreaElement, cursorPos: number) => {
    const upper = partial.toUpperCase();
    const filtered = placeholders.filter(p => p.name.startsWith(upper));
    setSuggestions(filtered);
    setSelectedIndex(0);
    if (filtered.length > 0) {
      updatePosition(ta, cursorPos);
      setVisible(true);
    } else {
      setVisible(false);
    }
  }, [placeholders, updatePosition]);

  const onKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (!visible) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex(i => (i + 1) % suggestions.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex(i => (i - 1 + suggestions.length) % suggestions.length);
    } else if (e.key === "Enter" || e.key === "Tab") {
      if (suggestions.length > 0) {
        e.preventDefault();
        applySelection(selectedIndex);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      dismiss();
    }
  }, [visible, suggestions, selectedIndex, applySelection, dismiss]);

  const onTextChange = useCallback((value: string, ta: HTMLTextAreaElement) => {
    const cursorPos = ta.selectionStart;
    const partial = getPartial(value, cursorPos);

    if (partial !== null) {
      filterSuggestions(partial, ta, cursorPos);
    } else {
      dismiss();
    }
  }, [getPartial, filterSuggestions, dismiss]);

  const onSelect = useCallback((index: number) => {
    applySelection(index);
  }, [applySelection]);

  return { visible, suggestions, selectedIndex, position, onKeyDown, onTextChange, onSelect, dismiss };
}
