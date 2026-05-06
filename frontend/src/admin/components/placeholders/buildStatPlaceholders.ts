import type { StatDefinitionItem } from "../../../types/world";
import type { PlaceholderInfo } from "../../../types/pipeline";

/**
 * One placeholder badge per `WorldStatDefinition`. Mirrors the
 * runtime substitution semantics from Feature 012 step 001:
 *
 * - `scope === "character"` → owner `user`,  token `{USER:NAME}`
 * - `scope === "world"`     → owner `world`, token `{WORLD:NAME}`
 *
 * `hidden` is included only as metadata — it does NOT gate the
 * placeholder (chat runtime substitutes hidden stats just like
 * visible ones; only the player-facing stats panel hides them).
 */
export interface StatPlaceholder {
  /** Full braced token, e.g. `"{USER:HEALTH}"`. */
  token: string;
  /** Display label without braces, e.g. `"USER:HEALTH"`. */
  label: string;
  owner: "user" | "world";
  kind: "int" | "enum" | "set";
  hidden: boolean;
}

function ownerForScope(scope: string): "user" | "world" {
  return scope === "world" ? "world" : "user";
}

function kindForStatType(stat_type: string): "int" | "enum" | "set" {
  if (stat_type === "enum") return "enum";
  if (stat_type === "set") return "set";
  return "int";
}

export function buildStatPlaceholders(
  defs: StatDefinitionItem[],
): StatPlaceholder[] {
  return defs.map((def) => {
    const owner = ownerForScope(def.scope);
    const prefix = owner === "user" ? "USER" : "WORLD";
    const label = `${prefix}:${def.name}`;
    return {
      token: `{${label}}`,
      label,
      owner,
      kind: kindForStatType(def.stat_type),
      hidden: def.hidden,
    };
  });
}

/**
 * Convert stat placeholders into the `PlaceholderInfo` shape consumed
 * by `PlaceholderTextarea` / `PlaceholderSuggestions` autocomplete.
 * The `name` is the unbraced label (e.g. `"USER:HEALTH"`); the
 * autocomplete adds braces at insertion time.
 */
export function statPlaceholdersToInfo(
  stats: StatPlaceholder[],
): PlaceholderInfo[] {
  return stats.map((s) => ({
    name: s.label,
    description: `Live ${s.owner} stat (${s.kind}${s.hidden ? ", hidden" : ""})`,
    category: "Stats",
  }));
}
