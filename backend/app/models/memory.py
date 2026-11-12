from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MemoryCreate(BaseModel):
    npc_id: int
    text: str = Field(..., min_length=1)
    role: str = Field("player", description="'player', 'npc', or 'system'")
    importance: float = Field(0.5, ge=0.0, le=10.0)


class MemoryResponse(BaseModel):
    id: str
    player_id: int
    npc_id: int
    text: str
    role: str
    importance: float
    timestamp: float
    score: Optional[float] = None


class MemoryUpdate(BaseModel):
    text: Optional[str] = None
    importance: Optional[float] = Field(None, ge=0.0, le=10.0)


class MemorySearch(BaseModel):
    npc_id: int
    query: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=50)


class MemoryStats(BaseModel):
    total_memories: int
    by_npc: List[Dict[str, Any]] = Field(default_factory=list)
    by_player: List[Dict[str, Any]] = Field(default_factory=list)
    recent: List[Dict[str, Any]] = Field(default_factory=list)
