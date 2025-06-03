import asyncio
import datetime
import enum

from sqlalchemy import ForeignKey, func, Text
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.database.session import engine


class ConditionsGoods(str, enum.Enum):
    new = "новый"
    used = "б/у"


class TradeStatus(str, enum.Enum):
    pending = "ожидает"
    accepted = "принята"
    rejected = "отклонена"


class Base(AsyncAttrs, DeclarativeBase):
    pass


class UsersORM(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    hashed_password: Mapped[str]


class GoodsORM(Base):
    __tablename__ = "goods"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    description: Mapped[str]
    image_url: Mapped[str | None]
    category: Mapped[str]
    condition: Mapped[ConditionsGoods] = mapped_column(default=ConditionsGoods.new)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class TradeORM(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    ad_sender_id: Mapped[int] = mapped_column(ForeignKey("goods.id"))
    ad_receiver_id: Mapped[int] = mapped_column(ForeignKey("goods.id"))
    comment: Mapped[str] = mapped_column(Text)
    status: Mapped[TradeStatus] = mapped_column(default=TradeStatus.pending)

    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    receiver_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


# Создание всех таблиц
async def async_main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def main():
    await async_main()


if __name__ == "__main__":
    asyncio.run(main())
