from typing import List, Optional
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.auth import TokenData
from app.models.inventory import (
    BuyRequest,
    InventoryItem,
    ItemResponse,
    SellRequest,
    TransactionResponse,
    TransferRequest,
    UseItemRequest,
)

router = APIRouter(tags=["Inventory & Economy"])


@router.get("/items", response_model=List[ItemResponse])
async def list_items(
    query: Optional[str] = Query(None, description="Full-text search query across item names and descriptions"),
    conn: asyncpg.Connection = Depends(get_db),
):
    """List merchant catalog items with optional PostgreSQL full-text search."""
    if query and query.strip():
        sql = """
            SELECT item_id, name, description, base_price, item_type, rarity, stock,
                   attack_power, defense_power, heal_amount
            FROM items
            WHERE search_vector @@ plainto_tsquery('english', $1)
            ORDER BY ts_rank(search_vector, plainto_tsquery('english', $1)) DESC, name ASC
        """
        rows = await conn.fetch(sql, query.strip())
    else:
        sql = """
            SELECT item_id, name, description, base_price, item_type, rarity, stock,
                   attack_power, defense_power, heal_amount
            FROM items
            ORDER BY item_id ASC
        """
        rows = await conn.fetch(sql)

    return [ItemResponse(**dict(r)) for r in rows]


@router.get("/my-inventory", response_model=List[InventoryItem])
async def get_my_inventory(
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Retrieve the inventory belonging to the authenticated player."""
    rows = await conn.fetch(
        """
        SELECT 
            pi.inventory_id,
            pi.item_id,
            i.name,
            i.description,
            i.base_price,
            i.item_type,
            i.rarity,
            i.attack_power,
            i.defense_power,
            i.heal_amount,
            pi.quantity,
            COALESCE(pi.is_equipped, FALSE) AS is_equipped,
            pi.acquired_at
        FROM player_inventory pi
        JOIN items i ON pi.item_id = i.item_id
        WHERE pi.player_id = $1 AND pi.quantity > 0
        ORDER BY i.name ASC
        """,
        current_user.player_id,
    )
    return [InventoryItem(**dict(r)) for r in rows]


@router.post("/buy")
async def buy_item(
    request_data: BuyRequest,
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Purchase items from merchant catalog via atomic stored procedure buy_item()."""
    try:
        try:
            await conn.execute(
                "CALL buy_item($1, $2, $3)",
                current_user.player_id,
                request_data.item_id,
                request_data.quantity,
            )
        except asyncpg.exceptions.WrongObjectTypeException:
            await conn.fetchval(
                "SELECT buy_item($1, $2, $3)",
                current_user.player_id,
                request_data.item_id,
                request_data.quantity,
            )
    except asyncpg.PostgresError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return {
        "detail": f"Successfully purchased {request_data.quantity}x item #{request_data.item_id}",
        "item_id": request_data.item_id,
        "quantity": request_data.quantity,
    }


@router.post("/sell")
async def sell_item(
    request_data: SellRequest,
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Sell items back to vendor at 50% base price via stored procedure sell_item()."""
    try:
        try:
            await conn.execute(
                "CALL sell_item($1, $2, $3)",
                current_user.player_id,
                request_data.item_id,
                request_data.quantity,
            )
        except asyncpg.exceptions.WrongObjectTypeException:
            await conn.fetchval(
                "SELECT sell_item($1, $2, $3)",
                current_user.player_id,
                request_data.item_id,
                request_data.quantity,
            )
    except asyncpg.PostgresError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return {
        "detail": f"Successfully sold {request_data.quantity}x item #{request_data.item_id}",
        "item_id": request_data.item_id,
        "quantity": request_data.quantity,
    }


@router.post("/transfer")
async def transfer_item(
    request_data: TransferRequest,
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Transfer items to another player with deadlock prevention via stored procedure transfer_item()."""
    if current_user.player_id == request_data.to_player_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transfer items to yourself",
        )

    try:
        try:
            await conn.execute(
                "CALL transfer_item($1, $2, $3, $4)",
                current_user.player_id,
                request_data.to_player_id,
                request_data.item_id,
                request_data.quantity,
            )
        except asyncpg.exceptions.WrongObjectTypeException:
            await conn.fetchval(
                "SELECT transfer_item($1, $2, $3, $4)",
                current_user.player_id,
                request_data.to_player_id,
                request_data.item_id,
                request_data.quantity,
            )
    except asyncpg.PostgresError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return {
        "detail": f"Successfully transferred {request_data.quantity}x item #{request_data.item_id} to player #{request_data.to_player_id}",
        "to_player_id": request_data.to_player_id,
        "item_id": request_data.item_id,
        "quantity": request_data.quantity,
    }


@router.get("/transactions", response_model=List[TransactionResponse])
async def get_my_transactions(
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Retrieve immutable audit ledger of player inventory transactions."""
    rows = await conn.fetch(
        """
        SELECT 
            t.transaction_id,
            t.player_id,
            t.item_id,
            i.name AS item_name,
            t.transaction_type,
            t.quantity,
            t.gold_amount,
            t.description,
            t.created_at
        FROM inventory_transactions t
        LEFT JOIN items i ON t.item_id = i.item_id
        WHERE t.player_id = $1
        ORDER BY t.created_at DESC
        LIMIT 100
        """,
        current_user.player_id,
    )
    return [TransactionResponse(**dict(r)) for r in rows]


@router.post("/use")
async def use_item(
    request_data: UseItemRequest,
    current_user: TokenData = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Use an item: drink a potion to restore HP, or equip/unequip a weapon or armor piece.

    Only one weapon and one armor piece can be equipped at a time; equipping a new
    one automatically unequips the previous item of that type.
    """
    from app.routers.battle import max_hp_for

    inv_item = await conn.fetchrow(
        """
        SELECT pi.inventory_id, pi.quantity, COALESCE(pi.is_equipped, FALSE) AS is_equipped,
               i.name, i.item_type, i.heal_amount
        FROM player_inventory pi
        JOIN items i ON pi.item_id = i.item_id
        WHERE pi.player_id = $1 AND pi.item_id = $2 AND pi.quantity > 0
        """,
        current_user.player_id,
        request_data.item_id,
    )
    if not inv_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found in your inventory",
        )

    item_type = inv_item["item_type"]
    item_name = inv_item["name"]

    if item_type == "potion":
        async with conn.transaction():
            player = await conn.fetchrow(
                "SELECT hp, level FROM players WHERE player_id = $1 FOR UPDATE", current_user.player_id
            )
            max_hp = max_hp_for(player["level"])
            if player["hp"] >= max_hp:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You are already at full health. Save the potion for battle!",
                )
            healed = min(inv_item["heal_amount"], max_hp - player["hp"])
            if inv_item["quantity"] > 1:
                await conn.execute(
                    "UPDATE player_inventory SET quantity = quantity - 1 WHERE inventory_id = $1",
                    inv_item["inventory_id"],
                )
            else:
                await conn.execute(
                    "DELETE FROM player_inventory WHERE inventory_id = $1",
                    inv_item["inventory_id"],
                )
            await conn.execute(
                "UPDATE players SET hp = hp + $1 WHERE player_id = $2", healed, current_user.player_id
            )
            await conn.execute(
                """
                INSERT INTO inventory_transactions (
                    player_id, item_id, transaction_type, quantity, gold_amount, description, created_at
                ) VALUES ($1, $2, 'consume_item', 1, 0, $3, NOW())
                """,
                current_user.player_id,
                request_data.item_id,
                f"Drank {item_name} (+{healed} HP)",
            )

        return {
            "success": True,
            "action": "consumed",
            "message": f"Drank {item_name}: restored {healed} HP.",
            "healed": healed,
        }

    if item_type not in ("weapon", "armor"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This item can't be used directly. Quest items unlock hunting grounds; materials can be sold.",
        )

    new_equip_state = not inv_item["is_equipped"]
    async with conn.transaction():
        if new_equip_state:
            # Unequip any other item of the same slot first.
            await conn.execute(
                """
                UPDATE player_inventory pi SET is_equipped = FALSE
                FROM items i
                WHERE pi.item_id = i.item_id AND pi.player_id = $1 AND i.item_type = $2 AND pi.is_equipped
                """,
                current_user.player_id,
                item_type,
            )
        await conn.execute(
            "UPDATE player_inventory SET is_equipped = $1 WHERE inventory_id = $2",
            new_equip_state,
            inv_item["inventory_id"],
        )
    verb = "Equipped" if new_equip_state else "Unequipped"
    return {
        "success": True,
        "action": "equip_toggled",
        "is_equipped": new_equip_state,
        "message": f"{verb} {item_name}.",
    }
