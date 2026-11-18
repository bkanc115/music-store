"""ORM-модели предметной области «Музыкальный магазин»."""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('admin', 'seller')", name="ck_users_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="seller")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Musician(Base):
    __tablename__ = "musicians"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200))
    country: Mapped[str | None] = mapped_column(String(100))
    instrument: Mapped[str | None] = mapped_column(String(100))

    memberships: Mapped[list["EnsembleMember"]] = relationship(
        back_populates="musician", cascade="all, delete-orphan"
    )


class Ensemble(Base):
    __tablename__ = "ensembles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    genre: Mapped[str | None] = mapped_column(String(100))
    founded_year: Mapped[int | None] = mapped_column(Integer)

    members: Mapped[list["EnsembleMember"]] = relationship(
        back_populates="ensemble", cascade="all, delete-orphan"
    )
    discs: Mapped[list["Disc"]] = relationship(back_populates="ensemble")


class EnsembleMember(Base):
    """Связь многие-ко-многим: музыкант состоит в ансамбле в определённой роли."""

    __tablename__ = "ensemble_members"
    __table_args__ = (UniqueConstraint("ensemble_id", "musician_id", name="uq_ensemble_musician"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ensemble_id: Mapped[int] = mapped_column(ForeignKey("ensembles.id", ondelete="CASCADE"))
    musician_id: Mapped[int] = mapped_column(ForeignKey("musicians.id", ondelete="CASCADE"))
    role: Mapped[str | None] = mapped_column(String(100))

    ensemble: Mapped[Ensemble] = relationship(back_populates="members")
    musician: Mapped[Musician] = relationship(back_populates="memberships")


class Disc(Base):
    __tablename__ = "discs"
    __table_args__ = (
        CheckConstraint("release_year IS NULL OR release_year >= 1900", name="ck_discs_year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    catalog_number: Mapped[str] = mapped_column(String(50), unique=True)
    ensemble_id: Mapped[int] = mapped_column(ForeignKey("ensembles.id", ondelete="RESTRICT"))
    label: Mapped[str | None] = mapped_column(String(100))
    release_year: Mapped[int | None] = mapped_column(Integer)
    tracklist: Mapped[str | None] = mapped_column(Text)

    ensemble: Mapped[Ensemble] = relationship(back_populates="discs")
    prices: Mapped[list["Price"]] = relationship(
        back_populates="disc", cascade="all, delete-orphan", order_by="Price.valid_from"
    )
    stock: Mapped["Stock | None"] = relationship(
        back_populates="disc", cascade="all, delete-orphan", uselist=False
    )
    sales: Mapped[list["Sale"]] = relationship(back_populates="disc")


class Price(Base):
    """История цен: действующей считается запись с наибольшей valid_from <= дата."""

    __tablename__ = "prices"
    __table_args__ = (
        UniqueConstraint("disc_id", "valid_from", name="uq_price_disc_date"),
        CheckConstraint("amount > 0", name="ck_prices_amount_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    disc_id: Mapped[int] = mapped_column(ForeignKey("discs.id", ondelete="CASCADE"))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    valid_from: Mapped[date] = mapped_column(Date)

    disc: Mapped[Disc] = relationship(back_populates="prices")


class Stock(Base):
    """Остаток диска на складе магазина (одна запись на диск)."""

    __tablename__ = "stock"
    __table_args__ = (CheckConstraint("quantity >= 0", name="ck_stock_quantity_nonnegative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    disc_id: Mapped[int] = mapped_column(ForeignKey("discs.id", ondelete="CASCADE"), unique=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    disc: Mapped[Disc] = relationship(back_populates="stock")


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_sales_quantity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    disc_id: Mapped[int] = mapped_column(ForeignKey("discs.id", ondelete="RESTRICT"))
    seller_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    sold_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    disc: Mapped[Disc] = relationship(back_populates="sales")
    seller: Mapped[User | None] = relationship()
