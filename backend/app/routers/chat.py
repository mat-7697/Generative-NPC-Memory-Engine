import logging
import time
import traceback
from typing import List
import uuid
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.database import get_db
from app.limiter import limiter
from app.models.auth import TokenData
from app.models.chat import ChatRequest, ChatResponse
from app.models.memory import MemoryResponse
from app.services.chat_fusion import (
    build_prompt,
    load_game_state,
    search_memories,
    update_relationship,
)
from app.services.embedding import embed_text
from app.services.llm import generate_response

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


@router.post("/", response_model=ChatResponse)
@limiter.limit(settings.rate_limit_chat)
async def chat_with_npc(
    request: Request,
    chat_data: ChatRequest,
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """End-to-end multimodal fusion chat pipeline linking PostgreSQL relational context and Qdrant vector memory."""
    try:
        async with conn.transaction():
            # 1. Load comprehensive game state from PostgreSQL
            game_state = await load_game_state(
                conn, current_user.player_id, chat_data.npc_id
            )
            npc = game_state.get("npc")
            if not npc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"NPC with ID {chat_data.npc_id} does not exist",
                )

            # 2. Embed the player's message
            query_vector = embed_text(chat_data.message)

            # 3. Retrieve relevant past memories from Qdrant (graceful fallback if offline)
            retrieved_memories: List[dict] = []
            q_client = None
            try:
                from app.qdrant_client import get_qdrant_client
                q_client = get_qdrant_client()
                retrieved_memories = search_memories(
                    client=q_client,
                    player_id=current_user.player_id,
                    npc_id=chat_data.npc_id,
                    query_vector=query_vector,
                    top_k=5,
                )
            except Exception as exc:
                logger.warning("Qdrant unavailable for memory retrieval: %s", exc)
                retrieved_memories = []

            # 4. Build system prompt and context incorporating persona and state
            system_prompt, context = build_prompt(
                npc=npc,
                game_state=game_state,
                memories=retrieved_memories,
                player_message=chat_data.message,
            )

            # 5. Generate LLM response (Google Gemini or deterministic Mock)
            npc_reply = generate_response(
                system_prompt=system_prompt,
                user_message=chat_data.message,
                context=context,
            )

            # 6. Calculate heuristic affinity delta and update relationship in DB
            affinity_delta = _compute_affinity_delta(chat_data.message)
            new_affinity = await update_relationship(
                conn=conn,
                player_id=current_user.player_id,
                npc_id=chat_data.npc_id,
                affinity_delta=affinity_delta,
            )
            game_state["relationship"]["affinity_score"] = new_affinity
            game_state["relationship"]["interaction_count"] += 1

        # 7. Store both player query and NPC reply into Qdrant as persistent memories
        now = time.time()
        player_mem_id = str(uuid.uuid4())
        npc_mem_id = str(uuid.uuid4())

        player_vector = query_vector
        npc_vector = embed_text(npc_reply)

        if q_client is not None:
            try:
                from qdrant_client.http import models as qmodels
                points_to_upsert = [
                    qmodels.PointStruct(
                        id=player_mem_id,
                        vector=player_vector,
                        payload={
                            "player_id": current_user.player_id,
                            "npc_id": chat_data.npc_id,
                            "session_id": f"session_{current_user.player_id}_{chat_data.npc_id}",
                            "text": chat_data.message,
                            "content": chat_data.message,
                            "role": "player",
                            "importance": 0.5,
                            "timestamp": now,
                        },
                    ),
                    qmodels.PointStruct(
                        id=npc_mem_id,
                        vector=npc_vector,
                        payload={
                            "player_id": current_user.player_id,
                            "npc_id": chat_data.npc_id,
                            "session_id": f"session_{current_user.player_id}_{chat_data.npc_id}",
                            "text": npc_reply,
                            "content": npc_reply,
                            "role": "npc",
                            "importance": 0.6,
                            "timestamp": now + 0.001,
                        },
                    ),
                ]
                q_client.upsert(
                    collection_name=settings.qdrant_collection,
                    points=points_to_upsert,
                )
            except Exception as exc:
                logger.warning("Qdrant upsert failed (non-fatal): %s", exc)

        memories_used_response = [
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
            for m in retrieved_memories
        ]

        return ChatResponse(
            reply=npc_reply,
            npc_name=npc["name"],
            memories_used=memories_used_response,
            game_state=game_state,
            affinity_change=affinity_delta,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Chat endpoint error: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat processing error: {str(exc)}",
        )
