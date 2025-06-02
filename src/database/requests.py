from fastapi import HTTPException


from src.database.models import GoodsORM, UsersORM, TradeORM, TradeStatus, async_session
from sqlalchemy import select, or_

from src.models import Goods, GoodsOut, GoodsUpdate, TradeCreate, TradeOut


async def user_registration(username, hashed_password):
    async with async_session() as session:
        async with session.begin():
            new_user = UsersORM(username=username, hashed_password=hashed_password)
            session.add(new_user)
            await session.commit()


async def is_username_taken(username):
    async with async_session() as session:
        query = select(UsersORM).filter(UsersORM.username == username)
        response = await session.execute(query)
        response = response.scalars().first()
        return response is not None


async def get_user_by_username(username):
    async with async_session() as session:
        query = select(UsersORM).filter(UsersORM.username == username)
        response = await session.execute(query)
        user = response.scalars().first()
        return user


async def add_goods(goods: Goods, user_id: int):
    async with async_session() as session:
        new_good = GoodsORM(
            title=goods.title,
            description=goods.description,
            image_url=goods.image_url,
            category=goods.category,
            condition=goods.condition,
            user_id=user_id,
        )
        session.add(new_good)
        await session.flush()
        await session.refresh(new_good)
        good_out = GoodsOut.model_validate(new_good)
        await session.commit()
        return good_out


async def get_goods_from_db(category, condition, search, limit):
    async with async_session() as session:
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
        result = await session.execute(query)

        result = result.scalars().all()
        return result


async def get_your_goods(user_id: int):
    async with async_session() as session:
        query = await session.execute(
            select(GoodsORM).filter(GoodsORM.user_id == user_id)
        )
        goods = query.scalars().all()
        return goods


async def get_good_by_id(good_id):
    async with async_session() as session:
        query = await session.execute(select(GoodsORM).filter(GoodsORM.id == good_id))
        good = query.scalar()
        return good


async def update_goods(good_id: int, update_data: GoodsUpdate, user_id: int):
    async with async_session() as session:
        query = await session.get(GoodsORM, good_id)

        if not query:
            raise HTTPException(status_code=404, detail="Объявление не найдено")

        if query.user_id != user_id:
            raise HTTPException(status_code=403, detail="Доступ запрещен")

        for field, value in update_data.model_dump(exclude_unset=True).items():
            setattr(query, field, value)

        await session.flush()
        await session.refresh(query)
        good_out = GoodsOut.model_validate(query)
        await session.commit()
        return good_out


async def delete_good_by_id(good_id: int, user_id: int):
    async with async_session() as session:
        query = await session.get(GoodsORM, good_id)

        if not query:
            raise HTTPException(status_code=404, detail="Объявление не найдено")

        if query.user_id != user_id:
            raise HTTPException(status_code=403, detail="Доступ запрещен")

        await session.delete(query)
        await session.commit()
        return {"message": "Объявление успешно удалено"}


async def create_trade(trade_data: TradeCreate, sender_id: int):
    async with async_session() as session:
        receiver_ad = await session.get(GoodsORM, trade_data.ad_receiver_id)
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
            receiver_id=receiver_ad.user_id
        )
        session.add(new_trade)
        await session.flush()
        await session.refresh(new_trade)
        trade = TradeOut.model_validate(new_trade)
        await session.commit()
        return trade


async def get_trades(sender_id=None, receiver_id=None, status=None):
    async with async_session() as session:
        query = select(TradeORM)

        if sender_id is not None:
            query = query.where(TradeORM.sender_id == sender_id)
        if receiver_id:
            query = query.where(TradeORM.receiver_id == receiver_id)
        if status:
            query = query.where(TradeORM.status == status)

        result = await session.execute(query)
        return result.scalars().all()


async def update_trade_status(trade_id: int, status: TradeStatus, user_id: int):
    async with async_session() as session:
        query = select(TradeORM).where(TradeORM.id == trade_id)
        result = await session.execute(query)
        trade = result.scalar_one_or_none()

        if not trade:
            raise HTTPException(status_code=404, detail="Предложение не найдено")
        if trade.receiver_id != user_id:
            raise HTTPException(
                status_code=403, detail="Вы не можете изменить это предложение"
            )

        trade.status = status
        await session.commit()
        await session.refresh(trade)
        return trade
