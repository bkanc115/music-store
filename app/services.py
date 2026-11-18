"""Бизнес-логика магазина. Здесь сосредоточены правила предметной области.

Правила:
  1. Продажа возможна только при наличии на складе нужного количества дисков;
     при продаже остаток уменьшается в той же транзакции.
  2. Цена продажи — цена, действующая на дату продажи (последняя запись
     истории цен с valid_from <= дата). Без действующей цены продавать нельзя.
  3. Остаток не может стать отрицательным при списании.
"""

import logging
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.errors import BusinessRuleError, NotFound
from app.models import Disc, Ensemble, Price, Sale, Stock, User

log = logging.getLogger("app.services")


def get_disc(db: Session, disc_id: int) -> Disc:
    disc = db.get(Disc, disc_id)
    if disc is None:
        raise NotFound(f"Диск с id={disc_id} не найден")
    return disc


def current_price(db: Session, disc_id: int, on: date | None = None) -> Decimal | None:
    on = on or date.today()
    stmt = (
        select(Price.amount)
        .where(Price.disc_id == disc_id, Price.valid_from <= on)
        .order_by(Price.valid_from.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def disc_view(db: Session, disc: Disc) -> dict:
    """Диск вместе с ансамблем, действующей ценой и остатком (для API и страниц)."""
    return {
        "id": disc.id,
        "title": disc.title,
        "catalog_number": disc.catalog_number,
        "ensemble_id": disc.ensemble_id,
        "ensemble_name": disc.ensemble.name,
        "label": disc.label,
        "release_year": disc.release_year,
        "tracklist": disc.tracklist,
        "current_price": current_price(db, disc.id),
        "stock_quantity": disc.stock.quantity if disc.stock else 0,
    }


def list_discs(db: Session, q: str | None = None, ensemble_id: int | None = None) -> list[dict]:
    stmt = select(Disc).options(joinedload(Disc.ensemble), joinedload(Disc.stock))
    if q:
        stmt = stmt.where(Disc.title.ilike(f"%{q}%"))
    if ensemble_id:
        stmt = stmt.where(Disc.ensemble_id == ensemble_id)
    discs = db.scalars(stmt.order_by(Disc.title)).unique().all()
    return [disc_view(db, d) for d in discs]


def ensure_ensemble(db: Session, ensemble_id: int) -> Ensemble:
    ensemble = db.get(Ensemble, ensemble_id)
    if ensemble is None:
        raise NotFound(f"Ансамбль с id={ensemble_id} не найден")
    return ensemble


def _locked_stock(db: Session, disc_id: int) -> Stock:
    """Строка остатка с блокировкой FOR UPDATE, чтобы параллельные продажи не ушли в минус."""
    stock = db.scalar(select(Stock).where(Stock.disc_id == disc_id).with_for_update())
    if stock is None:
        stock = Stock(disc_id=disc_id, quantity=0)
        db.add(stock)
        db.flush()
    return stock


def adjust_stock(db: Session, disc_id: int, delta: int) -> Stock:
    get_disc(db, disc_id)
    stock = _locked_stock(db, disc_id)
    if stock.quantity + delta < 0:
        raise BusinessRuleError(
            "Списание больше, чем есть на складе",
            {"available": stock.quantity, "requested": -delta},
        )
    stock.quantity += delta
    db.commit()
    log.info("stock_adjusted disc_id=%s delta=%s quantity=%s", disc_id, delta, stock.quantity)
    return stock


def register_sale(db: Session, disc_id: int, quantity: int, seller: User | None) -> Sale:
    disc = get_disc(db, disc_id)
    now = datetime.now(UTC)

    price = current_price(db, disc.id, now.date())
    if price is None:
        raise BusinessRuleError("Для диска не задана действующая цена — продажа невозможна")

    stock = _locked_stock(db, disc.id)
    if stock.quantity < quantity:
        raise BusinessRuleError(
            "Недостаточно дисков на складе",
            {"available": stock.quantity, "requested": quantity},
        )

    stock.quantity -= quantity
    sale = Sale(
        disc_id=disc.id,
        seller_id=seller.id if seller else None,
        quantity=quantity,
        unit_price=price,
        total=price * quantity,
        sold_at=now,
    )
    db.add(sale)
    db.commit()
    log.info(
        "sale_registered sale_id=%s disc_id=%s qty=%s total=%s seller=%s",
        sale.id,
        disc.id,
        quantity,
        sale.total,
        seller.username if seller else None,
    )
    return sale


def top_sellers(
    db: Session, limit: int = 10, date_from: date | None = None, date_to: date | None = None
) -> list[dict]:
    copies = func.sum(Sale.quantity).label("copies_sold")
    revenue = func.sum(Sale.total).label("revenue")
    stmt = (
        select(Disc.id, Disc.title, Ensemble.name, copies, revenue)
        .join(Sale, Sale.disc_id == Disc.id)
        .join(Ensemble, Ensemble.id == Disc.ensemble_id)
        .group_by(Disc.id, Disc.title, Ensemble.name)
        .order_by(copies.desc(), revenue.desc())
        .limit(limit)
    )
    if date_from:
        stmt = stmt.where(func.date(Sale.sold_at) >= date_from)
    if date_to:
        stmt = stmt.where(func.date(Sale.sold_at) <= date_to)
    return [
        {
            "disc_id": r[0],
            "title": r[1],
            "ensemble": r[2],
            "copies_sold": int(r[3]),
            "revenue": Decimal(r[4]),
        }
        for r in db.execute(stmt)
    ]
