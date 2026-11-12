from typing import List
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from app.auth.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.auth import TokenData
from app.models.player import LeaderboardEntry, PlayerResponse, PlayerUpdate

router = APIRouter(tags=["Players"])


@router.get("/me", response_model=PlayerResponse)
async def get_my_profile(
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Retrieve profile and progression statistics for the currently authenticated player."""
    row = await conn.fetchrow(
        """
        SELECT player_id, username, email, role, gold, level, xp, created_at
        FROM players
        WHERE player_id = $1
        """,
        current_user.player_id,
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player profile not found",
        )
    return PlayerResponse(**dict(row))


@router.put("/me", response_model=PlayerResponse)
async def update_my_profile(
    update_data: PlayerUpdate,
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Update profile fields for the authenticated player."""
    # Check if email is being changed and if it is already taken
    if update_data.email is not None:
        conflict = await conn.fetchrow(
            "SELECT player_id FROM players WHERE email = $1 AND player_id != $2",
            update_data.email,
            current_user.player_id,
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already in use by another player",
            )

    fields = []
    values = []
    idx = 1

    if update_data.email is not None:
        fields.append(f"email = ${idx}")
        values.append(update_data.email)
        idx += 1

    if update_data.gold is not None:
        fields.append(f"gold = ${idx}")
        values.append(update_data.gold)
        idx += 1

    if update_data.level is not None:
        fields.append(f"level = ${idx}")
        values.append(update_data.level)
        idx += 1

    if update_data.xp is not None:
        fields.append(f"xp = ${idx}")
        values.append(update_data.xp)
        idx += 1

    if not fields:
        # No updates provided, return current profile
        row = await conn.fetchrow(
            "SELECT player_id, username, email, role, gold, level, xp, created_at FROM players WHERE player_id = $1",
            current_user.player_id,
        )
        return PlayerResponse(**dict(row))

    values.append(current_user.player_id)
    query = f"""
        UPDATE players
        SET {', '.join(fields)}
        WHERE player_id = ${idx}
        RETURNING player_id, username, email, role, gold, level, xp, created_at
    """

    row = await conn.fetchrow(query, *values)
    return PlayerResponse(**dict(row))


@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(conn: asyncpg.Connection = Depends(get_db)):
    """Retrieve global player leaderboard using analytical window functions from the player_leaderboard view."""
    rows = await conn.fetch(
        """
        SELECT 
            leaderboard_rank AS rank,
            username,
            level,
            xp,
            gold,
            quest_completion_count AS quests_completed,
            total_items_owned AS total_items
        FROM player_leaderboard
        ORDER BY leaderboard_rank ASC, username ASC
        LIMIT 100
        """
    )
    return [LeaderboardEntry(**dict(row)) for row in rows]


@router.get("/{player_id}", response_model=PlayerResponse)
async def get_player_by_id(
    player_id: int,
    _: TokenData = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Retrieve player profile by ID (Administrative privilege required)."""
    row = await conn.fetchrow(
        """
        SELECT player_id, username, email, role, gold, level, xp, created_at
        FROM players
        WHERE player_id = $1
        """,
        player_id,
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Player with ID {player_id} not found",
        )
    return PlayerResponse(**dict(row))
