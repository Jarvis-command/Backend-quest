"""Database access for Restaurant Orders."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant import OrderDetails, Payment


async def create_order(
    db: AsyncSession,
    *,
    order: OrderDetails,
    payment: Payment,
) -> OrderDetails:

    db.add(order)

    await db.flush()

    payment.order_id = order.order_id

    db.add(payment)

    await db.commit()

    await db.refresh(order)

    return order


async def list_orders(
    db: AsyncSession,
    *,
    order_id: UUID,
) -> list[OrderDetails]:

    result = await db.execute(
        select(OrderDetails)
        .where(OrderDetails.order_id == order_id)
    )

    return list(result.scalars().all())