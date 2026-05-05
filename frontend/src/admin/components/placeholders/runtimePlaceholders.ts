import type { PlaceholderInfo } from "../../../types/pipeline";

/**
 * Runtime placeholder tokens shared by `World.initial_message` and
 * world document content (locations, NPCs, lore facts). Substituted at
 * chat runtime — `{LOCATION_NAME}` / `{LOCATION_SUMMARY}` resolve to
 * the player's current location for documents, and to the starting
 * location for `initial_message` (current == starting at chat creation).
 *
 * Names are stored unbraced (`CHARACTER_NAME`, not `{CHARACTER_NAME}`);
 * surrounding braces are added at insertion time by the editor — same
 * convention as the pipeline stage prompt placeholders.
 *
 * Substitution sites: `backend/app/services/chat_service.py`,
 * `backend/app/services/chat_context.py`, `backend/app/services/chat_tools.py`.
 */
export const RUNTIME_PLACEHOLDERS: PlaceholderInfo[] = [
  {
    name: "CHARACTER_NAME",
    description: "The chat session character name",
    category: "Character",
  },
  {
    name: "LOCATION_NAME",
    description: "The player's current location name",
    category: "Location",
  },
  {
    name: "LOCATION_SUMMARY",
    description: "The player's current location content / summary",
    category: "Location",
  },
];
