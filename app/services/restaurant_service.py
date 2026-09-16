import random

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant import OrderDetails, Payment
from app.repositories import restaurant_repository


async def place_order(
    db: AsyncSession,
    *,
    name: str,
    food_item: str,
    phno: int,
) -> OrderDetails:

    price = random.randint(150, 300)

    order = OrderDetails(
        name=name,
        food_item=food_item,
        phno=phno,
        price=price,
    )

    payment = Payment(
        food_item=food_item,
        price=price,
    )

    return await restaurant_repository.create_order(
        db,
        order=order,
        payment=payment,
    )


async def get_orders(
    db: AsyncSession,
    *,
    order_id,
) -> list[OrderDetails]:

    return await restaurant_repository.list_orders(
        db,
        order_id=order_id,
    )