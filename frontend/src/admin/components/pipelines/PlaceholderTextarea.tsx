import { useState } from "react";
import { Textarea, type TextareaProps } from "@mantine/core";
import { observer } from "mobx-react-lite";
import type { PlaceholderInfo } from "../../../types/pipeline";
import { PlaceholderSuggestions } from "./PlaceholderSuggestions";
import {
  PlaceholderAutocompleteState,
  applySelection,
  handleKeyDown,
  onTextChange,
} from "./placeholderAutocompleteState";

interface PlaceholderTextareaProps {
  value: string;
  onChange: (v: string) => void;
  placeholders: PlaceholderInfo[];
  textareaProps?: Omit<TextareaProps, "value" | "onChange" | "onKeyDown" | "ref">;
}

export const PlaceholderTextarea = observer(function PlaceholderTextarea({
  value,
  onChange,
  placeholders,
  textareaProps,
}: PlaceholderTextareaProps) {
  const [state] = useState(() => new PlaceholderAutocompleteState());

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
