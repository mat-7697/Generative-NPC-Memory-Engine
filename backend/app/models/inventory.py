from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ItemResponse(BaseModel):
    item_id: int
    name: str
    description: Optional[str] = None
    base_price: int
    item_type: str
    rarity: str
    stock: int
    attack_power: int = 0
    defense_power: int = 0
    heal_amount: int = 0


class InventoryItem(BaseModel):
    inventory_id: int
    item_id: int
    name: str
    description: Optional[str] = None
    base_price: int
    item_type: str
    rarity: str
    attack_power: int = 0
    defense_power: int = 0
    heal_amount: int = 0
    quantity: int
    is_equipped: bool = False
    acquired_at: datetime


class UseItemRequest(BaseModel):
    item_id: int = Field(..., gt=0)


class BuyRequest(BaseModel):
    item_id: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)


class SellRequest(BaseModel):
    item_id: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)


class TransferRequest(BaseModel):
    to_player_id: int = Field(..., gt=0)
    item_id: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)


class TransactionResponse(BaseModel):
    transaction_id: int
    player_id: int
    item_id: Optional[int] = None
    item_name: Optional[str] = None
    transaction_type: str
    quantity: int
    gold_amount: int
    description: Optional[str] = None
    created_at: datetime
