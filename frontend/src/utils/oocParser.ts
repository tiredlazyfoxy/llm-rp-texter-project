/** Extract (( ... )) OOC user instructions from message text. */
export function extractUserInstructions(text: string): { content: string; userInstructions: string | null } {
  const parts: string[] = [];
  const content = text.replace(/\(\((.+?)\)\)/gs, (_, inner: string) => {
    parts.push(inner.trim());
    return "";
  }).trim();
  return { content, userInstructions: parts.length ? parts.join("\n") : null };
}
