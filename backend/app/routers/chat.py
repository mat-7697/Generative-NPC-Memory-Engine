import asyncio
import json
import logging
import threading
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple
import uuid
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.database import get_db, get_pool
from app.limiter import limiter
from app.models.auth import TokenData
from app.models.chat import ChatRequest, ChatResponse
from app.models.memory import MemoryResponse
from app.services.chat_fusion import (
    build_prompt,
    get_recent_dialogue,
    load_game_state,
    search_memories,
    update_relationship,
)
from app.services.embedding import embed_text
from app.services.llm import generate_response_with_source, stream_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Generative NPC Chat & Fusion"])
settings = get_settings()


def _compute_affinity_delta(message: str) -> float:
    """Heuristic sentiment score evaluating player courtesy vs hostility."""
    lower = message.lower()
    friendly_tokens = [
        "thank", "thanks", "please", "help", "honor", "great", "glad",
        "friend", "appreciate", "kind", "hello", "greetings", "good",
    ]
    hostile_tokens = [
        "idiot", "fool", "die", "kill", "hate", "ugly", "shut up",
        "trash", "steal", "rob", "stupid", "worthless", "attack",
    ]

    hostile_matches = sum(1 for t in hostile_tokens if t in lower)
    friendly_matches = sum(1 for t in friendly_tokens if t in lower)

    if hostile_matches > 0:
        return -2.0 * hostile_matches
    if friendly_matches > 0:
        return min(3.0, 1.0 + (0.5 * (friendly_matches - 1)))
    return 0.5


async def _prepare_turn(
    conn: asyncpg.Connection, player_id: int, npc_id: int, message: str,
    client_history: Optional[List[dict]] = None,
) -> Tuple[Dict[str, Any], List[dict], Any, List[float], str, str, List[dict]]:
    """Steps 1-4: load game state, embed the message, recall memories and recent
    dialogue, build the prompt."""
    # 1. Load comprehensive game state from PostgreSQL (fast read, no lock held)
    game_state = await load_game_state(conn, player_id, npc_id)
    npc = game_state.get("npc")
    if not npc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NPC with ID {npc_id} does not exist",
        )

    # 2. Embed the player's message in thread pool to prevent blocking FastAPI event loop
    query_vector = await asyncio.to_thread(embed_text, message)

    # 3. Retrieve relevant past memories from Qdrant in thread pool
    retrieved_memories: List[dict] = []
    q_client = None
    try:
        from app.qdrant_client import get_qdrant_client
        q_client = get_qdrant_client()
        retrieved_memories = await asyncio.to_thread(
            search_memories,
            client=q_client,
            player_id=player_id,
            npc_id=npc_id,
            query_vector=query_vector,
            top_k=5,
        )
    except Exception as exc:
        logger.warning("Qdrant unavailable for memory retrieval: %s", exc)
        retrieved_memories = []

    # 3b. Recent back-and-forth, sent to the LLM as real conversation turns
    history: List[dict] = []
    if q_client is not None:
        history = await asyncio.to_thread(get_recent_dialogue, q_client, player_id, npc_id)
    recent_ids = {h["id"] for h in history}
    # Fall back to the dialogue the client has on screen, so the NPC still follows
    # the current conversation when long-term memory is empty or offline.
    if not history and client_history:
        history = client_history[-10:]

    # 4. Build system prompt and context incorporating persona and state.
    # Memories already present in the recent history aren't repeated in the context.
    system_prompt, context = build_prompt(
        npc=npc,
        game_state=game_state,
        memories=[m for m in retrieved_memories if m["id"] not in recent_ids],
        player_message=message,
    )
    return game_state, retrieved_memories, q_client, query_vector, system_prompt, context, history


async def _finalize_turn(
    conn: asyncpg.Connection,
    player_id: int,
    npc_id: int,
    message: str,
    npc_reply: str,
    game_state: Dict[str, Any],
    q_client: Any,
    query_vector: List[float],
) -> float:
    """Steps 6-7: commit relationship progression, then store both turns as memories."""
    # 6. Atomic, quick PostgreSQL transaction to update relationship affinity and counts
    affinity_delta = _compute_affinity_delta(message)
    async with conn.transaction():
        new_affinity = await update_relationship(
            conn=conn,
            player_id=player_id,
            npc_id=npc_id,
            affinity_delta=affinity_delta,
        )
    game_state["relationship"]["affinity_score"] = new_affinity
    game_state["relationship"]["interaction_count"] += 1

    # 7. Asynchronously store player query and NPC reply into Qdrant as persistent memories
    if q_client is not None:
        try:
            from qdrant_client.http import models as qmodels

            now = time.time()
            session_id = f"session_{player_id}_{npc_id}"
            npc_vector = await asyncio.to_thread(embed_text, npc_reply)
            points_to_upsert = [
                qmodels.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=query_vector,
                    payload={
                        "player_id": player_id,
                        "npc_id": npc_id,
                        "session_id": session_id,
                        "text": message,
                        "content": message,
                        "role": "player",
                        "importance": 0.5,
                        "timestamp": now,
                    },
                ),
                qmodels.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=npc_vector,
                    payload={
                        "player_id": player_id,
                        "npc_id": npc_id,
                        "session_id": session_id,
                        "text": npc_reply,
                        "content": npc_reply,
                        "role": "npc",
                        "importance": 0.6,
                        "timestamp": now + 0.001,
                    },
                ),
            ]
            await asyncio.to_thread(
                q_client.upsert,
                collection_name=settings.qdrant_collection,
                points=points_to_upsert,
            )
        except Exception as exc:
            logger.warning("Qdrant upsert failed (non-fatal): %s", exc)

    return affinity_delta


def _memories_response(memories: List[dict]) -> List[MemoryResponse]:
    return [
        MemoryResponse(
            id=m["id"],
            player_id=m["player_id"],
            npc_id=m["npc_id"],
            text=m["text"],
            role=m["role"],
            importance=m["importance"],
            timestamp=m["timestamp"],
            score=m.get("score"),
        )
        for m in memories
    ]


@router.post("/", response_model=ChatResponse)
@limiter.limit(settings.rate_limit_chat)
async def chat_with_npc(
    request: Request,
    chat_data: ChatRequest,
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """End-to-end multimodal fusion chat pipeline.

    Execution Pipeline (Optimized Non-Blocking & Transaction Isolated):
    1. Fast relational state retrieval (no long-lived transaction held).
    2. Asynchronous embedding computation off the event loop.
    3. Non-blocking semantic vector retrieval from Qdrant.
    4. Prompt synthesis with Big-Five personality traits & game state context.
    5. Asynchronous LLM inference outside of database transactions.
    6. Atomic, short-lived PostgreSQL transaction to commit relationship progression.
    7. Asynchronous memory persistence into Qdrant vector index.
    """
    try:
        player_id, npc_id, message = current_user.player_id, chat_data.npc_id, chat_data.message
        (game_state, memories, q_client, query_vector,
         system_prompt, context, history) = await _prepare_turn(
            conn, player_id, npc_id, message, [t.model_dump() for t in chat_data.history]
        )

        # 5. Generate LLM response asynchronously OUTSIDE of any database transaction
        npc_reply, source = await asyncio.to_thread(
            generate_response_with_source,
            system_prompt=system_prompt,
            user_message=message,
            context=context,
            history=history,
        )

        affinity_delta = await _finalize_turn(
            conn, player_id, npc_id, message, npc_reply, game_state, q_client, query_vector
        )

        return ChatResponse(
            reply=npc_reply,
            npc_name=game_state["npc"]["name"],
            memories_used=_memories_response(memories),
            game_state=game_state,
            affinity_change=affinity_delta,
            source=source,
            memory_online=q_client is not None,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Chat endpoint error: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat processing error: {str(exc)}",
        )


def _sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def _iterate_in_thread(sync_gen):
    """Drive a blocking generator in a worker thread, yielding its items asynchronously."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    done = object()

    def worker():
        try:
            for item in sync_gen:
                loop.call_soon_threadsafe(queue.put_nowait, item)
        except Exception as exc:  # surfaced to the async side
            loop.call_soon_threadsafe(queue.put_nowait, exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, done)

    threading.Thread(target=worker, daemon=True).start()
    while True:
        item = await queue.get()
        if item is done:
            return
        if isinstance(item, Exception):
            raise item
        yield item


@router.post("/stream")
@limiter.limit(settings.rate_limit_chat)
async def chat_with_npc_stream(
    request: Request,
    chat_data: ChatRequest,
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Same pipeline as POST /api/chat/, but the NPC reply streams back token-by-token
    as Server-Sent Events: `meta`, then many `delta`, then `done` (or `error`)."""
    player_id, npc_id, message = current_user.player_id, chat_data.npc_id, chat_data.message
    # Run steps 1-4 before streaming starts so a bad NPC id returns a normal HTTP error.
    (game_state, memories, q_client, query_vector,
     system_prompt, context, history) = await _prepare_turn(
        conn, player_id, npc_id, message, [t.model_dump() for t in chat_data.history]
    )

    async def event_stream():
        yield _sse("meta", {
            "npc_name": game_state["npc"]["name"],
            "memories_used": [m.model_dump() for m in _memories_response(memories)],
            "memory_online": q_client is not None,
        })

        parts: List[str] = []
        source: Optional[str] = None
        try:
            async for kind, value in _iterate_in_thread(
                stream_response(system_prompt, message, context, history)
            ):
                if kind == "delta":
                    parts.append(value)
                    yield _sse("delta", {"text": value})
                elif kind == "source":
                    source = value
        except Exception as exc:
            logger.error("Streaming chat error: %s\n%s", exc, traceback.format_exc())
            yield _sse("error", {"detail": f"Chat processing error: {exc}"})
            return

        npc_reply = "".join(parts).strip()
        try:
            # A fresh pooled connection: the request-scoped one may already be released.
            pool = get_pool()
            async with pool.acquire() as fin_conn:
                affinity_delta = await _finalize_turn(
                    fin_conn, player_id, npc_id, message, npc_reply,
                    game_state, q_client, query_vector,
                )
        except Exception as exc:
            logger.error("Failed to persist streamed chat turn: %s", exc)
            affinity_delta = 0.0

        yield _sse("done", {
            "reply": npc_reply,
            "source": source or "mock",
            "affinity_change": affinity_delta,
            "game_state": game_state,
        })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
