import re
from typing import List, Optional
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.auth import TokenData
from app.models.quest import (
    PlayerQuestResponse,
    PrerequisiteChain,
    QuestCompleteRequest,
    QuestResponse,
)

router = APIRouter(tags=["Quests"])


def _normalize_answer(text: str) -> str:
    """Lenient comparison key: case-insensitive, ignores punctuation/spacing and a leading article.

    "The Echo!", "an echo" and "ECHO" all normalize to "echo"; "Moon-Orchid" and "moon orchid" match.
    """
    text = text.strip().lower()
    text = re.sub(r"^(the|an|a)\s+", "", text)
    return re.sub(r"[^a-z0-9]", "", text)


@router.get("/search", response_model=List[QuestResponse])
async def search_quests(
    query: str = Query(..., min_length=1, description="Full-text search keywords for quest title or description"),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Full-text search across quests catalog using tsvector and ts_rank."""
    rows = await conn.fetch(
        """
        SELECT quest_id, title, description, reward_gold, reward_xp, reward_item_id, min_level, quest_type,
               challenge_type, challenge_question, challenge_hint
        FROM quests
        WHERE search_vector @@ plainto_tsquery('english', $1)
        ORDER BY ts_rank(search_vector, plainto_tsquery('english', $1)) DESC
        """,
        query.strip(),
    )
    return [QuestResponse(**dict(r)) for r in rows]


@router.get("/my-quests", response_model=List[PlayerQuestResponse])
async def get_my_quests(
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Retrieve player quest lifecycle status matrix including prerequisite eligibility."""
    rows = await conn.fetch(
        """
        SELECT 
            pq.player_quest_id,
            q.quest_id,
            q.title,
            q.description,
            q.reward_gold,
            q.reward_xp,
            q.reward_item_id,
            q.min_level,
            q.quest_type,
            COALESCE(pq.status, 'available') AS status,
            pq.started_at,
            pq.completed_at,
            can_start_quest($1, q.quest_id) AS can_start,
            q.challenge_type,
            q.challenge_question,
            q.challenge_hint
        FROM quests q
        LEFT JOIN player_quests pq ON q.quest_id = pq.quest_id AND pq.player_id = $1
        ORDER BY q.min_level ASC, q.quest_id ASC
        """,
        current_user.player_id,
    )
    return [PlayerQuestResponse(**dict(r)) for r in rows]


@router.post("/reset-progress")
async def reset_quest_progress(
    reset_level: bool = False,
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Reset player quest logs back to available for live challenge demonstration."""
    await conn.execute("DELETE FROM player_quests WHERE player_id = $1", current_user.player_id)
    if reset_level:
        await conn.execute("UPDATE players SET level = 1, xp = 0 WHERE player_id = $1", current_user.player_id)
    return {"detail": "Quest progress reset! You can now accept and solve challenges from the beginning."}


@router.get("/", response_model=List[QuestResponse])
async def list_quests(conn: asyncpg.Connection = Depends(get_db)):
    """Retrieve all quests available in the game catalog."""
    rows = await conn.fetch(
        """
        SELECT quest_id, title, description, reward_gold, reward_xp, reward_item_id, min_level, quest_type,
               challenge_type, challenge_question, challenge_hint
        FROM quests
        ORDER BY min_level ASC, quest_id ASC
        """
    )
    return [QuestResponse(**dict(r)) for r in rows]


@router.get("/{quest_id}", response_model=QuestResponse)
async def get_quest(quest_id: int, conn: asyncpg.Connection = Depends(get_db)):
    """Retrieve specific quest details by ID."""
    row = await conn.fetchrow(
        """
        SELECT quest_id, title, description, reward_gold, reward_xp, reward_item_id, min_level, quest_type,
               challenge_type, challenge_question, challenge_hint
        FROM quests
        WHERE quest_id = $1
        """,
        quest_id,
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quest with ID {quest_id} not found",
        )
    return QuestResponse(**dict(row))


@router.get("/{quest_id}/prerequisites", response_model=List[PrerequisiteChain])
async def get_prerequisites(quest_id: int, conn: asyncpg.Connection = Depends(get_db)):
    """Traverse the hierarchical prerequisite DAG for a quest via recursive CTE get_prerequisite_chain()."""
    rows = await conn.fetch(
        "SELECT quest_id, quest_title, required_quest_id, required_quest_title, depth, prerequisite_path FROM get_prerequisite_chain($1)",
        quest_id,
    )
    return [
        PrerequisiteChain(
            quest_id=r["quest_id"],
            title=r["quest_title"],
            required_quest_id=r["required_quest_id"],
            required_quest_title=r["required_quest_title"],
            depth=r["depth"],
            path=r["prerequisite_path"],
        )
        for r in rows
    ]


@router.post("/{quest_id}/start")
async def start_quest(
    quest_id: int,
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Start an available quest after recursively validating DAG prerequisites and player level."""
    # Check if quest exists
    quest = await conn.fetchrow("SELECT quest_id, title FROM quests WHERE quest_id = $1", quest_id)
    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quest with ID {quest_id} not found",
        )

    # Check existing status
    existing = await conn.fetchrow(
        "SELECT status FROM player_quests WHERE player_id = $1 AND quest_id = $2",
        current_user.player_id,
        quest_id,
    )
    if existing and existing["status"] in ("active", "completed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Quest is already {existing['status']}",
        )

    # Validate recursive prerequisites and min_level via can_start_quest()
    can_start = await conn.fetchval(
        "SELECT can_start_quest($1, $2)",
        current_user.player_id,
        quest_id,
    )
    if not can_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot start quest: level requirement or prerequisite quest chain not completed",
        )

    row = await conn.fetchrow(
        """
        INSERT INTO player_quests (player_id, quest_id, status, started_at)
        VALUES ($1, $2, 'active', NOW())
        ON CONFLICT (player_id, quest_id)
        DO UPDATE SET status = 'active', started_at = NOW()
        RETURNING player_quest_id, status, started_at
        """,
        current_user.player_id,
        quest_id,
    )

    return {
        "detail": f"Quest '{quest['title']}' started successfully",
        "player_quest_id": row["player_quest_id"],
        "status": row["status"],
        "started_at": row["started_at"],
    }


@router.post("/{quest_id}/complete")
async def complete_quest(
    quest_id: int,
    payload: Optional[QuestCompleteRequest] = None,
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Complete an active quest, verifying challenge solution, awarding gold, XP, and potential bonus items atomically."""
    quest = await conn.fetchrow(
        """
        SELECT 
            pq.player_quest_id,
            pq.status,
            q.title,
            q.reward_gold,
            q.reward_xp,
            q.reward_item_id,
            q.challenge_type,
            q.challenge_question,
            q.challenge_hint,
            q.challenge_answer,
            i.name AS reward_item_name
        FROM player_quests pq
        JOIN quests q ON pq.quest_id = q.quest_id
        LEFT JOIN items i ON q.reward_item_id = i.item_id
        WHERE pq.player_id = $1 AND pq.quest_id = $2
        """,
        current_user.player_id,
        quest_id,
    )

    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quest has not been accepted by player",
        )

    if quest["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Quest cannot be completed because its current status is '{quest['status']}'",
        )

    # Validate challenge solution requirement.
    # challenge_answer may list several accepted answers separated by "|".
    expected_answer = (quest["challenge_answer"] or "").strip()
    if expected_answer:
        provided = payload.submitted() if payload else ""
        accepted = {_normalize_answer(a) for a in expected_answer.split("|") if a.strip()}
        if not provided or _normalize_answer(provided) not in accepted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect answer. Read the question again, or reveal the hint if you're stuck.",
            )

    # Gold, XP, reward item and ledger entry are granted by the
    # trg_reward_quest_completion trigger when status flips to 'completed'.
    await conn.execute(
        """
        UPDATE player_quests
        SET status = 'completed', completed_at = NOW()
        WHERE player_quest_id = $1
        """,
        quest["player_quest_id"],
    )

    return {
        "detail": f"Quest '{quest['title']}' completed successfully!",
        "reward_gold": quest["reward_gold"],
        "reward_xp": quest["reward_xp"],
        "reward_item": quest["reward_item_name"],
    }
