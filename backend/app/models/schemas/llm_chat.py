"""Pydantic schemas for the LLM chat endpoint."""

from pydantic import BaseModel


class ChatMessageIn(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class LlmChatRequest(BaseModel):
    model_id: str
    messages: list[ChatMessageIn]
    temperature: float = 0.7
    top_p: float = 1.0
    repetition_penalty: float = 1.0
    enable_thinking: bool = False
    current_content: str
    world_id: str
    doc_id: str
    doc_type: str  # "location" | "npc" | "lore_fact"
