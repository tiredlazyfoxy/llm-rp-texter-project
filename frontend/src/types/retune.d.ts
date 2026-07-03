/**
 * Combined retune status poll DTO — mirrors backend `RetuneStatusResponse`
 * (`backend/app/models/schemas/chat.py`). Response body for
 * `POST /api/chats/{chatId}/retune`, `POST /api/chats/{chatId}/retune/stop`,
 * and `GET /api/chats/{chatId}/retune/status`. One poll learns both the
 * running->idle edge and the current profile values. `world_id` is a string.
 */
export interface RetuneStatus {
  running: boolean;
  plan_tuning: string;
  tone_tuning: string;
  world_id: string;
}
