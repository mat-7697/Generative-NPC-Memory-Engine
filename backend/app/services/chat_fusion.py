import json
import logging
import math
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Tuple
from uuid import UUID
import asyncpg
from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.config import get_settings

logger = logging.getLogger(__name__)


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable types to serializable equivalents."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    return obj


async def load_game_state(
    conn: asyncpg.Connection, player_id: int, npc_id: int
) -> Dict[str, Any]:
    """Load player progression, inventory, active quests, and NPC relationship."""
    # 1. Player base stats
    player_row = await conn.fetchrow(
        "SELECT player_id, username, level, xp, gold, role FROM players WHERE player_id = $1",
        player_id,
    )
    player_dict = _sanitize_for_json(dict(player_row)) if player_row else {}

    # 2. Player inventory items
    inv_rows = await conn.fetch(
        """
        SELECT pi.item_id, i.name, i.item_type, i.rarity, i.base_price, pi.quantity
        FROM player_inventory pi
        JOIN items i ON pi.item_id = i.item_id
        WHERE pi.player_id = $1 AND pi.quantity > 0
        ORDER BY i.name ASC
        """,
        player_id,
    )
    inventory = [_sanitize_for_json(dict(row)) for row in inv_rows]

    # 3. Active and Completed quests
    quest_rows = await conn.fetch(
        """
        SELECT q.quest_id, q.title, q.description, q.reward_gold, q.reward_xp, pq.status, pq.started_at,
               q.challenge_type, q.challenge_question, q.challenge_hint
        FROM player_quests pq
        JOIN quests q ON pq.quest_id = q.quest_id
        WHERE pq.player_id = $1 AND pq.status = 'active'
        ORDER BY pq.started_at ASC
        """,
        player_id,
    )
    active_quests = [_sanitize_for_json(dict(row)) for row in quest_rows]

    completed_rows = await conn.fetch(
        """
        SELECT q.quest_id, q.title, pq.completed_at
        FROM player_quests pq
        JOIN quests q ON pq.quest_id = q.quest_id
        WHERE pq.player_id = $1 AND pq.status = 'completed'
        ORDER BY pq.completed_at DESC
        LIMIT 5
        """,
        player_id,
    )
    completed_quests = [_sanitize_for_json(dict(row)) for row in completed_rows]

    # 4. NPC Details
    npc_row = await conn.fetchrow(
        "SELECT npc_id, name, persona, location, personality_traits, greeting FROM npcs WHERE npc_id = $1",
        npc_id,
    )
    npc_dict = _sanitize_for_json(dict(npc_row)) if npc_row else {}
    if npc_dict and isinstance(npc_dict.get("personality_traits"), str):
        try:
            npc_dict["personality_traits"] = json.loads(npc_dict["personality_traits"])
        except Exception:
            pass

    # 5. Relationship with this NPC
    rel_row = await conn.fetchrow(
        """
        SELECT affinity_score, interaction_count, last_interaction
        FROM npc_relationships
        WHERE player_id = $1 AND npc_id = $2
        """,
        player_id,
        npc_id,
    )
    if rel_row:
        relationship = {
            "affinity_score": float(rel_row["affinity_score"]),
            "interaction_count": rel_row["interaction_count"],
            "last_interaction": (
                rel_row["last_interaction"].isoformat()
                if rel_row["last_interaction"]
                else None
            ),
        }
    else:
        relationship = {
            "affinity_score": 0.0,
            "interaction_count": 0,
            "last_interaction": None,
        }

    return {
        "player": player_dict,
        "inventory": inventory,
        "active_quests": active_quests,
        "completed_quests": completed_quests,
        "npc": npc_dict,
        "relationship": relationship,
    }


def search_memories(
    client: QdrantClient,
    player_id: int,
    npc_id: int,
    query_vector: List[float],
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Query Qdrant for past dialogue memories filtered by player and NPC, ranked by cosine similarity and recency."""
    settings = get_settings()
    collection_name = settings.qdrant_collection

    query_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="player_id", match=models.MatchValue(value=player_id)
            ),
            models.FieldCondition(
                key="npc_id", match=models.MatchValue(value=npc_id)
            ),
        ]
    )

    try:
        search_hits = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=top_k * 2,
        )
    except Exception as exc:
        logger.warning("Error searching Qdrant collection '%s': %s", collection_name, exc)
        return []

    now = time.time()
    scored_memories = []

    for hit in search_hits:
        payload = hit.payload or {}
        mem_ts = float(payload.get("timestamp", now))
        # Recency decay scoring: 1.0 for new, decaying smoothly over time (half-life ~ 48 hours)
        age_hours = max(0.0, (now - mem_ts) / 3600.0)
        recency_score = math.exp(-0.015 * age_hours)
        vector_score = float(hit.score)

        # Prompt specification: final_score = vector_score * 0.7 + recency_score * 0.3
        final_score = round((vector_score * 0.7) + (recency_score * 0.3), 4)

        text_content = payload.get("text") or payload.get("content") or ""

        scored_memories.append(
            {
                "id": str(hit.id),
                "player_id": int(payload.get("player_id", player_id)),
                "npc_id": int(payload.get("npc_id", npc_id)),
                "text": text_content,
                "role": payload.get("role", "player"),
                "importance": float(payload.get("importance", 0.5)),
                "timestamp": mem_ts,
                "score": final_score,
            }
        )

    # Sort descending by recency-weighted final_score
    scored_memories.sort(key=lambda m: m["score"], reverse=True)
    return scored_memories[:top_k]


def get_recent_dialogue(
    client: QdrantClient, player_id: int, npc_id: int, max_messages: int = 10
) -> List[Dict[str, Any]]:
    """Return the most recent dialogue lines between this player and NPC, oldest first.

    Semantic search finds *relevant* memories; this supplies the *recent* back-and-forth
    so the NPC can follow the conversation and avoid repeating itself.
    """
    settings = get_settings()
    scroll_filter = models.Filter(
        must=[
            models.FieldCondition(key="player_id", match=models.MatchValue(value=player_id)),
            models.FieldCondition(key="npc_id", match=models.MatchValue(value=npc_id)),
        ]
    )
    try:
        records, _ = client.scroll(
            collection_name=settings.qdrant_collection,
            scroll_filter=scroll_filter,
            limit=500,
            with_payload=True,
            with_vectors=False,
        )
    except Exception as exc:
        logger.warning("Could not load recent dialogue from Qdrant: %s", exc)
        return []

    lines = []
    for rec in records:
        payload = rec.payload or {}
        text = (payload.get("text") or payload.get("content") or "").strip()
        if not text:
            continue
        lines.append({
            "id": str(rec.id),
            "role": "npc" if payload.get("role") == "npc" else "player",
            "text": text,
            "timestamp": float(payload.get("timestamp", 0.0)),
        })
    lines.sort(key=lambda m: m["timestamp"])
    return lines[-max_messages:]


def _attitude_guidance(affinity: float) -> str:
    if affinity >= 50.0:
        return "You trust this person deeply: be warm, open, share secrets and favours freely."
    if affinity >= 15.0:
        return "You like this person: be friendly and a little more forthcoming than with strangers."
    if affinity <= -50.0:
        return "You despise this person: be cold, curt and unhelpful, though never break character."
    if affinity <= -15.0:
        return "You're wary of this person: be guarded, short and slow to share anything useful."
    return "You don't know this person well yet: be civil but reserved, true to your nature."


def build_prompt(
    npc: Dict[str, Any],
    game_state: Dict[str, Any],
    memories: List[Dict[str, Any]],
    player_message: str,
) -> Tuple[str, str]:
    """Synthesize structured system persona and dynamic game state context for the LLM."""
    npc_name = npc.get("name", "NPC")
    persona = npc.get("persona", "A friendly citizen of the realm.")
    location = npc.get("location", "the town square")
    traits = npc.get("personality_traits", {})

    traits_desc = ", ".join(f"{k}: {v}" for k, v in traits.items()) if isinstance(traits, dict) and traits else "adaptable"
    affinity = float(game_state.get("relationship", {}).get("affinity_score", 0.0) or 0.0)

    system_prompt = (
        f"You are {npc_name}, a living character in a fantasy world, currently at {location}.\n"
        f"Who you are: {persona}\n"
        f"Personality traits: {traits_desc}\n"
        f"Attitude toward the player: {_attitude_guidance(affinity)}\n\n"
        "How to talk:\n"
        "- Respond to exactly what the player just said. React to it first (feelings, opinions, a "
        "question back) before adding anything new. Never answer with a generic speech.\n"
        "- Sound like a real person with your own voice, quirks and opinions - not a narrator or quest-giver.\n"
        "- Vary how you open every reply. Never reuse a catchphrase, sound effect or opening you have "
        "already used earlier in this conversation (e.g. don't start each reply with the same '*action*').\n"
        "- If the player tells you their name, call them by it from then on. If they share something "
        "personal (a fear, a goal, a loss), remember it and treat it with the emotion your character would.\n"
        "- Ask the player a question now and then to keep the conversation going.\n"
        "- Mention the player's items, quests or past memories only when it naturally fits - don't list them.\n"
        "- If the player asks about an active quest, challenge or secret (smuggler ciphers, blast furnace "
        "ratios, cellar dire rats...), give helpful in-character clues.\n"
        "- If asked about things that don't exist in your world (phones, the internet, real countries), "
        "react with in-character confusion rather than breaking character.\n"
        "- Speak only as yourself, in plain dialogue. No prefixes like your name or 'NPC:'."
    )

    # Build Context
    player = game_state.get("player", {})
    username = player.get("username", "Adventurer")
    level = player.get("level", 1)
    gold = player.get("gold", 0)

    inventory = game_state.get("inventory", [])
    if inventory:
        inv_summary = ", ".join(f"{i['name']} (x{i['quantity']})" for i in inventory[:6])
    else:
        inv_summary = "Empty pouches"

    active_quests = game_state.get("active_quests", [])
    if active_quests:
        quest_details = []
        for q in active_quests[:3]:
            q_str = f"'{q['title']}'"
            if q.get("challenge_type"):
                q_str += f" [Challenge: {q['challenge_type']}]"
            if q.get("challenge_question"):
                q_str += f" - Task: {q['challenge_question']}"
            quest_details.append(q_str)
        quest_summary = " | ".join(quest_details)
    else:
        quest_summary = "None (No quests currently underway)"

    completed_quests = game_state.get("completed_quests", [])
    if completed_quests:
        completed_summary = ", ".join(f"'{cq['title']}'" for cq in completed_quests[:4])
    else:
        completed_summary = "None yet"

    rel = game_state.get("relationship", {})
    affinity = rel.get("affinity_score", 0.0)
    interactions = rel.get("interaction_count", 0)

    if affinity >= 50.0:
        attitude = "Revered / Trusted Friend"
    elif affinity >= 15.0:
        attitude = "Friendly"
    elif affinity <= -50.0:
        attitude = "Hostile / Despised"
    elif affinity <= -15.0:
        attitude = "Suspicious"
    else:
        attitude = "Neutral"

    context_lines = [
        f"Player Character: {username} (account name; prefer any name they introduce themselves with) "
        f"(Level: {level}, Gold: {gold})",
        f"Player Inventory: {inv_summary}",
        f"Active Quests & Objectives: {quest_summary}",
        f"Completed Quests: {completed_summary}",
        f"Relationship: Affinity {affinity:+.1f} ({attitude}), Interactions: {interactions}",
    ]

    if memories:
        context_lines.append("\nRecalled Memories from Past Encounters:")
        for m in memories:
            role_label = "Player" if m.get("role") == "player" else npc_name
            context_lines.append(f"- [{role_label}]: {m.get('text', '')}")

    context = "\n".join(context_lines)
    return system_prompt, context


async def update_relationship(
    conn: asyncpg.Connection, player_id: int, npc_id: int, affinity_delta: float
) -> float:
    """Atomic upsert of player-NPC relationship affinity and interaction counter."""
    row = await conn.fetchrow(
        """
        INSERT INTO npc_relationships (player_id, npc_id, affinity_score, interaction_count, last_interaction)
        VALUES ($1, $2, GREATEST(-100.0, LEAST(100.0, $3::decimal)), 1, NOW())
        ON CONFLICT (player_id, npc_id)
        DO UPDATE SET
            affinity_score = GREATEST(-100.0, LEAST(100.0, npc_relationships.affinity_score + $3::decimal)),
            interaction_count = npc_relationships.interaction_count + 1,
            last_interaction = NOW()
        RETURNING affinity_score
        """,
        player_id,
        npc_id,
        affinity_delta,
    )
    return float(row["affinity_score"]) if row else 0.0
