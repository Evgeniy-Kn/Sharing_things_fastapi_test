from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import GoodsORM, UsersORM, TradeORM, TradeStatus, async_session
from sqlalchemy import select, or_

from src.models import Goods, GoodsOut, GoodsUpdate, TradeCreate, TradeOut


async def user_registration(username, hashed_password, db: AsyncSession):
    new_user = UsersORM(username=username, hashed_password=hashed_password)
    db.add(new_user)
    await db.commit()


async def is_username_taken(username, db: AsyncSession):
    query = select(UsersORM).filter(UsersORM.username == username)
    response = await db.execute(query)
    response = response.scalars().first()
    return response is not None


async def get_user_by_username(username, db: AsyncSession):
    query = select(UsersORM).filter(UsersORM.username == username)
    response = await db.execute(query)
    user = response.scalars().first()
    return user


async def add_goods(goods: Goods, user_id: int, db: AsyncSession):
    new_good = GoodsORM(
        title=goods.title,
        description=goods.description,
        image_url=goods.image_url,
        category=goods.category,
        condition=goods.condition,
        user_id=user_id,
    )
    db.add(new_good)
    await db.flush()
    await db.refresh(new_good)
    good_out = GoodsOut.model_validate(new_good)
    await db.commit()
    return good_out


async def get_goods_from_db(category, condition, search, limit, db: AsyncSession):

    query = select(GoodsORM)

    if category:
        query = query.where(GoodsORM.category == category)
    if condition:
        query = query.where(GoodsORM.condition == condition)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                GoodsORM.title.ilike(search_pattern),
                GoodsORM.description.ilike(search_pattern),
            )
        )

    query = query.limit(limit)
    result = await db.execute(query)

    result = result.scalars().all()
    return result


async def get_your_goods(user_id: int, db: AsyncSession):
    query = await db.execute(select(GoodsORM).filter(GoodsORM.user_id == user_id))
    goods = query.scalars().all()
    return goods


async def get_good_by_id(good_id, db: AsyncSession):
        query = await db.execute(select(GoodsORM).filter(GoodsORM.id == good_id))
        good = query.scalar()
        return good


async def update_goods(good_id: int, update_data: GoodsUpdate, user_id: int, db: AsyncSession):
    query = await db.get(GoodsORM, good_id)

    if not query:
        raise HTTPException(status_code=404, detail="Объявление не найдено")

    if query.user_id != user_id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(query, field, value)

    await db.flush()
    await db.refresh(query)
    good_out = GoodsOut.model_validate(query)
    await db.commit()
    return good_out


async def delete_good_by_id(good_id: int, user_id: int, db: AsyncSession):
    query = await db.get(GoodsORM, good_id)

    if not query:
        raise HTTPException(status_code=404, detail="Объявление не найдено")

    if query.user_id != user_id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    await db.delete(query)
    await db.commit()
    return {"message": "Объявление успешно удалено"}


async def create_trade(trade_data: TradeCreate, sender_id: int, db: AsyncSession):
    receiver_ad = await db.get(GoodsORM, trade_data.ad_receiver_id)
    if not receiver_ad:
        raise HTTPException(
            status_code=404, detail="Объявление получателя не найдено"
        )
    if sender_id == receiver_ad.user_id:
        raise HTTPException(
            status_code=400, detail="Нельзя предложить обмен самому себе"
        )

    new_trade = TradeORM(
        ad_sender_id=trade_data.ad_sender_id,
        ad_receiver_id=trade_data.ad_receiver_id,
        comment=trade_data.comment,
        sender_id=sender_id,
        receiver_id=receiver_ad.user_id,
    )
    db.add(new_trade)
    await db.flush()
    await db.refresh(new_trade)
    trade = TradeOut.model_validate(new_trade)
    await db.commit()
    return trade


async def get_trades(sender_id, receiver_id, status, db: AsyncSession = None):

    query = select(TradeORM)

    if sender_id is not None and receiver_id is not None:
        # Получаем сделки, где sender_id = X или receiver_id = X (текущий пользователь)
        query = query.where(
            or_(
                TradeORM.sender_id == sender_id,
                TradeORM.receiver_id == receiver_id,
            )
        )
    else:
        if sender_id is not None:
            query = query.where(TradeORM.sender_id == sender_id)
        if receiver_id is not None:
            query = query.where(TradeORM.receiver_id == receiver_id)
    if status is not None:
        query = query.where(TradeORM.status == status)

    result = await db.execute(query)
    return result.scalars().all()


async def update_trade_status(trade_id: int, status: TradeStatus, user_id: int, db: AsyncSession):
        query = select(TradeORM).where(TradeORM.id == trade_id)
        result = await db.execute(query)
        trade = result.scalar_one_or_none()

        if not trade:
            raise HTTPException(status_code=404, detail="Предложение не найдено")
        if trade.receiver_id != user_id:
            raise HTTPException(
                status_code=403, detail="Вы не можете изменить это предложение"
            )

        trade.status = status
        await db.commit()
        await db.refresh(trade)
        return trade
