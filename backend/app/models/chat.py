from typing import Any, Dict, List, Literal
from pydantic import BaseModel, Field
from app.models.memory import MemoryResponse


class ChatTurn(BaseModel):
    role: Literal["player", "npc"]
    text: str = Field(..., min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    npc_id: int = Field(..., gt=0, description="Target NPC ID")
    message: str = Field(..., min_length=1, description="Player message content")
    history: List[ChatTurn] = Field(
        default_factory=list,
        max_length=20,
        description="Recent on-screen dialogue (oldest first). Used as conversation context "
        "when long-term memory (Qdrant) has no recent turns or is unavailable.",
    )


class ChatResponse(BaseModel):
    reply: str
    npc_name: str
    memories_used: List[MemoryResponse] = Field(default_factory=list)
    game_state: Dict[str, Any] = Field(default_factory=dict)
    affinity_change: float
    source: str = Field("mock", description='Gemini model that wrote the reply, or "mock"')
    memory_online: bool = Field(True, description="False if long-term memory (Qdrant) was unavailable")
