from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.database.models import ConditionsGoods, TradeStatus


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class UserCreate(BaseModel):
    username: str
    password: str


class Goods(BaseModel):
    title: str
    description: str
    image_url: str | None
    category: str
    condition: ConditionsGoods


class GoodsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    image_url: str | None
    category: str
    condition: ConditionsGoods
    user_id: int
    created_at: datetime


class GoodsUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    image_url: str | None = None
    category: str | None = None
    condition: ConditionsGoods | None = None


class TradeCreate(BaseModel):
    ad_sender_id: int
    ad_receiver_id: int
    comment: str


class TradeUpdate(BaseModel):
    status: TradeStatus


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ad_sender_id: int
    ad_receiver_id: int
    comment: str
    status: TradeStatus
