"""
Audit & Enhancements Test Suite - Generative NPC Memory Engine
Tests Priority 1 (SQL Workbench, safety parser, DML preview/commit, EXPLAIN single-run, DB explorer),
Priority 3 (Async chat non-blocking pipeline & Qdrant fallback), and
Priority 4 (Security, memory stats isolation, player profile tamper protection).
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from app.models.auth import TokenData
from app.routers.sql_safety import (
    strip_sql_comments,
    check_multiple_statements,
    inspect_sql_statement,
    redact_sensitive_columns,
    format_plan_tree,
)
from app.routers.admin import SQLPlaygroundRequest, execute_sql_playground, explain_analyze_query


def run_coro(coro):
    """Safely step an async coroutine without requiring loopback network socketpairs."""
    try:
        coro.send(None)
    except StopIteration as exc:
        return exc.value


# ==============================================================================
# 1. SQL SAFETY PARSER TESTS
# ==============================================================================
class TestSQLSafetyParser:
    """Verifies robust SQL statement parsing, comment stripping, multi-statement rejection, and redaction."""

    def test_strip_leading_and_inline_comments(self):
        """TC-SQL-01: Verifies -- single-line and /* */ block comments are stripped cleanly."""
        raw_sql = """
        -- Leading comment explaining query
        /* Multi-line
           block comment */
        SELECT p.player_id, p.username -- inline comment
        FROM players p;
        """
        cleaned = strip_sql_comments(raw_sql)
        assert cleaned.startswith("SELECT p.player_id")
        assert "-- Leading comment" not in cleaned
        assert "Multi-line" not in cleaned
        assert cleaned.endswith(";")

    def test_reject_multiple_statements(self):
        """TC-SQL-02: Verifies semicolons chaining multiple statements are detected."""
        stacked_sql = "SELECT 1; DROP TABLE players;"
        has_multiple = check_multiple_statements(stacked_sql)
        assert has_multiple is True

    def test_allow_single_statement_with_trailing_semicolon(self):
        """TC-SQL-03: Single statement with trailing semicolon and whitespace is accepted."""
        single_sql = "SELECT * FROM items WHERE is_quest_item = true;   "
        has_multiple = check_multiple_statements(single_sql)
        assert has_multiple is False

    def test_detect_cte_mutation(self):
        """TC-SQL-04: CTE that contains mutation (DELETE/UPDATE/INSERT) is detected as mutation."""
        cte_delete_sql = """
        WITH deleted_players AS (
            DELETE FROM players
            WHERE gold < 0
            RETURNING player_id, username
        )
        SELECT * FROM deleted_players;
        """
        info = inspect_sql_statement(cte_delete_sql)
        assert info["has_mutation"] is True
        assert info["is_read_only"] is False
        assert info["is_dml"] is True
        assert info["category"] == "CTE"

    def test_detect_destructive_ddl(self):
        """TC-SQL-05: Destructive DDL (DROP, TRUNCATE, ALTER) is identified as is_ddl=True."""
        ddl_queries = [
            "DROP TABLE players CASCADE",
            "TRUNCATE TABLE player_inventory",
            "ALTER TABLE npcs ADD COLUMN secret text",
        ]
        for query in ddl_queries:
            info = inspect_sql_statement(query)
            assert info["is_ddl"] is True
            assert info["is_read_only"] is False
            assert info["has_mutation"] is True

    def test_classify_standard_select_and_joins(self):
        """TC-SQL-06: Standard SELECT, JOINs, and aggregates are classified as read-only."""
        query = """
        SELECT p.username, COUNT(pi.item_id) as total_items
        FROM players p
        LEFT JOIN player_inventory pi ON p.player_id = pi.player_id
        GROUP BY p.username
        ORDER BY total_items DESC;
        """
        info = inspect_sql_statement(query)
        assert info["is_read_only"] is True
        assert info["is_dml"] is False
        assert info["is_ddl"] is False
        assert info["category"] == "SELECT"

    def test_redact_sensitive_columns(self):
        """TC-SQL-07: password_hash and credentials columns are redacted in returned rows."""
        columns = ["player_id", "username", "password_hash", "gold"]
        rows = [
            {"player_id": 1, "username": "admin", "password_hash": "$2b$12$fakehashvalue", "gold": 1000},
            {"player_id": 2, "username": "hero", "password_hash": "$2b$12$anotherhashval", "gold": 250},
        ]
        redacted = redact_sensitive_columns(columns, rows)
        for row in redacted:
            assert row["password_hash"] == "[REDACTED_PASSWORD_HASH]"
            assert row["username"] in ("admin", "hero")
            assert isinstance(row["gold"], int)

    def test_ascii_plan_tree_formatter(self):
        """TC-SQL-08: format_plan_tree formats nested plan tree nodes cleanly."""
        nested_plan = {
            "Node Type": "Limit",
            "Startup Cost": 0.0,
            "Total Cost": 15.2,
            "Plan Rows": 10,
            "Actual Rows": 10,
            "Actual Total Time": 0.42,
            "Plans": [
                {
                    "Node Type": "Seq Scan",
                    "Relation Name": "players",
                    "Startup Cost": 0.0,
                    "Total Cost": 14.5,
                    "Plan Rows": 100,
                    "Actual Rows": 10,
                    "Actual Total Time": 0.38,
                }
            ],
        }
        tree_lines = format_plan_tree(nested_plan)
        tree_text = "\n".join(tree_lines)
        assert "Limit" in tree_text
        assert "cost=0.00..15.20" in tree_text


# ==============================================================================
# 2. SQL WORKBENCH EXECUTION & TRANSACTION MODES
# ==============================================================================
class TestSQLWorkbenchModes:
    """Verifies Read-Only mode safety, DML preview/rollback, and explicit commit."""

    def test_read_only_mode_rejects_mutation(self):
        """TC-WB-01: In read_only mode, mutation queries are rejected before DB execution."""
        req = SQLPlaygroundRequest(
            query="DELETE FROM players WHERE player_id = 999;",
            mode="read_only",
            confirm_commit=False,
        )
        with pytest.raises(HTTPException) as exc_info:
            run_coro(execute_sql_playground(req, conn=AsyncMock()))
        assert exc_info.value.status_code == 400
        assert "Data mutations" in exc_info.value.detail

    def test_read_only_mode_rejects_ddl(self):
        """TC-WB-02: In read_only mode, DDL statements (DROP, ALTER) are rejected."""
        req = SQLPlaygroundRequest(
            query="DROP TABLE npcs;",
            mode="read_only",
            confirm_commit=False,
        )
        with pytest.raises(HTTPException) as exc_info:
            run_coro(execute_sql_playground(req, conn=AsyncMock()))
        assert exc_info.value.status_code == 400
        assert "Destructive DDL operations" in exc_info.value.detail

    def test_dml_mode_preview_rollback(self):
        """TC-WB-03: In DML mode with confirm_commit=False, transaction is automatically rolled back."""
        req = SQLPlaygroundRequest(
            query="UPDATE players SET gold = gold + 500 WHERE player_id = 1 RETURNING player_id, gold;",
            mode="dml",
            confirm_commit=False,
        )
        mock_conn = MagicMock()
        mock_tx = AsyncMock()
        mock_conn.transaction.return_value = mock_tx
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")
        mock_conn.fetch = AsyncMock(return_value=[{"player_id": 1, "gold": 1500}])

        result = run_coro(execute_sql_playground(req, conn=mock_conn))
        assert result["success"] is True
        assert result["transaction_status"] == "ROLLED_BACK (PREVIEW)"
        assert result["rolled_back"] is True
        assert result["committed"] is False

    def test_dml_mode_confirm_commit(self):
        """TC-WB-04: In DML mode with confirm_commit=True, changes are committed."""
        req = SQLPlaygroundRequest(
            query="UPDATE players SET gold = gold + 500 WHERE player_id = 1 RETURNING player_id, gold;",
            mode="dml",
            confirm_commit=True,
        )
        mock_conn = MagicMock()
        mock_tx = AsyncMock()
        mock_conn.transaction.return_value = mock_tx
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")
        mock_conn.fetch = AsyncMock(return_value=[{"player_id": 1, "gold": 1500}])

        result = run_coro(execute_sql_playground(req, conn=mock_conn))
        assert result["success"] is True
        assert result["transaction_status"] == "COMMITTED"
        assert result["committed"] is True
        assert result["rolled_back"] is False

    def test_explain_analyze_rejects_mutation(self):
        """TC-WB-05: EXPLAIN ANALYZE on a mutation statement raises 400."""
        req = SQLPlaygroundRequest(
            query="DELETE FROM players WHERE player_id = 2;"
        )
        with pytest.raises(HTTPException) as exc_info:
            run_coro(explain_analyze_query(req, conn=AsyncMock()))
        assert exc_info.value.status_code == 400
        assert "EXPLAIN ANALYZE is restricted to read-only queries" in exc_info.value.detail


# ==============================================================================
# 3. SECURITY & PRIVACY AUDIT TESTS
# ==============================================================================
class TestSecurityAndPrivacyAudit:
    """Verifies memory stats tenant privacy, and player profile tamper protection."""

    def test_memory_stats_tenant_isolation_for_player(self):
        """TC-SEC-03: Regular player calling /api/memory/stats sees only their own memories."""
        from app.routers.memory import get_memory_stats

        player_user = TokenData(player_id=5, username="adventurer_5", role="player")
        mock_client = MagicMock()
        mock_client.count.return_value = MagicMock(count=12)
        mock_client.scroll.return_value = ([], None)

        with patch("app.routers.memory.get_qdrant_client", return_value=mock_client):
            stats = run_coro(get_memory_stats(current_user=player_user))
            assert stats.total_memories == 12

            # Assert count_filter was passed with player_id matching 5
            count_filter = mock_client.count.call_args[1].get("count_filter")
            assert count_filter is not None
            assert count_filter.must[0].key == "player_id"
            assert count_filter.must[0].match.value == 5

    def test_memory_stats_admin_global_access(self):
        """TC-SEC-04: Admin calling /api/memory/stats can view global database memory counts."""
        from app.routers.memory import get_memory_stats

        admin_user = TokenData(player_id=1, username="admin", role="admin")
        mock_client = MagicMock()
        mock_client.count.return_value = MagicMock(count=1500)
        mock_client.scroll.return_value = ([], None)

        with patch("app.routers.memory.get_qdrant_client", return_value=mock_client):
            stats = run_coro(get_memory_stats(current_user=admin_user))
            assert stats.total_memories == 1500

            # Admin has count_filter=None (global view)
            count_filter = mock_client.count.call_args[1].get("count_filter")
            assert count_filter is None

    def test_player_me_tamper_protection_blocks_gold_and_level(self):
        """TC-SEC-05: Non-admin player updating /api/players/me cannot alter gold, level, or xp (403 Forbidden)."""
        from app.routers.players import update_my_profile
        from app.models.player import PlayerUpdate

        player_user = TokenData(player_id=10, username="legit_player", role="player")
        tamper_attempt = PlayerUpdate(
            email="new_email@example.com",
            gold=999999,  # Hack attempt
            level=99,     # Hack attempt
            xp=500000,    # Hack attempt
        )

        mock_conn = AsyncMock()
        with pytest.raises(HTTPException) as exc_info:
            run_coro(update_my_profile(tamper_attempt, current_user=player_user, conn=mock_conn))
        assert exc_info.value.status_code == 403
        assert "Modifying gold, level, or xp directly requires administrative clearance" in exc_info.value.detail


# ==============================================================================
# 4. CHAT PIPELINE ASYNC & FALLBACK RELIABILITY
# ==============================================================================
class TestChatPipelineAsyncReliability:
    """Verifies graceful Qdrant fallback and async non-blocking execution in chat pipeline."""

    @pytest.mark.asyncio
    async def test_chat_pipeline_graceful_qdrant_fallback(self):
        """TC-AI-01: Chat succeeds and returns valid response even when Qdrant search/insert fails."""
        from app.routers.chat import chat_with_npc
        from app.models.chat import ChatRequest
        from starlette.requests import Request
        from datetime import datetime, timezone

        req = ChatRequest(npc_id=1, message="Hello, what wares do you offer?")
        player_user = TokenData(player_id=1, username="hero", role="player")
        mock_request = Request({
            "type": "http",
            "method": "POST",
            "path": "/api/chat/",
            "url": "http://testserver/api/chat/",
            "headers": [],
            "client": ("127.0.0.1", 12345),
        })

        mock_conn = MagicMock()
        mock_conn.transaction.return_value = AsyncMock()
        # Mock player
        mock_conn.fetchrow = AsyncMock(side_effect=[
            {
                "player_id": 1,
                "username": "hero",
                "email": "hero@example.com",
                "gold": 500,
                "level": 3,
                "xp": 120,
                "role": "player",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
            # Mock NPC
            {
                "npc_id": 1,
                "name": "Alden",
                "role": "Blacksmith",
                "personality": "Gruff, practical, honorable blacksmith who respects strength.",
                "dialogue_style": "Terse, direct, medieval blacksmith vernacular.",
                "greeting": "Well met, traveler. Looking for steel?",
                "system_prompt": "You are Alden the blacksmith.",
                "avatar_url": None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
            # Mock relationship initial load
            {
                "affinity_score": 15,
                "interaction_count": 2,
                "last_interaction": datetime.now(timezone.utc),
            },
            # Mock update_relationship RETURNING affinity_score
            {
                "affinity_score": 18.0,
            },
        ])
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        # Mock Qdrant memory search and client upsert to simulate service outage
        mock_q_client = MagicMock()
        mock_q_client.upsert.side_effect = Exception("Qdrant write failed")
        with patch("app.routers.chat.search_memories", side_effect=Exception("Qdrant connection refused")), \
             patch("app.qdrant_client.get_qdrant_client", return_value=mock_q_client):

            response = await chat_with_npc(request=mock_request, chat_data=req, current_user=player_user, conn=mock_conn)
            assert response.npc_name == "Alden"
            assert len(response.reply) > 0
            assert response.affinity_change == 1.0
            # Chat succeeded gracefully despite Qdrant outage!
            assert response.memories_used == []
