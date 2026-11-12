import json
from typing import List
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from qdrant_client.http import models
from app.auth.dependencies import get_current_user, require_admin
from app.config import get_settings
from app.database import get_db
from app.models.auth import TokenData
from app.models.npc import NPCCreate, NPCResponse, NPCRelationship, NPCUpdate
from app.qdrant_client import get_qdrant_client

router = APIRouter(tags=["NPCs"])


def _format_npc_row(row) -> NPCResponse:
    d = dict(row)
    traits = d.get("personality_traits")
    if isinstance(traits, str):
        try:
            d["personality_traits"] = json.loads(traits)
        except Exception:
            d["personality_traits"] = {}
    elif traits is None:
        d["personality_traits"] = {}
    return NPCResponse(**d)


@router.get("/", response_model=List[NPCResponse])
async def list_npcs(conn: asyncpg.Connection = Depends(get_db)):
    """Retrieve catalog of all active NPCs in the game world."""
    rows = await conn.fetch(
        "SELECT npc_id, name, persona, location, personality_traits, greeting FROM npcs ORDER BY npc_id ASC"
    )
    return [_format_npc_row(r) for r in rows]


@router.get("/{npc_id}", response_model=NPCResponse)
async def get_npc(npc_id: int, conn: asyncpg.Connection = Depends(get_db)):
    """Retrieve NPC configuration, persona, and personality traits by ID."""
    row = await conn.fetchrow(
        "SELECT npc_id, name, persona, location, personality_traits, greeting FROM npcs WHERE npc_id = $1",
        npc_id,
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NPC with ID {npc_id} does not exist",
        )
    return _format_npc_row(row)


@router.get("/{npc_id}/relationship", response_model=NPCRelationship)
async def get_npc_relationship(
    npc_id: int,
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Retrieve the current player's dynamic affinity and interaction history with an NPC."""
    # Ensure NPC exists
    npc_row = await conn.fetchrow("SELECT npc_id, name FROM npcs WHERE npc_id = $1", npc_id)
    if not npc_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NPC with ID {npc_id} does not exist",
        )

    rel_row = await conn.fetchrow(
        """
        SELECT 
            relationship_id,
            player_id,
            npc_id,
            affinity_score,
            interaction_count,
            last_interaction
        FROM npc_relationships
        WHERE player_id = $1 AND npc_id = $2
        """,
        current_user.player_id,
        npc_id,
    )

    if rel_row:
        return NPCRelationship(
            relationship_id=rel_row["relationship_id"],
            player_id=rel_row["player_id"],
            npc_id=rel_row["npc_id"],
            npc_name=npc_row["name"],
            affinity_score=float(rel_row["affinity_score"]),
            interaction_count=rel_row["interaction_count"],
            last_interaction=rel_row["last_interaction"],
        )

    # Return initial default relationship if none exists
    return NPCRelationship(
        relationship_id=0,
        player_id=current_user.player_id,
        npc_id=npc_id,
        npc_name=npc_row["name"],
        affinity_score=0.0,
        interaction_count=0,
        last_interaction=None,
    )


@router.post("/", response_model=NPCResponse, status_code=status.HTTP_201_CREATED)
async def create_npc(
    npc_data: NPCCreate,
    _: TokenData = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Create a new NPC persona (Admin only)."""
    traits_json = json.dumps(npc_data.personality_traits or {})
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO npcs (name, persona, location, personality_traits, greeting)
            VALUES ($1, $2, $3, $4::jsonb, $5)
            RETURNING npc_id, name, persona, location, personality_traits, greeting
            """,
            npc_data.name,
            npc_data.persona,
            npc_data.location,
            traits_json,
            npc_data.greeting,
        )
    except asyncpg.exceptions.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An NPC with the name '{npc_data.name}' already exists",
        )
    return _format_npc_row(row)


@router.put("/{npc_id}", response_model=NPCResponse)
async def update_npc(
    npc_id: int,
    update_data: NPCUpdate,
    _: TokenData = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Update an existing NPC's persona, location, traits, or greeting (Admin only)."""
    fields = []
    values = []
    idx = 1

    if update_data.persona is not None:
        fields.append(f"persona = ${idx}")
        values.append(update_data.persona)
        idx += 1

    if update_data.location is not None:
        fields.append(f"location = ${idx}")
        values.append(update_data.location)
        idx += 1

    if update_data.personality_traits is not None:
        fields.append(f"personality_traits = ${idx}::jsonb")
        values.append(json.dumps(update_data.personality_traits))
        idx += 1

    if update_data.greeting is not None:
        fields.append(f"greeting = ${idx}")
        values.append(update_data.greeting)
        idx += 1

    if not fields:
        row = await conn.fetchrow(
            "SELECT npc_id, name, persona, location, personality_traits, greeting FROM npcs WHERE npc_id = $1",
            npc_id,
        )
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NPC not found")
        return _format_npc_row(row)

    values.append(npc_id)
    query = f"""
        UPDATE npcs
        SET {', '.join(fields)}
        WHERE npc_id = ${idx}
        RETURNING npc_id, name, persona, location, personality_traits, greeting
    """
    row = await conn.fetchrow(query, *values)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NPC not found")
    return _format_npc_row(row)


@router.delete("/{npc_id}", status_code=status.HTTP_200_OK)
async def delete_npc(
    npc_id: int,
    _: TokenData = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Delete NPC from relational database and purge associated memories from Qdrant (Admin only)."""
    # 1. Delete from PostgreSQL
    res = await conn.execute("DELETE FROM npcs WHERE npc_id = $1", npc_id)
    if res == "DELETE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NPC with ID {npc_id} not found",
        )

    # 2. Delete all Qdrant memories for this NPC
    settings = get_settings()
    try:
        q_client = get_qdrant_client()
        q_client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[models.FieldCondition(key="npc_id", match=models.MatchValue(value=npc_id))]
                )
            ),
        )
    except Exception as exc:
        # Log notice but do not abort since relational row was deleted
        pass

    return {"detail": f"NPC {npc_id} and associated vector memories deleted successfully"}
