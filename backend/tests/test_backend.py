import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.auth.utils import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)
from app.services.embedding import embed_text, embed_texts
from app.services.llm import generate_response
from app.services.chat_fusion import build_prompt
from app.routers.chat import _compute_affinity_delta


def run_coro(coro):
    """Safely step an async coroutine without requiring loopback network socketpairs."""
    try:
        coro.send(None)
    except StopIteration as exc:
        return exc.value


def test_root_endpoint():
    from app.main import root
    data = run_coro(root())
    assert data["status"] == "online"
    assert "/docs" in data["docs_url"]


def test_health_endpoint():
    from app.main import health_check
    data = run_coro(health_check())
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "database" in data


def test_openapi_contains_all_routers():
    schema = app.openapi()
    paths = schema["paths"]

    # Verify key endpoints from all 8 routers
    assert "/api/auth/register" in paths
    assert "/api/auth/login" in paths
    assert "/api/players/me" in paths
    assert "/api/players/leaderboard" in paths
    assert "/api/npcs/" in paths
    assert "/api/npcs/{npc_id}/relationship" in paths
    assert "/api/inventory/items" in paths
    assert "/api/inventory/buy" in paths
    assert "/api/inventory/my-inventory" in paths
    assert "/api/quests/" in paths
    assert "/api/quests/my-quests" in paths
    assert "/api/quests/{quest_id}/start" in paths
    assert "/api/memory/" in paths
    assert "/api/memory/search" in paths
    assert "/api/memory/stats" in paths
    assert "/api/chat/" in paths
    assert "/api/admin/players" in paths
    assert "/api/admin/audit-log" in paths
    assert "/api/admin/npc-popularity" in paths
    assert "/api/admin/quest-progress" in paths


def test_password_hashing():
    pw = "DragonSlayer42!"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_token_flow():
    payload = {"sub": "aldor_the_brave", "player_id": 99, "role": "admin"}
    token = create_access_token(payload)
    assert isinstance(token, str)

    decoded = decode_access_token(token)
    assert decoded.username == "aldor_the_brave"
    assert decoded.player_id == 99
    assert decoded.role == "admin"


def test_embedding_service():
    text1 = "I need to purchase an iron dagger"
    text2 = "I need to purchase an iron dagger"
    text3 = "The weather in the mountains is chilly"

    vec1 = embed_text(text1)
    vec2 = embed_text(text2)
    vec3 = embed_text(text3)

    assert len(vec1) == 384
    # Deterministic matching
    assert vec1 == vec2
    # Non-identical texts should not be equal
    assert vec1 != vec3

    batch_vecs = embed_texts([text1, text3])
    assert len(batch_vecs) == 2


def test_mock_llm_generation():
    prompt = "You are Thorin, the village blacksmith."
    msg = "Can you forge a new sword for me?"
    reply = generate_response(prompt, msg, context="Met at the forge earlier.")

    assert len(reply) > 10
    assert any(w in reply.lower() for w in ["blade", "steel", "forge", "anvil"])


def test_affinity_sentiment_heuristic():
    positive_delta = _compute_affinity_delta("Thank you kindly for your assistance, good friend!")
    negative_delta = _compute_affinity_delta("You stupid thief, get out of my way!")
    neutral_delta = _compute_affinity_delta("What is the time of day?")

    assert positive_delta > 0
    assert negative_delta < 0
    assert neutral_delta >= 0


def test_chat_prompt_synthesis():
    npc = {
        "name": "Elena",
        "persona": "Kind innkeeper at The Prancing Pony",
        "location": "Bree",
        "personality_traits": {"warmth": 0.9, "curiosity": 0.8},
    }
    game_state = {
        "player": {"username": "Frodo", "level": 2, "gold": 50},
        "inventory": [{"name": "Lembas Bread", "quantity": 3}],
        "active_quests": [{"title": "Deliver the Ring"}],
        "relationship": {"affinity_score": 25.0, "interaction_count": 3},
    }
    memories = [
        {"role": "player", "text": "I lost my pony on the road."},
    ]

    system_prompt, context = build_prompt(npc, game_state, memories, "Greetings Elena")

    assert "Elena" in system_prompt
    assert "innkeeper" in system_prompt
    assert "Frodo" in context
    assert "Lembas Bread" in context
    assert "Deliver the Ring" in context
    assert "I lost my pony" in context
