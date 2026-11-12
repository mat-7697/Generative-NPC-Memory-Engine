from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class NPCResponse(BaseModel):
    npc_id: int
    name: str
    persona: str
    location: Optional[str] = None
    personality_traits: Dict[str, Any] = Field(default_factory=dict)
    greeting: Optional[str] = None


class NPCCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    persona: str = Field(..., min_length=1)
    location: Optional[str] = Field(None, max_length=100)
    personality_traits: Optional[Dict[str, Any]] = Field(default_factory=dict)
    greeting: Optional[str] = None


class NPCUpdate(BaseModel):
    persona: Optional[str] = None
    location: Optional[str] = None
    personality_traits: Optional[Dict[str, Any]] = None
    greeting: Optional[str] = None


class NPCRelationship(BaseModel):
    relationship_id: int
    player_id: int
    npc_id: int
    npc_name: Optional[str] = None
    affinity_score: float
    interaction_count: int
    last_interaction: Optional[datetime] = None
