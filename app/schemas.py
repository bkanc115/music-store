"""Pydantic-схемы: валидация входных данных и формат ответов API."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Авторизация -----------------------------------------------------------
class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    role: Literal["admin", "seller"] = "seller"


class UserOut(ORM):
    id: int
    username: str
    role: str


# --- Музыканты и ансамбли --------------------------------------------------
class MusicianIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    instrument: str | None = Field(default=None, max_length=100)


class MusicianOut(ORM, MusicianIn):
    id: int


class EnsembleIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    genre: str | None = Field(default=None, max_length=100)
    founded_year: int | None = Field(default=None, ge=1800, le=2100)


class EnsembleOut(ORM, EnsembleIn):
    id: int


class MemberIn(BaseModel):
    musician_id: int = Field(gt=0)
    role: str | None = Field(default=None, max_length=100)


class MemberOut(ORM):
    musician: MusicianOut
    role: str | None


# --- Диски, цены, остатки --------------------------------------------------
class DiscIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    catalog_number: str = Field(min_length=1, max_length=50)
    ensemble_id: int = Field(gt=0)
    label: str | None = Field(default=None, max_length=100)
    release_year: int | None = Field(default=None, ge=1900, le=2100)
    tracklist: str | None = None


class DiscOut(ORM):
    id: int
    title: str
    catalog_number: str
    ensemble_id: int
    ensemble_name: str
    label: str | None
    release_year: int | None
    tracklist: str | None
    current_price: Decimal | None
    stock_quantity: int


class PriceIn(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    valid_from: date


class PriceOut(ORM):
    id: int
    disc_id: int
    amount: Decimal
    valid_from: date


class StockAdjustIn(BaseModel):
    """Поступление (delta > 0) или списание (delta < 0) дисков."""

    delta: int = Field(ge=-100_000, le=100_000)

    @field_validator("delta")
    @classmethod
    def not_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("delta не может быть равен 0")
        return v


class StockOut(BaseModel):
    disc_id: int
    title: str
    quantity: int


# --- Продажи и отчёты ------------------------------------------------------
class SaleIn(BaseModel):
    disc_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=1000)


class SaleOut(ORM):
    id: int
    disc_id: int
    seller_id: int | None
    quantity: int
    unit_price: Decimal
    total: Decimal
    sold_at: datetime


class LowStockOut(BaseModel):
    disc_id: int
    title: str
    ensemble: str
    quantity: int


class TopSellerOut(BaseModel):
    disc_id: int
    title: str
    ensemble: str
    copies_sold: int
    revenue: Decimal
