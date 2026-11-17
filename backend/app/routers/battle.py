"""Turn-based combat campaign: hunt monsters, use your gear, seal the Void Rift.

All combat is resolved server-side inside a transaction that row-locks the
player and the active battle (SELECT ... FOR UPDATE), so double-clicks or
parallel requests can never apply the same turn twice.

Stats:
    max HP  = 90 + 10 x level
    attack  = 4 + 2 x level + equipped weapon attack_power
    defense = level + equipped armor defense_power
"""

import random
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.auth import TokenData

router = APIRouter(tags=["Combat Campaign"])

CRIT_CHANCE = 0.10
CRIT_MULT = 1.75
MONSTER_MISS_CHANCE = 0.08
DEFEAT_GOLD_PENALTY = 0.10


class StartBattleRequest(BaseModel):
    monster_id: int = Field(..., gt=0)


class UseItemInBattleRequest(BaseModel):
    item_id: int = Field(..., gt=0)


def max_hp_for(level: int) -> int:
    return 90 + 10 * level


def rest_cost_for(level: int) -> int:
    return 10 + 2 * level


async def _player_stats(conn: asyncpg.Connection, player_id: int, lock: bool = False) -> Dict[str, Any]:
    row = await conn.fetchrow(
        f"SELECT player_id, level, xp, gold, hp FROM players WHERE player_id = $1 {'FOR UPDATE' if lock else ''}",
        player_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Player not found")
    gear = await conn.fetch(
        """
        SELECT i.item_id, i.name, i.item_type, i.attack_power, i.defense_power
        FROM player_inventory pi JOIN items i ON i.item_id = pi.item_id
        WHERE pi.player_id = $1 AND pi.is_equipped AND pi.quantity > 0
          AND i.item_type IN ('weapon', 'armor')
        """,
        player_id,
    )
    weapon = next((dict(g) for g in gear if g["item_type"] == "weapon"), None)
    armor = next((dict(g) for g in gear if g["item_type"] == "armor"), None)
    level = row["level"]
    max_hp = max_hp_for(level)
    return {
        "player_id": row["player_id"],
        "level": level,
        "xp": row["xp"],
        "gold": row["gold"],
        "hp": min(row["hp"], max_hp),
        "max_hp": max_hp,
        "attack": 4 + 2 * level + (weapon["attack_power"] if weapon else 0),
        "defense": level + (armor["defense_power"] if armor else 0),
        "weapon": weapon,
        "armor": armor,
    }


async def _owned_item_ids(conn: asyncpg.Connection, player_id: int) -> set:
    rows = await conn.fetch(
        "SELECT item_id FROM player_inventory WHERE player_id = $1 AND quantity > 0", player_id
    )
    return {r["item_id"] for r in rows}


async def _build_state(conn: asyncpg.Connection, player_id: int) -> Dict[str, Any]:
    player = await _player_stats(conn, player_id)
    owned = await _owned_item_ids(conn, player_id)

    monsters = await conn.fetch(
        """
        SELECT m.*, ri.name AS required_item_name, li.name AS loot_item_name,
               COALESCE(k.kills, 0) AS kills
        FROM monsters m
        LEFT JOIN items ri ON ri.item_id = m.required_item_id
        LEFT JOIN items li ON li.item_id = m.loot_item_id
        LEFT JOIN player_monster_kills k ON k.monster_id = m.monster_id AND k.player_id = $1
        ORDER BY m.monster_id
        """,
        player_id,
    )
    monster_list: List[Dict[str, Any]] = []
    for m in monsters:
        lock_reason: Optional[str] = None
        if player["level"] < m["min_level"]:
            lock_reason = f"Reach level {m['min_level']}"
        elif m["required_item_id"] and m["required_item_id"] not in owned:
            lock_reason = f"Requires {m['required_item_name']}"
        monster_list.append(
            {
                "monster_id": m["monster_id"],
                "name": m["name"],
                "region": m["region"],
                "description": m["description"],
                "icon": m["icon"],
                "min_level": m["min_level"],
                "max_hp": m["max_hp"],
                "attack": m["attack"],
                "defense": m["defense"],
                "gold_reward": m["gold_reward"],
                "xp_reward": m["xp_reward"],
                "loot_item_name": m["loot_item_name"],
                "loot_chance": float(m["loot_chance"]),
                "is_boss": m["is_boss"],
                "required_item_name": m["required_item_name"],
                "kills": m["kills"],
                "unlocked": lock_reason is None,
                "lock_reason": lock_reason,
            }
        )

    battle = await conn.fetchrow(
        "SELECT battle_id, monster_id, monster_hp, empowered, turns FROM battles WHERE player_id = $1 AND status = 'active'",
        player_id,
    )
    active = None
    if battle:
        mon = next(m for m in monster_list if m["monster_id"] == battle["monster_id"])
        active = {**dict(battle), "monster": mon}

    potions = await conn.fetch(
        """
        SELECT i.item_id, i.name, i.heal_amount, pi.quantity
        FROM player_inventory pi JOIN items i ON i.item_id = pi.item_id
        WHERE pi.player_id = $1 AND pi.quantity > 0 AND i.item_type = 'potion'
        ORDER BY i.heal_amount
        """,
        player_id,
    )
    boss_kills = sum(m["kills"] for m in monster_list if m["is_boss"])
    return {
        "player": player,
        "monsters": monster_list,
        "active_battle": active,
        "potions": [dict(p) for p in potions],
        "rest_cost": rest_cost_for(player["level"]),
        "rift_sealed": boss_kills > 0,
        "regions_cleared": sum(1 for m in monster_list if m["kills"] > 0),
    }


def _roll(base: float) -> int:
    return max(1, round(base * random.uniform(0.85, 1.15)))


async def _locked_active_battle(conn: asyncpg.Connection, player_id: int):
    battle = await conn.fetchrow(
        """
        SELECT b.battle_id, b.monster_hp, b.empowered, b.turns, m.*
        FROM battles b JOIN monsters m ON m.monster_id = b.monster_id
        WHERE b.player_id = $1 AND b.status = 'active'
        FOR UPDATE OF b
        """,
        player_id,
    )
    if not battle:
        raise HTTPException(status_code=400, detail="You are not in a battle. Choose a monster to hunt first.")
    return battle


async def _monster_turn(conn, player: Dict[str, Any], battle, log: List[str]) -> Dict[str, Any]:
    """Monster strikes back. Returns outcome dict; handles player defeat."""
    if random.random() < MONSTER_MISS_CHANCE:
        log.append(f"The {battle['name']} lunges at you but misses!")
        return {"defeated": False, "hp": player["hp"]}

    dmg = _roll(max(1, battle["attack"] - player["defense"]))
    new_hp = max(0, player["hp"] - dmg)
    log.append(f"The {battle['name']} hits you for {dmg} damage.")

    if new_hp > 0:
        await conn.execute("UPDATE players SET hp = $1 WHERE player_id = $2", new_hp, player["player_id"])
        return {"defeated": False, "hp": new_hp}

    # Defeat: lose 10% gold, wake up at the inn with a quarter of your health.
    penalty = int(player["gold"] * DEFEAT_GOLD_PENALTY)
    revive_hp = max(1, player["max_hp"] // 4)
    await conn.execute(
        "UPDATE players SET hp = $1, gold = gold - $2 WHERE player_id = $3",
        revive_hp, penalty, player["player_id"],
    )
    await conn.execute(
        "UPDATE battles SET status = 'lost', monster_hp = $1, ended_at = NOW() WHERE battle_id = $2",
        battle["monster_hp"], battle["battle_id"],
    )
    log.append(
        f"You collapse... Villagers carry you back to the Whispering Crow Inn. "
        f"You lost {penalty} gold and recover with {revive_hp} HP."
    )
    return {"defeated": True, "hp": revive_hp, "gold_lost": penalty}


async def _victory(conn, player: Dict[str, Any], battle, log: List[str]) -> Dict[str, Any]:
    await conn.execute(
        "UPDATE battles SET status = 'won', monster_hp = 0, ended_at = NOW() WHERE battle_id = $1",
        battle["battle_id"],
    )
    await conn.execute(
        "UPDATE players SET gold = gold + $1, xp = xp + $2 WHERE player_id = $3",
        battle["gold_reward"], battle["xp_reward"], player["player_id"],
    )
    await conn.execute(
        """
        INSERT INTO player_monster_kills (player_id, monster_id, kills) VALUES ($1, $2, 1)
        ON CONFLICT (player_id, monster_id) DO UPDATE SET kills = player_monster_kills.kills + 1
        """,
        player["player_id"], battle["monster_id"],
    )
    log.append(f"You defeated the {battle['name']}! +{battle['gold_reward']} gold, +{battle['xp_reward']} XP.")

    loot = None
    if battle["loot_item_id"] and random.random() < float(battle["loot_chance"]):
        loot = await conn.fetchval("SELECT name FROM items WHERE item_id = $1", battle["loot_item_id"])
        await conn.execute(
            """
            INSERT INTO player_inventory (player_id, item_id, quantity) VALUES ($1, $2, 1)
            ON CONFLICT (player_id, item_id) DO UPDATE SET quantity = player_inventory.quantity + 1
            """,
            player["player_id"], battle["loot_item_id"],
        )
        await conn.execute(
            """
            INSERT INTO inventory_transactions (player_id, item_id, transaction_type, quantity, gold_amount, description)
            VALUES ($1, $2, 'battle_loot', 1, $3, $4)
            """,
            player["player_id"], battle["loot_item_id"], battle["gold_reward"],
            f"Looted {loot} from a {battle['name']}",
        )
        log.append(f"Loot! The {battle['name']} dropped: {loot}.")

    if battle["is_boss"]:
        log.append("The Ashen Wyrm falls and the Void Rift collapses. The realm is saved!")

    old_level = player["level"]
    new_level = await conn.fetchval("SELECT level FROM players WHERE player_id = $1", player["player_id"])
    if new_level > old_level:
        # Level up: grow max HP and fully heal as a reward.
        await conn.execute(
            "UPDATE players SET hp = $1 WHERE player_id = $2", max_hp_for(new_level), player["player_id"]
        )
        log.append(f"LEVEL UP! You are now level {new_level}. Health fully restored.")

    return {"loot": loot, "leveled_up": new_level > old_level}


@router.get("/state")
async def get_state(
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Player combat stats, all hunting grounds (with lock reasons), active battle and potions."""
    return await _build_state(conn, current_user.player_id)


@router.post("/start")
async def start_battle(
    data: StartBattleRequest,
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    async with conn.transaction():
        player = await _player_stats(conn, current_user.player_id, lock=True)
        state = await _build_state(conn, current_user.player_id)
        if state["active_battle"]:
            raise HTTPException(status_code=400, detail="Finish your current battle first.")
        monster = next((m for m in state["monsters"] if m["monster_id"] == data.monster_id), None)
        if not monster:
            raise HTTPException(status_code=404, detail="Monster not found")
        if not monster["unlocked"]:
            raise HTTPException(status_code=400, detail=f"Locked: {monster['lock_reason']}.")
        if player["hp"] <= 1:
            raise HTTPException(status_code=400, detail="You are too wounded to fight. Drink a potion or rest at the inn.")
        await conn.execute(
            "INSERT INTO battles (player_id, monster_id, monster_hp) VALUES ($1, $2, $3)",
            current_user.player_id, data.monster_id, monster["max_hp"],
        )
    log = [f"You enter the {monster['region']}. A {monster['name']} blocks your path!"]
    return {"log": log, "outcome": "ongoing", "state": await _build_state(conn, current_user.player_id)}


@router.post("/attack")
async def attack(
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    log: List[str] = []
    outcome = "ongoing"
    async with conn.transaction():
        player = await _player_stats(conn, current_user.player_id, lock=True)
        battle = await _locked_active_battle(conn, current_user.player_id)

        base = max(1, player["attack"] - battle["defense"] / 2)
        dmg = _roll(base)
        crit = random.random() < CRIT_CHANCE
        if crit:
            dmg = round(dmg * CRIT_MULT)
        if battle["empowered"]:
            dmg *= 2
        weapon = player["weapon"]["name"] if player["weapon"] else "your fists"
        log.append(
            f"You strike with {weapon} for {dmg} damage"
            + (" (CRITICAL!)" if crit else "")
            + (" (empowered x2)" if battle["empowered"] else "")
            + "."
        )
        monster_hp = max(0, battle["monster_hp"] - dmg)
        await conn.execute(
            "UPDATE battles SET monster_hp = $1, empowered = FALSE, turns = turns + 1 WHERE battle_id = $2",
            monster_hp, battle["battle_id"],
        )
        battle = {**dict(battle), "monster_hp": monster_hp}

        if monster_hp == 0:
            await _victory(conn, player, battle, log)
            outcome = "won"
        else:
            res = await _monster_turn(conn, player, battle, log)
            if res["defeated"]:
                outcome = "lost"

    return {"log": log, "outcome": outcome, "state": await _build_state(conn, current_user.player_id)}


@router.post("/use-item")
async def use_item_in_battle(
    data: UseItemInBattleRequest,
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    log: List[str] = []
    outcome = "ongoing"
    async with conn.transaction():
        player = await _player_stats(conn, current_user.player_id, lock=True)
        battle = await _locked_active_battle(conn, current_user.player_id)
        item = await conn.fetchrow(
            """
            SELECT pi.inventory_id, pi.quantity, i.name, i.item_type, i.heal_amount
            FROM player_inventory pi JOIN items i ON i.item_id = pi.item_id
            WHERE pi.player_id = $1 AND pi.item_id = $2 AND pi.quantity > 0
            FOR UPDATE OF pi
            """,
            current_user.player_id, data.item_id,
        )
        if not item or item["item_type"] != "potion":
            raise HTTPException(status_code=400, detail="You don't have that potion.")

        await conn.execute(
            "UPDATE player_inventory SET quantity = quantity - 1 WHERE inventory_id = $1", item["inventory_id"]
        )
        await conn.execute(
            "DELETE FROM player_inventory WHERE inventory_id = $1 AND quantity <= 0", item["inventory_id"]
        )
        healed = min(item["heal_amount"], player["max_hp"] - player["hp"])
        player["hp"] += healed
        await conn.execute("UPDATE players SET hp = $1 WHERE player_id = $2", player["hp"], player["player_id"])
        await conn.execute(
            """
            INSERT INTO inventory_transactions (player_id, item_id, transaction_type, quantity, gold_amount, description)
            VALUES ($1, $2, 'consume_item', 1, 0, $3)
            """,
            current_user.player_id, data.item_id, f"Drank {item['name']} in battle (+{healed} HP)",
        )
        log.append(f"You drink a {item['name']} and recover {healed} HP.")

        empowered = item["name"] == "Mana Draught"
        if empowered:
            log.append("Arcane power surges through you: your next attack deals double damage!")
        await conn.execute(
            "UPDATE battles SET turns = turns + 1, empowered = empowered OR $1 WHERE battle_id = $2",
            empowered, battle["battle_id"],
        )

        res = await _monster_turn(conn, player, battle, log)
        if res["defeated"]:
            outcome = "lost"

    return {"log": log, "outcome": outcome, "state": await _build_state(conn, current_user.player_id)}


@router.post("/flee")
async def flee(
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    async with conn.transaction():
        await _player_stats(conn, current_user.player_id, lock=True)
        battle = await _locked_active_battle(conn, current_user.player_id)
        await conn.execute(
            "UPDATE battles SET status = 'fled', ended_at = NOW() WHERE battle_id = $1", battle["battle_id"]
        )
    log = [f"You escape from the {battle['name']}. Live to fight another day."]
    return {"log": log, "outcome": "fled", "state": await _build_state(conn, current_user.player_id)}


@router.post("/rest")
async def rest_at_inn(
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Pay Elara at the Whispering Crow Inn to fully restore your health."""
    async with conn.transaction():
        player = await _player_stats(conn, current_user.player_id, lock=True)
        if await conn.fetchval(
            "SELECT 1 FROM battles WHERE player_id = $1 AND status = 'active'", current_user.player_id
        ):
            raise HTTPException(status_code=400, detail="You can't rest in the middle of a battle.")
        if player["hp"] >= player["max_hp"]:
            raise HTTPException(status_code=400, detail="You are already at full health.")
        cost = rest_cost_for(player["level"])
        if player["gold"] < cost:
            raise HTTPException(status_code=400, detail=f"Resting costs {cost} gold. You can't afford it.")
        await conn.execute(
            "UPDATE players SET hp = $1, gold = gold - $2 WHERE player_id = $3",
            player["max_hp"], cost, current_user.player_id,
        )
        await conn.execute(
            """
            INSERT INTO inventory_transactions (player_id, item_id, transaction_type, quantity, gold_amount, description)
            VALUES ($1, NULL, 'inn_rest', 1, $2, 'Rested at the Whispering Crow Inn (full heal)')
            """,
            current_user.player_id, cost,
        )
    log = [f"You rest at the Whispering Crow Inn for {cost} gold. Health fully restored."]
    return {"log": log, "outcome": "rested", "state": await _build_state(conn, current_user.player_id)}
