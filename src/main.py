from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, status
from fastapi.params import Query
from fastapi.security import OAuth2PasswordRequestForm

from src.database.models import ConditionsGoods, Base
from src.database.requests import *
from src.database.session import get_db, engine
from src.models import (
    Token,
    UserCreate,
    Goods,
    GoodsOut,
    GoodsUpdate,
    TradeOut,
    TradeCreate,
    TradeUpdate,
)
from src.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_password_hash,
    authenticate_user,
    get_current_user,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(lifespan=lifespan, title="Площадка для обмена товарами")


@app.post("/register", tags=["users"])
async def registration_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    if await is_username_taken(username=user.username, db=db):
        raise HTTPException(
            status_code=400, detail="Пользователь с таким именем уже существует"
        )

    hashed_password = get_password_hash(user.password)
    await user_registration(user.username, hashed_password, db)
    return {"message": "Пользователь зарегистрирован"}


@app.post("/login", tags=["users"])
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db),
) -> Token:
    user = await authenticate_user(
        form_data.username,
        form_data.password,
        db=db,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "id": user.id}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")


@app.get("/goods/mine", tags=["goods"])
async def read_your_goods(
    current_user: Annotated[UsersORM, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    response = await get_your_goods(current_user.id, db)
    return response


@app.post("/goods/", tags=["goods"])
async def create_goods(
    good: Goods,
    current_user: Annotated[UsersORM, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    response = await add_goods(good, user_id=current_user.id, db=db)
    return {"message": "товар добавлен", "goods": response}


@app.get("/goods/", response_model=list[GoodsOut], tags=["goods"])
async def get_goods(
    category: str | None = None,
    condition: ConditionsGoods | None = None,
    search: str | None = None,
    limit: int = Query(default=10, le=20),
    db: AsyncSession = Depends(get_db),
):
    response = await get_goods_from_db(category, condition, search, limit, db)
    return response


@app.get("/goods/{good_id}", response_model=GoodsOut, tags=["goods"])
async def get_one_good(good_id: int, db: AsyncSession = Depends(get_db)):
    response = await get_good_by_id(good_id, db)
    return response


@app.patch("/goods/{good_id}", tags=["goods"])
async def edit_good(
    good_id: int,
    update_data: GoodsUpdate,
    current_user: Annotated[UsersORM, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    updated = await update_goods(good_id, update_data, user_id=current_user.id, db=db)
    return updated


@app.delete("/goods/{good_id}", tags=["goods"])
async def delete_good(
    good_id: int,
    current_user: Annotated[UsersORM, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    response = await delete_good_by_id(good_id, current_user.id, db=db)
    return response


@app.post("/offers/", response_model=TradeOut, tags=["offers"])
async def send_trade_offer(
    trade_data: TradeCreate,
    current_user: Annotated[UsersORM, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    trade = await create_trade(trade_data, sender_id=current_user.id, db=db)
    return trade


@app.get("/offers/", response_model=list[TradeOut], tags=["offers"])
async def get_list_trades(
    sender_id: int = None,
    receiver_id: int = None,
    trade_status: TradeStatus = None,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if sender_id is None and receiver_id is None:
        sender_id = current_user.id
        receiver_id = current_user.id

    trades = await get_trades(sender_id, receiver_id, trade_status, db=db)
    return trades


@app.patch("/offers/{offer_id}", response_model=TradeOut, tags=["offers"])
async def change_trade_status(
    offer_id: int,
    update: TradeUpdate,
    current_user: Annotated[UsersORM, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    trade = await update_trade_status(offer_id, update.status, current_user.id, db=db)
    return trade


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
