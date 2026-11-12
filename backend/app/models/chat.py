from typing import Any, Dict, List
from pydantic import BaseModel, Field
from app.models.memory import MemoryResponse


class ChatRequest(BaseModel):
    npc_id: int = Field(..., gt=0, description="Target NPC ID")
    message: str = Field(..., min_length=1, description="Player message content")


class ChatResponse(BaseModel):
    reply: str
    npc_name: str
    memories_used: List[MemoryResponse] = Field(default_factory=list)
    game_state: Dict[str, Any] = Field(default_factory=dict)
    affinity_change: float
