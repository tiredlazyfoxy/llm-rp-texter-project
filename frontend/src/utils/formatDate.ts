/** Format ISO date string: today → "HH:MM", otherwise → "YYYY-MM-DD" */
export function formatDate(iso: string | null, fallback = "-"): string {
  if (!iso) return fallback;
  const d = new Date(iso);
  const now = new Date();
  const isToday =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  if (isToday) {
    return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false });
  }
  return d.toISOString().slice(0, 10);
}
