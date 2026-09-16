"""Restaurant endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.restaurant import (
    OrderCreate,
    OrderListResponse,
    OrderResponse,
)
from app.services import restaurant_service

router = APIRouter(tags=["restaurant"])



# GET MENU


class Food(BaseModel):
    Cuisine: str
    Starter: str
    Maincourse: str
    Dessert: str


_Menu: list[Food] = [
    Food(
        Cuisine="Indian",
        Starter="Tandoori",
        Maincourse="Biryani",
        Dessert="Apricot Delight"
    ),
    Food(
        Cuisine="Chinese",
        Starter="Manchuria",
        Maincourse="Fried Rice",
        Dessert="Strawberry Jelly"
    )
]


@router.get("/get-menu", response_model=list[Food])
async def get_menu():
    return _Menu



# PLACE ORDER


@router.post("/orders", response_model=OrderResponse)
async def place_order(
    order: OrderCreate,
    db: AsyncSession = Depends(get_db),
):
    created_order = await restaurant_service.place_order(
        db,
        name=order.name,
        food_item=order.food_item,
        phno=order.phno,
    )

    return {
        "message": "Order placed successfully",
        "order_id": created_order.order_id,
        "food_item": created_order.food_item,
    }



# LIST ORDERS


@router.get(
    "/orders/{order_id}",
    response_model=OrderListResponse,
)
async def list_orders(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    orders = await restaurant_service.get_orders(
        db,
        order_id=order_id,
    )

    return {
        "order_id": order_id,
        "food_items": [
            order.food_item
            for order in orders
        ],
    }