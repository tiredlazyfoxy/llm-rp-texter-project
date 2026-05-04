import { useEffect, useState, type RefObject } from "react";
import { Textarea, type TextareaProps } from "@mantine/core";
import { observer } from "mobx-react-lite";
import type { PlaceholderInfo } from "../../../types/pipeline";
import { PlaceholderSuggestions } from "./PlaceholderSuggestions";
import {
  PlaceholderAutocompleteState,
  applySelection,
  handleKeyDown,
  insertAtCursor,
  onTextChange,
} from "./placeholderAutocompleteState";

/**
 * Imperative API exposed via the optional `controllerRef` prop. Lets a
 * caller insert text at the current caret position without owning the
 * underlying DOM `<textarea>` ref.
 */
export interface PlaceholderTextareaController {
  insertAtCursor: (text: string) => void;
}

interface PlaceholderTextareaProps {
  value: string;
  onChange: (v: string) => void;
  placeholders: PlaceholderInfo[];
  textareaProps?: Omit<TextareaProps, "value" | "onChange" | "onKeyDown" | "ref">;
  /** Optional outbound controller — caller's `current` is set on mount. */
  controllerRef?: RefObject<PlaceholderTextareaController | null>;
}

export const PlaceholderTextarea = observer(function PlaceholderTextarea({
  value,
  onChange,
  placeholders,
  textareaProps,
  controllerRef,
}: PlaceholderTextareaProps) {
  const [state] = useState(() => new PlaceholderAutocompleteState());

  // Publish the controller while mounted; clear on unmount so stale refs
  // can't outlive the textarea.
  useEffect(() => {
    if (!controllerRef) return;
    controllerRef.current = {
      insertAtCursor: (text: string) => insertAtCursor(state, text, value, onChange),
    };
    return () => {
      controllerRef.current = null;
    };
    // value/onChange are read fresh on each call via the closure above,
    // but the controller object itself only needs to be re-bound when
    // the underlying state instance changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [controllerRef, state, value, onChange]);

  return (
    <>
      <Textarea
        {...textareaProps}
        ref={state.textareaRef}
        value={value}
        onChange={(e) => {
          onChange(e.currentTarget.value);
          onTextChange(state, placeholders, e.currentTarget.value, e.currentTarget);
        }}
        onKeyDown={(e) => handleKeyDown(state, e, value, onChange)}
      />
      <PlaceholderSuggestions
        visible={state.visible}
        suggestions={state.suggestions}
        selectedIndex={state.selectedIndex}
        position={state.position}
        onSelect={(index) => applySelection(state, index, value, onChange)}
      />
    </>
  );
});
