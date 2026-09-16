import uuid

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OrderDetails(Base):
    __tablename__ = "order_details"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        default=uuid.uuid4,
        index=True
    )

    name: Mapped[str] = mapped_column(String)
    food_item: Mapped[str] = mapped_column(String)
    phno: Mapped[int] = mapped_column(Integer)
    price: Mapped[int] = mapped_column(Integer)


class Payment(Base):
    __tablename__ = "payment"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    order_id: Mapped[uuid.UUID] = mapped_column(index=True)
    food_item: Mapped[str] = mapped_column(String)

    payment_id: Mapped[uuid.UUID] = mapped_column(
        default=uuid.uuid4,
        unique=True,
        index=True
    )

    price: Mapped[int] = mapped_column(Integer)