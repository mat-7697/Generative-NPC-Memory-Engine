from collections import Counter
import math
import time
from typing import List, Optional
import uuid
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from qdrant_client.http import models
from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.auth import TokenData
from app.models.memory import (
    MemoryCreate,
    MemoryResponse,
    MemoryStats,
    MemoryUpdate,
)
from app.qdrant_client import get_qdrant_client
from app.services.embedding import embed_text

router = APIRouter(tags=["Generative Memory (Qdrant)"])


@router.get("/stats", response_model=MemoryStats)
async def get_memory_stats(
    current_user: TokenData = Depends(get_current_user),
):
    """Retrieve statistical aggregations of vector memories in Qdrant.

    Privacy & Tenant Isolation:
    - Administrators receive global statistics across all players and NPCs.
    - Standard players receive statistics strictly isolated to their own player_id.
    """
    settings = get_settings()
    client = get_qdrant_client()
    collection_name = settings.qdrant_collection

    is_admin = (current_user.role == "admin")
    own_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="player_id", match=models.MatchValue(value=current_user.player_id)
            )
        ]
    )
    scroll_filter = None if is_admin else own_filter

    try:
        count_res = client.count(
            collection_name=collection_name,
            count_filter=scroll_filter,
            exact=True,
        )
        total_memories = count_res.count
        player_memories = (
            client.count(collection_name=collection_name, count_filter=own_filter, exact=True).count
            if is_admin
            else total_memories
        )
    except Exception:
        # Graceful fallback when Qdrant is offline or starting up
        return MemoryStats(
            total_memories=0,
            by_npc=[],
            by_player=[],
            recent=[],
        )

    by_npc = []
    by_player = []
    recent = []

    try:
        scroll_res, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=scroll_filter,
            limit=500,
            with_payload=True,
            with_vectors=False,
        )

        npc_counts = Counter()
        player_counts = Counter()
        items = []

        for point in scroll_res:
            p = point.payload or {}
            n_id = p.get("npc_id")
            pl_id = p.get("player_id")

            # Enforce player data isolation: regular player must never see other player ids
            if not is_admin and pl_id != current_user.player_id:
                continue

            if n_id is not None:
                npc_counts[n_id] += 1
            if pl_id is not None:
                player_counts[pl_id] += 1

            items.append(
                {
                    "id": str(point.id),
                    "player_id": pl_id,
                    "npc_id": n_id,
                    "text": p.get("text") or p.get("content", ""),
                    "role": p.get("role", "player"),
                    "importance": p.get("importance", 0.5),
                    "timestamp": p.get("timestamp", 0.0),
                }
            )

        items.sort(key=lambda x: x["timestamp"], reverse=True)
        recent = items[:10]

        by_npc = [{"npc_id": k, "count": v} for k, v in npc_counts.items()]
        by_player = [{"player_id": k, "count": v} for k, v in player_counts.items()]

    except Exception:
        pass

    return MemoryStats(
        total_memories=total_memories,
        player_memories=player_memories,
        by_npc=by_npc,
        by_player=by_player,
        recent=recent,
    )


@router.get("/search", response_model=List[MemoryResponse])
async def search_memories(
    npc_id: Optional[int] = Query(None, description="Target NPC ID to filter memories (all NPCs if omitted)"),
    query: Optional[str] = Query(None, description="Semantic text query; omit to list most recent memories"),
    top_k: int = Query(5, ge=1, le=50, description="Number of results to retrieve"),
    current_user: TokenData = Depends(get_current_user),
):
    """Semantic vector search across NPC dialogue memories with recency-weighted decay scoring.

    With no query, returns the player's most recent memories (no similarity score).
    """
    settings = get_settings()
    client = get_qdrant_client()
    collection_name = settings.qdrant_collection

    conditions = [
        models.FieldCondition(
            key="player_id", match=models.MatchValue(value=current_user.player_id)
        )
    ]
    if npc_id is not None:
        conditions.append(
            models.FieldCondition(key="npc_id", match=models.MatchValue(value=npc_id))
        )
    query_filter = models.Filter(must=conditions)

    if not query or not query.strip():
        try:
            points, _ = client.scroll(
                collection_name=collection_name,
                scroll_filter=query_filter,
                limit=500,
                with_payload=True,
                with_vectors=False,
            )
        except Exception:
            return []
        recent = []
        for pt in points:
            p = pt.payload or {}
            recent.append(
                MemoryResponse(
                    id=str(pt.id),
                    player_id=int(p.get("player_id", current_user.player_id)),
                    npc_id=int(p.get("npc_id", npc_id or 0)),
                    text=p.get("text") or p.get("content", ""),
                    role=p.get("role", "player"),
                    importance=float(p.get("importance", 0.5)),
                    timestamp=float(p.get("timestamp", 0.0)),
                    score=None,
                )
            )
        recent.sort(key=lambda m: m.timestamp or 0.0, reverse=True)
        return recent[:top_k]

    query_vec = embed_text(query)

    try:
        search_hits = client.search(
            collection_name=collection_name,
            query_vector=query_vec,
            query_filter=query_filter,
            limit=top_k * 2,
        )
    except Exception:
        # Graceful fallback when Qdrant is offline
        return []

    now = time.time()
    results = []

    for hit in search_hits:
        p = hit.payload or {}
        mem_ts = float(p.get("timestamp", now))
        age_hours = max(0.0, (now - mem_ts) / 3600.0)
        recency_score = math.exp(-0.015 * age_hours)
        vector_score = float(hit.score)

        final_score = round((vector_score * 0.7) + (recency_score * 0.3), 4)

        results.append(
            MemoryResponse(
                id=str(hit.id),
                player_id=int(p.get("player_id", current_user.player_id)),
                npc_id=int(p.get("npc_id", npc_id or 0)),
                text=p.get("text") or p.get("content", ""),
                role=p.get("role", "player"),
                importance=float(p.get("importance", 0.5)),
                timestamp=mem_ts,
                score=final_score,
            )
        )

    results.sort(key=lambda m: m.score or 0.0, reverse=True)
    return results[:top_k]


@router.post("/", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    data: MemoryCreate,
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Embed and store a discrete memory event into Qdrant vector database."""
    # Verify NPC exists
    npc = await conn.fetchrow("SELECT npc_id FROM npcs WHERE npc_id = $1", data.npc_id)
    if not npc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NPC with ID {data.npc_id} does not exist",
        )

    settings = get_settings()
    client = get_qdrant_client()
    collection_name = settings.qdrant_collection

    memory_id = str(uuid.uuid4())
    now = time.time()
    vector = embed_text(data.text)

    payload = {
        "player_id": current_user.player_id,
        "npc_id": data.npc_id,
        "session_id": f"session_{current_user.player_id}_{data.npc_id}",
        "text": data.text,
        "content": data.text,
        "role": data.role,
        "importance": data.importance,
        "timestamp": now,
    }

    try:
        client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=memory_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to insert memory point into Qdrant: {exc}",
        )

    return MemoryResponse(
        id=memory_id,
        player_id=current_user.player_id,
        npc_id=data.npc_id,
        text=data.text,
        role=data.role,
        importance=data.importance,
        timestamp=now,
        score=1.0,
    )


@router.delete("/player/{player_id}/npc/{npc_id}")
async def delete_player_npc_memories(
    player_id: int,
    npc_id: int,
    current_user: TokenData = Depends(get_current_user),
):
    """Delete all vector memories for a specific player and NPC pair."""
    # Ensure authorization: must be either the target player or an admin
    if current_user.role != "admin" and current_user.player_id != player_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete memories belonging to another player",
        )

    settings = get_settings()
    client = get_qdrant_client()
    collection_name = settings.qdrant_collection

    try:
        client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="player_id", match=models.MatchValue(value=player_id)
                        ),
                        models.FieldCondition(
                            key="npc_id", match=models.MatchValue(value=npc_id)
                        ),
                    ]
                )
            ),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete memories: {exc}",
        )

    return {
        "detail": f"Purged all memories between Player #{player_id} and NPC #{npc_id}"
    }


@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    update_data: MemoryUpdate,
    current_user: TokenData = Depends(get_current_user),
):
    """Update text content (re-embedding) or importance score of an existing memory."""
    settings = get_settings()
    client = get_qdrant_client()
    collection_name = settings.qdrant_collection

    try:
        points = client.retrieve(
            collection_name=collection_name,
            ids=[memory_id],
            with_payload=True,
            with_vectors=True,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve memory point: {exc}",
        )

    if not points:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory with ID {memory_id} not found",
        )

    point = points[0]
    payload = point.payload or {}

    # Check ownership
    if current_user.role != "admin" and payload.get("player_id") != current_user.player_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot edit memories belonging to another player",
        )

    new_text = update_data.text if update_data.text is not None else payload.get("text", "")
    new_importance = (
        update_data.importance
        if update_data.importance is not None
        else payload.get("importance", 0.5)
    )

    payload["text"] = new_text
    payload["content"] = new_text
    payload["importance"] = new_importance

    if update_data.text is not None:
        vector = embed_text(new_text)
    else:
        vector = point.vector

    try:
        client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=memory_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update memory in Qdrant: {exc}",
        )

    return MemoryResponse(
        id=memory_id,
        player_id=int(payload.get("player_id", current_user.player_id)),
        npc_id=int(payload.get("npc_id", 0)),
        text=new_text,
        role=payload.get("role", "player"),
        importance=new_importance,
        timestamp=float(payload.get("timestamp", time.time())),
        score=1.0,
    )


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    """Delete a single memory point from Qdrant vector collection."""
    settings = get_settings()
    client = get_qdrant_client()
    collection_name = settings.qdrant_collection

    # Retrieve to check ownership
    points = client.retrieve(
        collection_name=collection_name,
        ids=[memory_id],
        with_payload=True,
    )
    if not points:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory with ID {memory_id} not found",
        )

    point = points[0]
    payload = point.payload or {}
    if current_user.role != "admin" and payload.get("player_id") != current_user.player_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete memories belonging to another player",
        )

    try:
        client.delete(
            collection_name=collection_name,
            points_selector=models.PointIdsList(points=[memory_id]),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete memory: {exc}",
        )

    return {"detail": f"Memory {memory_id} deleted successfully"}
