import type { PlaceholderInfo } from "../../../types/pipeline";

/**
 * Placeholder tokens available inside `World.initial_message`.
 *
 * Names are stored unbraced (`CHARACTER_NAME`, not `{CHARACTER_NAME}`);
 * surrounding braces are added at insertion time by the editor — same
 * convention as the pipeline stage prompt placeholders.
 *
 * Substituted at chat start in `backend/app/services/chat_service.py`.
 */
export const INITIAL_MESSAGE_PLACEHOLDERS: PlaceholderInfo[] = [
  {
    name: "CHARACTER_NAME",
    description: "The chat session character name",
    category: "Character",
  },
  {
    name: "LOCATION_NAME",
    description: "The starting location name",
    category: "Location",
  },
  {
    name: "LOCATION_SUMMARY",
    description: "The starting location content / summary",
    category: "Location",
  },
];
