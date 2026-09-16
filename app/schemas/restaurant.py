"""Pydantic schemas for Restaurant orders."""

from uuid import UUID

from pydantic import BaseModel


class OrderCreate(BaseModel):
    name: str
    food_item: str
    phno: int


class OrderResponse(BaseModel):
    message: str
    order_id: UUID
    food_item: str


class OrderListResponse(BaseModel):
    order_id: UUID
    food_items: list[str]