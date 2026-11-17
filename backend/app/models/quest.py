from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class QuestResponse(BaseModel):
    quest_id: int
    title: str
    description: Optional[str] = None
    reward_gold: int
    reward_xp: int
    reward_item_id: Optional[int] = None
    min_level: int
    quest_type: str
    challenge_type: Optional[str] = None
    challenge_question: Optional[str] = None
    challenge_hint: Optional[str] = None


class PlayerQuestResponse(BaseModel):
    player_quest_id: Optional[int] = None
    quest_id: int
    title: str
    description: Optional[str] = None
    reward_gold: Optional[int] = None
    reward_xp: Optional[int] = None
    reward_item_id: Optional[int] = None
    min_level: Optional[int] = None
    quest_type: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    can_start: bool = True
    challenge_type: Optional[str] = None
    challenge_question: Optional[str] = None
    challenge_hint: Optional[str] = None


class QuestCompleteRequest(BaseModel):
    solution: Optional[str] = Field(None, description="Player submitted solution or CTF flag to complete quest")
    answer: Optional[str] = Field(None, description="Alias for `solution` (sent by the web client)")

    def submitted(self) -> str:
        return (self.solution or self.answer or "").strip()


class PrerequisiteChain(BaseModel):
    quest_id: int
    title: Optional[str] = None
    required_quest_id: Optional[int] = None
    required_quest_title: Optional[str] = None
    depth: int
    path: str


class QuestCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    reward_gold: Optional[int] = Field(0, ge=0)
    reward_xp: Optional[int] = Field(0, ge=0)
    reward_item_id: Optional[int] = None
    min_level: Optional[int] = Field(1, ge=1)
    quest_type: Optional[str] = Field("main", pattern="^(main|side|daily|hidden)$")


class QuestUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    reward_gold: Optional[int] = Field(None, ge=0)
    reward_xp: Optional[int] = Field(None, ge=0)
    reward_item_id: Optional[int] = None
    min_level: Optional[int] = Field(None, ge=1)
    quest_type: Optional[str] = Field(None, pattern="^(main|side|daily|hidden)$")
