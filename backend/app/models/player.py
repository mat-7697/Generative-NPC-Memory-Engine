import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class PlayerResponse(BaseModel):
    player_id: int
    username: str
    email: str
    role: str
    gold: int
    level: int
    xp: int
    created_at: datetime


class PlayerUpdate(BaseModel):
    email: Optional[str] = None
    gold: Optional[int] = Field(None, ge=0)
    level: Optional[int] = Field(None, ge=1)
    xp: Optional[int] = Field(None, ge=0)

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        pattern = r"^[\w\.\+\-]+@[\w\.\-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower().strip()


class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    level: int
    xp: int
    gold: int
    quests_completed: int
    total_items: int
