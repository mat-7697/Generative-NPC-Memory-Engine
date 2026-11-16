import json
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from qdrant_client.http import models
from app.auth.dependencies import require_admin
from app.config import get_settings
from app.database import get_db
from app.models.auth import TokenData
from app.models.inventory import ItemResponse
from app.models.player import PlayerResponse
from app.models.quest import QuestCreate, QuestResponse, QuestUpdate
from app.qdrant_client import get_qdrant_client
from app.routers.sql_safety import (
    check_multiple_statements,
    format_plan_tree,
    inspect_sql_statement,
    redact_sensitive_columns,
    strip_sql_comments,
)

router = APIRouter(tags=["Administration"], dependencies=[Depends(require_admin)])


class AdminPlayerUpdate(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = Field(None, pattern="^(player|admin)$")
    gold: Optional[int] = Field(None, ge=0)
    level: Optional[int] = Field(None, ge=1)
    xp: Optional[int] = Field(None, ge=0)


class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    base_price: int = Field(..., gt=0)
    item_type: str = Field("misc", pattern="^(weapon|armor|potion|misc|quest_item)$")
    rarity: str = Field("common", pattern="^(common|uncommon|rare|epic|legendary)$")
    stock: int = Field(-1)


class ItemUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    base_price: Optional[int] = Field(None, gt=0)
    item_type: Optional[str] = Field(None, pattern="^(weapon|armor|potion|misc|quest_item)$")
    rarity: Optional[str] = Field(None, pattern="^(common|uncommon|rare|epic|legendary)$")
    stock: Optional[int] = None


@router.get("/players", response_model=List[PlayerResponse])
async def list_all_players(conn: asyncpg.Connection = Depends(get_db)):
    """List all player profiles in the database."""
    rows = await conn.fetch(
        """
        SELECT player_id, username, email, role, gold, level, xp, created_at
        FROM players
        ORDER BY player_id ASC
        """
    )
    return [PlayerResponse(**dict(r)) for r in rows]


@router.put("/players/{player_id}", response_model=PlayerResponse)
async def update_player(
    player_id: int,
    update_data: AdminPlayerUpdate,
    conn: asyncpg.Connection = Depends(get_db),
):
    """Administratively update any player's attributes, role, or balances."""
    fields = []
    values = []
    idx = 1

    if update_data.email is not None:
        fields.append(f"email = ${idx}")
        values.append(update_data.email)
        idx += 1

    if update_data.role is not None:
        fields.append(f"role = ${idx}")
        values.append(update_data.role)
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
        row = await conn.fetchrow(
            "SELECT player_id, username, email, role, gold, level, xp, created_at FROM players WHERE player_id = $1",
            player_id,
        )
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
        return PlayerResponse(**dict(row))

    values.append(player_id)
    query = f"""
        UPDATE players
        SET {', '.join(fields)}
        WHERE player_id = ${idx}
        RETURNING player_id, username, email, role, gold, level, xp, created_at
    """
    row = await conn.fetchrow(query, *values)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    return PlayerResponse(**dict(row))


@router.delete("/players/{player_id}")
async def delete_player(
    player_id: int,
    conn: asyncpg.Connection = Depends(get_db),
):
    """Delete a player account, cascading relational rows and purging Qdrant vector memories."""
    res = await conn.execute("DELETE FROM players WHERE player_id = $1", player_id)
    if res == "DELETE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Player with ID {player_id} not found",
        )

    # Purge vector memories from Qdrant
    settings = get_settings()
    try:
        q_client = get_qdrant_client()
        q_client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[models.FieldCondition(key="player_id", match=models.MatchValue(value=player_id))]
                )
            ),
        )
    except Exception:
        pass

    return {"detail": f"Player #{player_id} and associated vector memories purged successfully"}


@router.get("/audit-log")
async def get_audit_log(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Retrieve paginated mutation audit logs recorded by schema triggers."""
    rows = await conn.fetch(
        """
        SELECT log_id, table_name, operation, row_id, old_data, new_data, changed_by, changed_at
        FROM audit_log
        ORDER BY changed_at DESC
        LIMIT $1 OFFSET $2
        """,
        limit,
        offset,
    )
    result = []
    for r in rows:
        d = dict(r)
        for key in ("old_data", "new_data"):
            if isinstance(d[key], str):
                try:
                    d[key] = json.loads(d[key])
                except Exception:
                    pass
        result.append(d)
    return result


@router.get("/stats")
async def get_dashboard_stats(conn: asyncpg.Connection = Depends(get_db)):
    """Retrieve operational metrics summarizing total registered entities and transactions."""
    row = await conn.fetchrow(
        """
        SELECT 
            (SELECT COUNT(*) FROM players)::INT AS total_players,
            (SELECT COUNT(*) FROM npcs)::INT AS total_npcs,
            (SELECT COUNT(*) FROM items)::INT AS total_items,
            (SELECT COUNT(*) FROM quests)::INT AS total_quests,
            (SELECT COUNT(*) FROM inventory_transactions)::INT AS total_transactions
        """
    )
    return dict(row)


@router.post("/items", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    item_data: ItemCreate,
    conn: asyncpg.Connection = Depends(get_db),
):
    """Add a new item to the merchant catalog."""
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO items (name, description, base_price, item_type, rarity, stock)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING item_id, name, description, base_price, item_type, rarity, stock
            """,
            item_data.name,
            item_data.description,
            item_data.base_price,
            item_data.item_type,
            item_data.rarity,
            item_data.stock,
        )
    except asyncpg.exceptions.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Item with name '{item_data.name}' already exists",
        )
    return ItemResponse(**dict(row))


@router.put("/items/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: int,
    item_data: ItemUpdate,
    conn: asyncpg.Connection = Depends(get_db),
):
    """Update catalog item attributes."""
    fields = []
    values = []
    idx = 1

    if item_data.name is not None:
        fields.append(f"name = ${idx}")
        values.append(item_data.name)
        idx += 1

    if item_data.description is not None:
        fields.append(f"description = ${idx}")
        values.append(item_data.description)
        idx += 1

    if item_data.base_price is not None:
        fields.append(f"base_price = ${idx}")
        values.append(item_data.base_price)
        idx += 1

    if item_data.item_type is not None:
        fields.append(f"item_type = ${idx}")
        values.append(item_data.item_type)
        idx += 1

    if item_data.rarity is not None:
        fields.append(f"rarity = ${idx}")
        values.append(item_data.rarity)
        idx += 1

    if item_data.stock is not None:
        fields.append(f"stock = ${idx}")
        values.append(item_data.stock)
        idx += 1

    if not fields:
        row = await conn.fetchrow(
            "SELECT item_id, name, description, base_price, item_type, rarity, stock FROM items WHERE item_id = $1",
            item_id,
        )
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        return ItemResponse(**dict(row))

    values.append(item_id)
    query = f"""
        UPDATE items
        SET {', '.join(fields)}
        WHERE item_id = ${idx}
        RETURNING item_id, name, description, base_price, item_type, rarity, stock
    """
    row = await conn.fetchrow(query, *values)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return ItemResponse(**dict(row))


@router.delete("/items/{item_id}")
async def delete_item(
    item_id: int,
    conn: asyncpg.Connection = Depends(get_db),
):
    """Delete an item from catalog."""
    res = await conn.execute("DELETE FROM items WHERE item_id = $1", item_id)
    if res == "DELETE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with ID {item_id} not found",
        )
    return {"detail": f"Item #{item_id} deleted successfully"}


@router.post("/quests", response_model=QuestResponse, status_code=status.HTTP_201_CREATED)
async def create_quest(
    quest_data: QuestCreate,
    conn: asyncpg.Connection = Depends(get_db),
):
    """Create a new quest in the game graph."""
    row = await conn.fetchrow(
        """
        INSERT INTO quests (title, description, reward_gold, reward_xp, reward_item_id, min_level, quest_type)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING quest_id, title, description, reward_gold, reward_xp, reward_item_id, min_level, quest_type
        """,
        quest_data.title,
        quest_data.description,
        quest_data.reward_gold or 0,
        quest_data.reward_xp or 0,
        quest_data.reward_item_id,
        quest_data.min_level or 1,
        quest_data.quest_type or "main",
    )
    return QuestResponse(**dict(row))


@router.put("/quests/{quest_id}", response_model=QuestResponse)
async def update_quest(
    quest_id: int,
    quest_data: QuestUpdate,
    conn: asyncpg.Connection = Depends(get_db),
):
    """Update quest details and rewards."""
    fields = []
    values = []
    idx = 1

    if quest_data.title is not None:
        fields.append(f"title = ${idx}")
        values.append(quest_data.title)
        idx += 1

    if quest_data.description is not None:
        fields.append(f"description = ${idx}")
        values.append(quest_data.description)
        idx += 1

    if quest_data.reward_gold is not None:
        fields.append(f"reward_gold = ${idx}")
        values.append(quest_data.reward_gold)
        idx += 1

    if quest_data.reward_xp is not None:
        fields.append(f"reward_xp = ${idx}")
        values.append(quest_data.reward_xp)
        idx += 1

    if quest_data.reward_item_id is not None:
        fields.append(f"reward_item_id = ${idx}")
        values.append(quest_data.reward_item_id)
        idx += 1

    if quest_data.min_level is not None:
        fields.append(f"min_level = ${idx}")
        values.append(quest_data.min_level)
        idx += 1

    if quest_data.quest_type is not None:
        fields.append(f"quest_type = ${idx}")
        values.append(quest_data.quest_type)
        idx += 1

    if not fields:
        row = await conn.fetchrow(
            "SELECT quest_id, title, description, reward_gold, reward_xp, reward_item_id, min_level, quest_type FROM quests WHERE quest_id = $1",
            quest_id,
        )
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found")
        return QuestResponse(**dict(row))

    values.append(quest_id)
    query = f"""
        UPDATE quests
        SET {', '.join(fields)}
        WHERE quest_id = ${idx}
        RETURNING quest_id, title, description, reward_gold, reward_xp, reward_item_id, min_level, quest_type
    """
    row = await conn.fetchrow(query, *values)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found")
    return QuestResponse(**dict(row))


@router.delete("/quests/{quest_id}")
async def delete_quest(
    quest_id: int,
    conn: asyncpg.Connection = Depends(get_db),
):
    """Delete a quest from the catalog."""
    res = await conn.execute("DELETE FROM quests WHERE quest_id = $1", quest_id)
    if res == "DELETE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quest with ID {quest_id} not found",
        )
    return {"detail": f"Quest #{quest_id} deleted successfully"}


@router.get("/npc-popularity")
async def get_npc_popularity(conn: asyncpg.Connection = Depends(get_db)):
    """Retrieve the npc_popularity view calculating interaction volume and sentiment metrics."""
    rows = await conn.fetch(
        """
        SELECT 
            npc_id,
            npc_name,
            location,
            total_unique_players,
            total_interaction_count,
            avg_affinity_score,
            popularity_rank
        FROM npc_popularity
        ORDER BY popularity_rank ASC
        """
    )
    return [dict(r) for r in rows]


@router.get("/quest-progress")
async def get_quest_progress(
    player_id: Optional[int] = Query(None, description="Filter quest progress for a specific player"),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Retrieve quest_progress view matrix cross-joining players and quests with recursive prerequisite evaluation."""
    if player_id is not None:
        rows = await conn.fetch(
            """
            SELECT 
                player_id,
                username,
                player_level,
                quest_id,
                quest_title,
                quest_type,
                min_level,
                status,
                reward_gold,
                reward_xp,
                reward_item_id,
                reward_item_name,
                prerequisites_met,
                started_at,
                completed_at
            FROM quest_progress
            WHERE player_id = $1
            ORDER BY min_level ASC, quest_id ASC
            """,
            player_id,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT 
                player_id,
                username,
                player_level,
                quest_id,
                quest_title,
                quest_type,
                min_level,
                status,
                reward_gold,
                reward_xp,
                reward_item_id,
                reward_item_name,
                prerequisites_met,
                started_at,
                completed_at
            FROM quest_progress
            ORDER BY player_id ASC, min_level ASC
            LIMIT 200
            """
        )
    return [dict(r) for r in rows]


# ==============================================================================
# SQL WORKBENCH - SAFE PARSING, DUAL MODES & SINGLE-RUN EXPLAIN ANALYZE
# ==============================================================================


class SQLPlaygroundRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000, description="SQL query to execute")
    mode: str = Field("read_only", pattern="^(read_only|dml)$", description="Execution mode: read_only or dml")
    confirm_commit: bool = Field(False, description="Require explicit confirmation before committing DML changes")


class _RollbackPreviewException(Exception):
    """Internal signal to roll back a DML transaction after previewing affected rows."""

    def __init__(self, row_count: int, columns: List[str], rows: List[Dict[str, Any]]):
        self.row_count = row_count
        self.columns = columns
        self.rows = rows


def _parse_affected_rows(status_str: str) -> int:
    """Extract affected row count from PostgreSQL command tags (e.g. 'UPDATE 3', 'INSERT 0 1')."""
    if not status_str:
        return 0
    parts = status_str.split()
    try:
        return int(parts[-1])
    except (ValueError, IndexError):
        return 0


def _sanitize_cell(val: Any) -> Any:
    """Format and serialize PostgreSQL data types for clean JSON rendering."""
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, UUID):
        return str(val)
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, dict):
        return {k: _sanitize_cell(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_sanitize_cell(v) for v in val]
    return val


@router.post("/sql-playground")
async def execute_sql_playground(
    payload: SQLPlaygroundRequest,
    conn: asyncpg.Connection = Depends(get_db),
):
    """Interactive PostgreSQL SQL Workbench with read-only transaction safeguards,

    DML preview/rollback, execution timing, and secrets redaction.
    """
    clean_query = strip_sql_comments(payload.query).strip().rstrip(";")
    if not clean_query:
        raise HTTPException(status_code=400, detail="SQL query string cannot be empty")

    # Safeguard 1: Disallow multiple statements in a single execution request
    if check_multiple_statements(clean_query):
        raise HTTPException(
            status_code=400,
            detail="Multiple SQL statements in a single request are prohibited for safety and transactional integrity.",
        )

    # Safeguard 2: Statement classification
    info = inspect_sql_statement(clean_query)
    if not info["valid"]:
        raise HTTPException(status_code=400, detail=info.get("error", "Invalid SQL statement"))

    # Safeguard 3: Restrict destructive DDL (DROP, TRUNCATE, ALTER on live database)
    if info.get("is_ddl"):
        raise HTTPException(
            status_code=400,
            detail=f"Destructive DDL operations ({info.get('first_keyword')}) are restricted on the live database. Use dedicated schema reset scripts (db/reset.sql) instead.",
        )

    start_time = time.perf_counter()

    try:
        # ----------------------------------------------------------------------
        # MODE 1: READ-ONLY MODE (Default)
        # ----------------------------------------------------------------------
        if payload.mode == "read_only":
            if info.get("is_dml") or info.get("has_mutation"):
                raise HTTPException(
                    status_code=400,
                    detail="Data mutations (INSERT, UPDATE, DELETE) are restricted in Read-Only Mode. Switch to 'DML Demonstration Mode' in the workbench toolbar.",
                )

            # Enforce read-only at PostgreSQL transaction engine level
            async with conn.transaction(readonly=True):
                await conn.execute("SET LOCAL statement_timeout = '5000ms'")
                rows = await conn.fetch(clean_query)

            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            if rows:
                columns = list(rows[0].keys())
                formatted_rows = [
                    {col: _sanitize_cell(row[col]) for col in columns}
                    for row in rows
                ]
                # Redact sensitive credentials (e.g. password_hash)
                formatted_rows = redact_sensitive_columns(columns, formatted_rows)
            else:
                columns = []
                formatted_rows = []

            return {
                "success": True,
                "mode": "read_only",
                "command": info.get("first_keyword", "SELECT"),
                "execution_time_ms": duration_ms,
                "row_count": len(formatted_rows),
                "columns": columns,
                "rows": formatted_rows[:500],
            }

        # ----------------------------------------------------------------------
        # MODE 2: DML DEMONSTRATION MODE (Preview/Rollback vs Explicit Commit)
        # ----------------------------------------------------------------------
        else:
            if not (info.get("is_dml") or info.get("has_mutation")):
                # If user ran a SELECT query in DML mode, execute it safely
                async with conn.transaction(readonly=True):
                    await conn.execute("SET LOCAL statement_timeout = '5000ms'")
                    rows = await conn.fetch(clean_query)
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                columns = list(rows[0].keys()) if rows else []
                formatted_rows = [
                    {col: _sanitize_cell(row[col]) for col in columns}
                    for row in rows
                ]
                formatted_rows = redact_sensitive_columns(columns, formatted_rows)
                return {
                    "success": True,
                    "mode": "dml",
                    "command": info.get("first_keyword", "SELECT"),
                    "execution_time_ms": duration_ms,
                    "row_count": len(formatted_rows),
                    "columns": columns,
                    "rows": formatted_rows[:500],
                }

            # If user hasn't explicitly confirmed commit: ROLLBACK PREVIEW MODE
            if not payload.confirm_commit:
                try:
                    async with conn.transaction():
                        await conn.execute("SET LOCAL statement_timeout = '5000ms'")
                        if "RETURNING" in clean_query.upper():
                            rows = await conn.fetch(clean_query)
                            row_count = len(rows)
                            columns = list(rows[0].keys()) if rows else []
                            formatted_rows = [
                                {col: _sanitize_cell(row[col]) for col in columns}
                                for row in rows
                            ]
                            formatted_rows = redact_sensitive_columns(columns, formatted_rows)
                        else:
                            status_res = await conn.execute(clean_query)
                            row_count = _parse_affected_rows(status_res)
                            columns = []
                            formatted_rows = []
                        raise _RollbackPreviewException(row_count, columns, formatted_rows)
                except _RollbackPreviewException as exc:
                    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    return {
                        "success": True,
                        "mode": "dml",
                        "command": info.get("first_keyword", "DML"),
                        "rolled_back": True,
                        "committed": False,
                        "transaction_status": "ROLLED_BACK (PREVIEW)",
                        "status": "ROLLBACK_PREVIEW",
                        "message": f"DML executed in preview mode and safely rolled back ({exc.row_count} rows affected). No permanent changes were written to PostgreSQL.",
                        "execution_time_ms": duration_ms,
                        "affected_rows": exc.row_count,
                        "row_count": exc.row_count,
                        "columns": exc.columns,
                        "rows": exc.rows[:500],
                    }

            # Explicit Confirmation Given: COMMIT MODE
            async with conn.transaction():
                await conn.execute("SET LOCAL statement_timeout = '5000ms'")
                if "RETURNING" in clean_query.upper():
                    rows = await conn.fetch(clean_query)
                    row_count = len(rows)
                    columns = list(rows[0].keys()) if rows else []
                    formatted_rows = [
                        {col: _sanitize_cell(row[col]) for col in columns}
                        for row in rows
                    ]
                    formatted_rows = redact_sensitive_columns(columns, formatted_rows)
                else:
                    status_res = await conn.execute(clean_query)
                    row_count = _parse_affected_rows(status_res)
                    columns = []
                    formatted_rows = []

            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "success": True,
                "mode": "dml",
                "command": info.get("first_keyword", "DML"),
                "committed": True,
                "rolled_back": False,
                "transaction_status": "COMMITTED",
                "status": "COMMITTED",
                "message": f"DML transaction committed successfully ({row_count} rows affected).",
                "execution_time_ms": duration_ms,
                "affected_rows": row_count,
                "row_count": row_count,
                "columns": columns,
                "rows": formatted_rows[:500],
            }

    except asyncpg.PostgresError as err:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "success": False,
            "error": str(err),
            "pg_code": getattr(err, "sqlstate", None),
            "execution_time_ms": duration_ms,
            "columns": [],
            "rows": [],
        }


@router.post("/explain-analyze")
async def explain_analyze_query(
    payload: SQLPlaygroundRequest,
    conn: asyncpg.Connection = Depends(get_db),
):
    """Run EXPLAIN (ANALYZE, BUFFERS, VERBOSE, COSTS, FORMAT JSON) executing the query

    EXACTLY ONCE and synthesizing both detailed performance metrics and visual tree structure.
    Restricted to read-only statements.
    """
    clean_query = strip_sql_comments(payload.query).strip().rstrip(";")
    if not clean_query:
        raise HTTPException(status_code=400, detail="Query string cannot be empty")

    if check_multiple_statements(clean_query):
        raise HTTPException(status_code=400, detail="Multiple SQL statements are not permitted in EXPLAIN ANALYZE.")

    info = inspect_sql_statement(clean_query)
    if info.get("has_mutation") or info.get("is_dml") or info.get("is_ddl"):
        raise HTTPException(
            status_code=400,
            detail="EXPLAIN ANALYZE is restricted to read-only queries (SELECT) to prevent unintended execution side-effects.",
        )

    try:
        # Run EXPLAIN ANALYZE exactly once with JSON format and buffers
        explain_json_query = f"EXPLAIN (ANALYZE, BUFFERS, VERBOSE, COSTS, FORMAT JSON) {clean_query}"
        async with conn.transaction(readonly=True):
            await conn.execute("SET LOCAL statement_timeout = '5000ms'")
            row = await conn.fetchrow(explain_json_query)

        plan_json = json.loads(row[0]) if row else []
        summary = {}
        text_plan = ""

        if plan_json and isinstance(plan_json, list) and len(plan_json) > 0:
            top_node = plan_json[0]
            summary["planning_time_ms"] = top_node.get("Planning Time")
            summary["execution_time_ms"] = top_node.get("Execution Time")
            plan_root = top_node.get("Plan", {})
            summary["node_type"] = plan_root.get("Node Type")
            summary["total_cost"] = plan_root.get("Total Cost")
            summary["actual_rows"] = plan_root.get("Actual Rows")
            summary["plan_rows"] = plan_root.get("Plan Rows")
            summary["shared_hit_blocks"] = plan_root.get("Shared Hit Blocks", 0)
            summary["shared_read_blocks"] = plan_root.get("Shared Read Blocks", 0)
            summary["relation_name"] = plan_root.get("Relation Name")
            summary["index_name"] = plan_root.get("Index Name")

            # Format the visual execution plan tree from the JSON node hierarchy
            tree_lines = format_plan_tree(plan_root)
            tree_lines.append(f"Planning Time: {summary['planning_time_ms']} ms")
            tree_lines.append(f"Execution Time: {summary['execution_time_ms']} ms")
            text_plan = "\n".join(tree_lines)

        return {
            "success": True,
            "summary": summary,
            "text_plan": text_plan,
            "json_plan": plan_json,
        }
    except asyncpg.PostgresError as err:
        return {
            "success": False,
            "error": str(err),
            "pg_code": getattr(err, "sqlstate", None),
        }


@router.get("/db-explorer")
async def get_database_explorer(conn: asyncpg.Connection = Depends(get_db)):
    """Dynamically introspect database metadata: tables, columns, primary keys,

    foreign keys, views, and stored functions/procedures.
    """
    # 1. Fetch tables and column details
    table_rows = await conn.fetch(
        """
        SELECT 
            c.table_name,
            c.column_name,
            c.data_type,
            c.is_nullable,
            c.column_default,
            c.ordinal_position,
            CASE WHEN pk.column_name IS NOT NULL THEN TRUE ELSE FALSE END AS is_primary_key,
            fk.foreign_table_name,
            fk.foreign_column_name
        FROM information_schema.columns c
        JOIN information_schema.tables t 
            ON c.table_name = t.table_name AND c.table_schema = t.table_schema
        LEFT JOIN (
            SELECT kcu.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = 'public'
        ) pk ON c.table_name = pk.table_name AND c.column_name = pk.column_name
        LEFT JOIN (
            SELECT 
                kcu.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
        ) fk ON c.table_name = fk.table_name AND c.column_name = fk.column_name
        WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE'
        ORDER BY c.table_name ASC, c.ordinal_position ASC;
        """
    )

    tables_map: Dict[str, List[Dict[str, Any]]] = {}
    for r in table_rows:
        t_name = r["table_name"]
        if t_name not in tables_map:
            tables_map[t_name] = []
        tables_map[t_name].append(
            {
                "name": r["column_name"],
                "type": r["data_type"],
                "nullable": r["is_nullable"] == "YES",
                "default": r["column_default"],
                "is_primary_key": r["is_primary_key"],
                "foreign_key": (
                    {"table": r["foreign_table_name"], "column": r["foreign_column_name"]}
                    if r["foreign_table_name"]
                    else None
                ),
            }
        )

    tables = [{"name": name, "columns": cols} for name, cols in tables_map.items()]

    # 2. Fetch views
    view_rows = await conn.fetch(
        """
        SELECT table_name AS view_name, view_definition
        FROM information_schema.views
        WHERE table_schema = 'public'
        ORDER BY table_name ASC;
        """
    )
    views = [{"name": r["view_name"], "definition": r["view_definition"]} for r in view_rows]

    # 3. Fetch stored functions and procedures
    routine_rows = await conn.fetch(
        """
        SELECT 
            routine_name,
            routine_type,
            data_type AS return_type
        FROM information_schema.routines
        WHERE routine_schema = 'public'
        ORDER BY routine_name ASC;
        """
    )
    routines = [
        {
            "name": r["routine_name"],
            "type": r["routine_type"],
            "return_type": r["return_type"],
        }
        for r in routine_rows
    ]

    return {
        "tables": tables,
        "views": views,
        "routines": routines,
    }


@router.get("/query-presets")
async def get_query_presets():
    """Curated viva and DBMS syllabus query presets covering all 12 evaluation categories."""
    return [
        # 1. Basic SQL
        {
            "name": "1. Player Wealth Filter & Sort",
            "category": "Basic SQL",
            "description": "Demonstrates SELECT, WHERE filter on numeric values, and ORDER BY with LIMIT.",
            "query": """SELECT player_id, username, level, gold, xp
FROM players
WHERE gold >= 100
ORDER BY gold DESC, level DESC
LIMIT 5;""",
        },
        {
            "name": "2. Distinct Rarity & Item Type Catalog",
            "category": "Basic SQL",
            "description": "Demonstrates SELECT DISTINCT to eliminate duplicate category tuples.",
            "query": """SELECT DISTINCT item_type, rarity
FROM items
ORDER BY item_type, rarity;""",
        },
        {
            "name": "3. Price Range & Set Membership (BETWEEN & IN)",
            "category": "Basic SQL",
            "description": "Demonstrates BETWEEN range matching and IN set inclusion operator.",
            "query": """SELECT name, item_type, rarity, base_price, stock
FROM items
WHERE base_price BETWEEN 40 AND 500
  AND item_type IN ('weapon', 'armor', 'potion')
ORDER BY base_price ASC;""",
        },
        {
            "name": "4. Wildcard Substring Pattern (LIKE)",
            "category": "Basic SQL",
            "description": "Demonstrates pattern matching using SQL LIKE with wildcard character %.",
            "query": """SELECT quest_id, title, min_level, reward_gold, reward_xp
FROM quests
WHERE title LIKE '%Secret%' OR description LIKE '%cellar%'
ORDER BY min_level ASC;""",
        },

        # 2. Joins
        {
            "name": "5. Multi-Table Valuation JOIN",
            "category": "Joins",
            "description": "3-table INNER JOIN across players, player_inventory, and items computing valuations.",
            "query": """SELECT 
    p.player_id,
    p.username,
    i.name AS item_name,
    i.rarity,
    pi.quantity,
    i.base_price AS unit_price,
    (pi.quantity * i.base_price) AS line_item_value
FROM players p
JOIN player_inventory pi ON p.player_id = pi.player_id
JOIN items i ON pi.item_id = i.item_id
ORDER BY line_item_value DESC;""",
        },
        {
            "name": "6. Outer LEFT JOIN with COALESCE",
            "category": "Joins",
            "description": "LEFT JOIN preserving unmatched starter quests, resolving prerequisite titles.",
            "query": """SELECT 
    q.quest_id,
    q.title AS quest_title,
    q.min_level,
    qp.required_quest_id,
    COALESCE(rq.title, 'None (Starter Quest)') AS prerequisite_title
FROM quests q
LEFT JOIN quest_prerequisites qp ON q.quest_id = qp.quest_id
LEFT JOIN quests rq ON qp.required_quest_id = rq.quest_id
ORDER BY q.quest_id ASC;""",
        },
        {
            "name": "7. RIGHT JOIN: Unowned Item Inventory Gaps",
            "category": "Joins",
            "description": "RIGHT JOIN identifying catalog items not currently possessed by any player.",
            "query": """SELECT 
    i.item_id,
    i.name AS catalog_item,
    i.rarity,
    i.base_price,
    pi.player_id,
    pi.quantity
FROM player_inventory pi
RIGHT JOIN items i ON pi.item_id = i.item_id
WHERE pi.player_id IS NULL
ORDER BY i.base_price DESC;""",
        },
        {
            "name": "8. FULL OUTER JOIN: Players & Quest Statuses",
            "category": "Joins",
            "description": "FULL OUTER JOIN retaining non-participating players and unattempted quests.",
            "query": """SELECT 
    p.username,
    COALESCE(pq.status, 'unassigned') AS player_status,
    q.title AS quest_title
FROM players p
FULL OUTER JOIN player_quests pq ON p.player_id = pq.player_id
FULL OUTER JOIN quests q ON pq.quest_id = q.quest_id
LIMIT 20;""",
        },
        {
            "name": "9. Self Join: Prerequisite Dependency Pairs",
            "category": "Joins",
            "description": "Self-join on quests table to link each quest directly to its requirement title.",
            "query": """SELECT 
    q.quest_id,
    q.title AS quest_title,
    req.quest_id AS prerequisite_id,
    req.title AS prerequisite_title
FROM quests q
JOIN quest_prerequisites qp ON q.quest_id = qp.quest_id
JOIN quests req ON qp.required_quest_id = req.quest_id
ORDER BY q.quest_id ASC;""",
        },

        # 3. Aggregations
        {
            "name": "10. GROUP BY + HAVING: Active Traders",
            "category": "Aggregations",
            "description": "Groups player items, filtering players holding 2+ distinct types using HAVING.",
            "query": """SELECT 
    p.player_id,
    p.username,
    COUNT(pi.item_id) AS distinct_item_types,
    SUM(pi.quantity) AS total_item_units,
    SUM(pi.quantity * i.base_price) AS aggregate_valuation
FROM players p
JOIN player_inventory pi ON p.player_id = pi.player_id
JOIN items i ON pi.item_id = i.item_id
GROUP BY p.player_id, p.username
HAVING COUNT(pi.item_id) >= 2
ORDER BY aggregate_valuation DESC;""",
        },
        {
            "name": "11. Category Statistics: Price & Stock Summary",
            "category": "Aggregations",
            "description": "Computes COUNT, MIN, MAX, AVG price, and total stock per item category.",
            "query": """SELECT 
    item_type,
    COUNT(*) AS total_items,
    MIN(base_price) AS minimum_price,
    ROUND(AVG(base_price), 2) AS average_price,
    MAX(base_price) AS maximum_price,
    SUM(CASE WHEN stock > 0 THEN stock ELSE 0 END) AS tracked_inventory_units
FROM items
GROUP BY item_type
ORDER BY average_price DESC;""",
        },

        # 4. Subqueries
        {
            "name": "12. Non-Correlated Subquery: Above Average Items",
            "category": "Subqueries",
            "description": "Subquery inside WHERE comparing individual item prices against catalog average.",
            "query": """SELECT item_id, name, item_type, rarity, base_price
FROM items
WHERE base_price > (SELECT AVG(base_price) FROM items)
ORDER BY base_price DESC;""",
        },
        {
            "name": "13. Correlated Subquery: Wealthiest at Level",
            "category": "Subqueries",
            "description": "Correlated subquery evaluating if a player has more gold than the average of their level peers.",
            "query": """SELECT p.player_id, p.username, p.level, p.gold
FROM players p
WHERE p.gold >= (
    SELECT COALESCE(AVG(p2.gold), 0)
    FROM players p2
    WHERE p2.level = p.level
)
ORDER BY p.level DESC;""",
        },
        {
            "name": "14. EXISTS Subquery: Completed Quest Players",
            "category": "Subqueries",
            "description": "EXISTS condition testing for presence of completed player_quests records.",
            "query": """SELECT p.player_id, p.username, p.level, p.gold
FROM players p
WHERE EXISTS (
    SELECT 1
    FROM player_quests pq
    WHERE pq.player_id = p.player_id AND pq.status = 'completed'
)
ORDER BY p.player_id ASC;""",
        },
        {
            "name": "15. Set Operators: UNION, INTERSECT, EXCEPT",
            "category": "Subqueries",
            "description": "Demonstrates set difference (EXCEPT) between Quest 1 completions and Quest 4 starts.",
            "query": """SELECT player_id, 'Completed Quest 1' AS reason
FROM player_quests
WHERE quest_id = 1 AND status = 'completed'
EXCEPT
SELECT player_id, 'Completed Quest 1' AS reason
FROM player_quests
WHERE quest_id = 4;""",
        },

        # 5. CTE and Recursive CTE
        {
            "name": "16. Common Table Expression (CTE): Net Worth",
            "category": "CTE and Recursive CTE",
            "description": "Encapsulates player wealth calculation in a clean WITH clause before final selection.",
            "query": """WITH player_wealth AS (
    SELECT 
        p.player_id,
        p.username,
        p.gold,
        COALESCE(SUM(pi.quantity * i.base_price), 0) AS inventory_worth
    FROM players p
    LEFT JOIN player_inventory pi ON p.player_id = pi.player_id
    LEFT JOIN items i ON pi.item_id = i.item_id
    GROUP BY p.player_id, p.username, p.gold
)
SELECT player_id, username, gold, inventory_worth, (gold + inventory_worth) AS total_player_wealth
FROM player_wealth
ORDER BY total_player_wealth DESC;""",
        },
        {
            "name": "17. WITH RECURSIVE: Prerequisite DAG Hierarchy",
            "category": "CTE and Recursive CTE",
            "description": "Recursive graph traversal walking the quest prerequisite chain backwards from Quest #8.",
            "query": """WITH RECURSIVE quest_prereq_chain AS (
    SELECT 
        quest_id,
        title,
        min_level,
        0 AS depth,
        title::text AS traversal_path
    FROM quests
    WHERE quest_id = 8
    UNION ALL
    SELECT 
        q.quest_id,
        q.title,
        q.min_level,
        c.depth + 1,
        c.traversal_path || ' -> ' || q.title
    FROM quest_prerequisites qp
    JOIN quest_prereq_chain c ON qp.quest_id = c.quest_id
    JOIN quests q ON qp.required_quest_id = q.quest_id
)
SELECT depth, quest_id, title, min_level, traversal_path
FROM quest_prereq_chain
ORDER BY depth ASC;""",
        },

        # 6. Window Functions
        {
            "name": "18. DENSE_RANK, RANK, & ROW_NUMBER Leaderboard",
            "category": "Window Functions",
            "description": "Demonstrates window ranking functions side-by-side without collapsing rows.",
            "query": """SELECT 
    player_id,
    username,
    level,
    xp,
    gold,
    ROW_NUMBER() OVER (ORDER BY level DESC, xp DESC) AS row_num,
    RANK() OVER (ORDER BY level DESC) AS level_rank,
    DENSE_RANK() OVER (ORDER BY level DESC) AS dense_level_rank,
    DENSE_RANK() OVER (ORDER BY gold DESC) AS wealth_rank
FROM players
ORDER BY row_num ASC;""",
        },
        {
            "name": "19. Running Total & Partitioned Wealth",
            "category": "Window Functions",
            "description": "Cumulative running balance using SUM() OVER (PARTITION BY ... ORDER BY ...).",
            "query": """SELECT 
    transaction_id,
    player_id,
    transaction_type,
    quantity,
    gold_amount,
    created_at,
    SUM(gold_amount) OVER (
        PARTITION BY player_id
        ORDER BY created_at ASC
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_gold_volume
FROM inventory_transactions
ORDER BY player_id ASC, created_at ASC;""",
        },

        # 7. Views
        {
            "name": "20. Query player_leaderboard View",
            "category": "Views",
            "description": "Queries relational view aggregating completed quests, total items, and DENSE_RANK standings.",
            "query": """SELECT leaderboard_rank, username, level, xp, gold, quest_completion_count, total_items_owned
FROM player_leaderboard
ORDER BY leaderboard_rank ASC;""",
        },
        {
            "name": "21. Query npc_popularity Sentiment View",
            "category": "Views",
            "description": "Queries relational view calculating interaction frequencies, average affinity, and ranks.",
            "query": """SELECT popularity_rank, npc_name, location, total_unique_players, total_interaction_count, avg_affinity_score
FROM npc_popularity
ORDER BY popularity_rank ASC;""",
        },
        {
            "name": "22. Query quest_progress Cross-Matrix View",
            "category": "Views",
            "description": "Queries view evaluating transitive prerequisites and eligibility via can_start_quest().",
            "query": """SELECT username, player_level, quest_title, min_level, status, reward_gold, reward_xp, prerequisites_met
FROM quest_progress
WHERE player_id = 2
ORDER BY min_level ASC;""",
        },

        # 8. Stored Procedures
        {
            "name": "23. Call can_start_quest() Function",
            "category": "Stored Procedures",
            "description": "Executes stored PL/pgSQL function checking level gate and all prerequisite quests.",
            "query": """SELECT 
    p.username,
    q.title AS quest_title,
    q.min_level,
    can_start_quest(p.player_id, q.quest_id) AS is_eligible
FROM players p
CROSS JOIN quests q
WHERE p.player_id = 2 AND q.quest_id IN (1, 4, 8)
ORDER BY q.quest_id ASC;""",
        },
        {
            "name": "24. ACID Procedure: buy_item Demonstration",
            "category": "Stored Procedures",
            "description": "Invokes ACID stored procedure buy_item with row locks, solvency validation, and audit entry.",
            "query": """CALL buy_item(2, 5, 1);""",
        },

        # 9. Triggers
        {
            "name": "25. Change Data Capture (CDC) Audit Trigger Log",
            "category": "Triggers",
            "description": "Inspects entries recorded automatically by triggers on player_inventory and players.",
            "query": """SELECT log_id, table_name, operation, row_id, old_data, new_data, changed_by, changed_at
FROM audit_log
ORDER BY changed_at DESC
LIMIT 10;""",
        },
        {
            "name": "26. Invariant Trigger: Negative Gold Blocker",
            "category": "Triggers",
            "description": "Demonstrates fn_block_negative_gold trigger aborting transaction on negative balance.",
            "query": """UPDATE players SET gold = -50 WHERE player_id = 2;""",
        },

        # 10. Indexing and Query Optimization
        {
            "name": "27. EXPLAIN ANALYZE on Foreign Key B-Tree",
            "category": "Indexing and Query Optimization",
            "description": "Benchmarks execution plan, index scan vs seq scan, buffer hits, and optimizer costs.",
            "query": """SELECT * FROM player_inventory WHERE player_id = 2;""",
        },
        {
            "name": "28. EXPLAIN ANALYZE on GIN Full-Text Search",
            "category": "Indexing and Query Optimization",
            "description": "Benchmarks GIN index lookup on tsvector column compared against unindexed LIKE scanning.",
            "query": """SELECT item_id, name, base_price, description
FROM items
WHERE search_vector @@ to_tsquery('english', 'sword | blade');""",
        },

        # 11. Full-Text Search
        {
            "name": "29. GIN tsvector @@ to_tsquery with ts_rank",
            "category": "Full-Text Search",
            "description": "Matches items matching English linguistic stems and ranks by relevance score.",
            "query": """SELECT 
    item_id,
    name,
    item_type,
    rarity,
    base_price,
    ts_rank(search_vector, to_tsquery('english', 'elixir | potion | draught')) AS relevance_rank
FROM items
WHERE search_vector @@ to_tsquery('english', 'elixir | potion | draught')
ORDER BY relevance_rank DESC, base_price ASC;""",
        },

        # 12. DML Operations
        {
            "name": "30. Controlled DML: INSERT with RETURNING",
            "category": "DML Operations",
            "description": "Inserts a new catalog item. In DML Preview Mode, changes are safely previewed and rolled back.",
            "query": """INSERT INTO items (name, description, base_price, item_type, rarity, stock)
VALUES ('Astral Sextant', 'Ancient navigation instrument tuned to ley-line harmonics.', 420, 'misc', 'rare', 3)
RETURNING item_id, name, base_price, rarity, stock;""",
        },
        {
            "name": "31. Controlled DML: UPDATE with RETURNING",
            "category": "DML Operations",
            "description": "Updates gold treasury balance. Previews affected rows in Preview Mode or commits on confirmation.",
            "query": """UPDATE players
SET gold = gold + 250
WHERE player_id = 2
RETURNING player_id, username, gold, updated_at;""",
        },
        {
            "name": "32. Controlled DML: DELETE with RETURNING",
            "category": "DML Operations",
            "description": "Removes a specific inventory entry and returns the deleted record.",
            "query": """DELETE FROM player_inventory
WHERE player_id = 1 AND item_id = 2
RETURNING inventory_id, player_id, item_id, quantity;""",
        },
    ]
