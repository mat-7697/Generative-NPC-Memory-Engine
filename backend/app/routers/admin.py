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


class SQLPlaygroundRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=5000, description="SQL query to execute")


def _sanitize_cell(val: Any) -> Any:
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
    """Execute arbitrary SQL queries for live viva demonstration, returning column headers, formatted rows, and exact execution timing."""
    raw_query = payload.query.strip().rstrip(";")
    if not raw_query:
        raise HTTPException(status_code=400, detail="SQL query string cannot be empty")

    start_time = time.perf_counter()
    try:
        # Check if the query returns rows (SELECT, WITH, EXPLAIN)
        first_word = raw_query.split()[0].upper()
        if first_word in ("SELECT", "WITH", "EXPLAIN", "SHOW", "TABLE"):
            rows = await conn.fetch(raw_query)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            if rows:
                columns = list(rows[0].keys())
                formatted_rows = [
                    {col: _sanitize_cell(row[col]) for col in columns}
                    for row in rows
                ]
            else:
                columns = []
                formatted_rows = []

            return {
                "success": True,
                "command": first_word,
                "execution_time_ms": duration_ms,
                "row_count": len(formatted_rows),
                "columns": columns,
                "rows": formatted_rows[:200],
            }
        else:
            # DML or DDL: execute within transaction
            status_result = await conn.execute(raw_query)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "success": True,
                "command": first_word,
                "status": status_result,
                "execution_time_ms": duration_ms,
                "row_count": 0,
                "columns": [],
                "rows": [],
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
    """Run EXPLAIN (ANALYZE, BUFFERS, VERBOSE, COSTS, FORMAT JSON) to benchmark query plans, index efficiency, and execution cost."""
    raw_query = payload.query.strip().rstrip(";")
    if not raw_query:
        raise HTTPException(status_code=400, detail="Query string cannot be empty")

    try:
        # 1. Fetch JSON execution plan
        explain_json_query = f"EXPLAIN (ANALYZE, BUFFERS, VERBOSE, COSTS, FORMAT JSON) {raw_query}"
        row = await conn.fetchrow(explain_json_query)
        plan_json = json.loads(row[0]) if row else []

        # 2. Fetch Text execution plan for visual tree view
        explain_text_query = f"EXPLAIN (ANALYZE, BUFFERS, VERBOSE, COSTS) {raw_query}"
        text_rows = await conn.fetch(explain_text_query)
        text_plan = "\n".join(r[0] for r in text_rows)

        summary = {}
        if plan_json and isinstance(plan_json, list) and len(plan_json) > 0:
            top_node = plan_json[0]
            summary["planning_time_ms"] = top_node.get("Planning Time")
            summary["execution_time_ms"] = top_node.get("Execution Time")
            plan_root = top_node.get("Plan", {})
            summary["node_type"] = plan_root.get("Node Type")
            summary["total_cost"] = plan_root.get("Total Cost")
            summary["actual_rows"] = plan_root.get("Actual Rows")
            summary["shared_hit_blocks"] = plan_root.get("Shared Hit Blocks", 0)
            summary["shared_read_blocks"] = plan_root.get("Shared Read Blocks", 0)

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


@router.get("/query-presets")
async def get_query_presets():
    """Curated viva and evaluation queries covering Joins, Aggregations, Window Functions, CTEs, GIN Search, and Triggers."""
    return [
        {
            "name": "1. Multi-Table JOIN with Wealth Aggregation",
            "category": "JOINs & GROUP BY",
            "description": "Calculates total player wealth by joining players with player_inventory and items table with GROUP BY and SUM.",
            "query": """SELECT 
    p.player_id,
    p.username,
    p.level,
    p.gold,
    COUNT(pi.item_id) AS total_inventory_slots,
    COALESCE(SUM(pi.quantity * i.base_price), 0) AS inventory_net_worth,
    p.gold + COALESCE(SUM(pi.quantity * i.base_price), 0) AS total_player_wealth
FROM players p
LEFT JOIN player_inventory pi ON p.player_id = pi.player_id
LEFT JOIN items i ON pi.item_id = i.item_id
GROUP BY p.player_id, p.username, p.level, p.gold
ORDER BY total_player_wealth DESC;""",
        },
        {
            "name": "2. Window Ranking: DENSE_RANK() Leaderboard",
            "category": "Window Functions",
            "description": "Computes peer leaderboard ranks using DENSE_RANK() over level, XP, and gold without collapse.",
            "query": """SELECT 
    player_id,
    username,
    level,
    xp,
    gold,
    DENSE_RANK() OVER (ORDER BY level DESC, xp DESC) AS level_rank,
    DENSE_RANK() OVER (ORDER BY gold DESC) AS wealth_rank
FROM players
ORDER BY level_rank ASC;""",
        },
        {
            "name": "3. Recursive CTE: Quest Prerequisite DAG Traversal",
            "category": "Recursive CTE",
            "description": "Traverses the hierarchical directed acyclic graph (DAG) of quest prerequisites from end boss backwards.",
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
        {
            "name": "4. GIN Index Full-Text Search on Items",
            "category": "Full-Text & GIN Index",
            "description": "Demonstrates tsvector @@ to_tsquery pattern matching utilizing PostgreSQL GIN index vs unindexed LIKE.",
            "query": """SELECT 
    item_id,
    name,
    item_type,
    rarity,
    base_price,
    description
FROM items
WHERE to_tsvector('english', name || ' ' || COALESCE(description, '')) @@ to_tsquery('english', 'elixir | blade | potion | crystal')
ORDER BY base_price DESC;""",
        },
        {
            "name": "5. Subquery with HAVING: Active Adventurers",
            "category": "Subquery & HAVING",
            "description": "Filters players actively pursuing at least 1 quest using aggregate HAVING condition.",
            "query": """SELECT 
    p.player_id,
    p.username,
    p.level,
    COUNT(pq.quest_id) AS active_quest_count
FROM players p
JOIN player_quests pq ON p.player_id = pq.player_id
WHERE pq.status = 'active'
GROUP BY p.player_id, p.username, p.level
HAVING COUNT(pq.quest_id) >= 1
ORDER BY active_quest_count DESC;""",
        },
        {
            "name": "6. CDC Audit Log: Trigger Verification",
            "category": "Triggers & Auditing",
            "description": "Inspects Change Data Capture (CDC) entries logged automatically by database audit triggers.",
            "query": """SELECT 
    audit_id,
    table_name,
    operation,
    player_id,
    old_data,
    new_data,
    changed_at
FROM audit_log
ORDER BY changed_at DESC
LIMIT 10;""",
        },
    ]
