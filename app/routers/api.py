"""HTTP API (JSON). Префикс /api.

Права доступа:
  * без входа — чтение каталога (диски, ансамбли, музыканты);
  * seller   — продажи, просмотр остатков и отчётов;
  * admin    — всё, включая изменение каталога, цен, остатков и пользователей.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app import schemas, services
from app.db import get_db
from app.errors import Conflict, NotFound, Unauthorized
from app.models import Disc, Ensemble, EnsembleMember, Musician, Price, Sale, Stock, User
from app.security import get_current_user, hash_password, require_admin, verify_password

router = APIRouter(prefix="/api")


# --- Авторизация -----------------------------------------------------------
@router.post("/auth/login", response_model=schemas.UserOut, tags=["auth"])
def login(data: schemas.LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == data.username))
    if user is None or not verify_password(data.password, user.password_hash):
        raise Unauthorized("Неверное имя пользователя или пароль")
    request.session.clear()
    request.session["user_id"] = user.id
    return user


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["auth"])
def logout(request: Request):
    request.session.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/auth/me", response_model=schemas.UserOut, tags=["auth"])
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/users", response_model=list[schemas.UserOut], tags=["auth"])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.scalars(select(User).order_by(User.id)).all()


@router.post("/users", response_model=schemas.UserOut, status_code=201, tags=["auth"])
def create_user(
    data: schemas.UserIn, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    if db.scalar(select(User).where(User.username == data.username)):
        raise Conflict("Пользователь с таким именем уже существует")
    user = User(username=data.username, password_hash=hash_password(data.password), role=data.role)
    db.add(user)
    db.commit()
    return user


# --- Музыканты -------------------------------------------------------------
@router.get("/musicians", response_model=list[schemas.MusicianOut], tags=["musicians"])
def list_musicians(db: Session = Depends(get_db)):
    return db.scalars(select(Musician).order_by(Musician.full_name)).all()


@router.post("/musicians", response_model=schemas.MusicianOut, status_code=201, tags=["musicians"])
def create_musician(
    data: schemas.MusicianIn, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    m = Musician(**data.model_dump())
    db.add(m)
    db.commit()
    return m


@router.get("/musicians/{musician_id}", response_model=schemas.MusicianOut, tags=["musicians"])
def get_musician(musician_id: int, db: Session = Depends(get_db)):
    m = db.get(Musician, musician_id)
    if m is None:
        raise NotFound(f"Музыкант с id={musician_id} не найден")
    return m


@router.put("/musicians/{musician_id}", response_model=schemas.MusicianOut, tags=["musicians"])
def update_musician(
    musician_id: int,
    data: schemas.MusicianIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    m = get_musician(musician_id, db)
    for k, v in data.model_dump().items():
        setattr(m, k, v)
    db.commit()
    return m


@router.delete("/musicians/{musician_id}", status_code=204, tags=["musicians"])
def delete_musician(
    musician_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    db.delete(get_musician(musician_id, db))
    db.commit()
    return Response(status_code=204)


# --- Ансамбли --------------------------------------------------------------
@router.get("/ensembles", response_model=list[schemas.EnsembleOut], tags=["ensembles"])
def list_ensembles(db: Session = Depends(get_db)):
    return db.scalars(select(Ensemble).order_by(Ensemble.name)).all()


@router.post("/ensembles", response_model=schemas.EnsembleOut, status_code=201, tags=["ensembles"])
def create_ensemble(
    data: schemas.EnsembleIn, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    if db.scalar(select(Ensemble).where(Ensemble.name == data.name)):
        raise Conflict("Ансамбль с таким названием уже существует")
    e = Ensemble(**data.model_dump())
    db.add(e)
    db.commit()
    return e


@router.get("/ensembles/{ensemble_id}", response_model=schemas.EnsembleOut, tags=["ensembles"])
def get_ensemble(ensemble_id: int, db: Session = Depends(get_db)):
    return services.ensure_ensemble(db, ensemble_id)


@router.put("/ensembles/{ensemble_id}", response_model=schemas.EnsembleOut, tags=["ensembles"])
def update_ensemble(
    ensemble_id: int,
    data: schemas.EnsembleIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    e = services.ensure_ensemble(db, ensemble_id)
    for k, v in data.model_dump().items():
        setattr(e, k, v)
    db.commit()
    return e


@router.delete("/ensembles/{ensemble_id}", status_code=204, tags=["ensembles"])
def delete_ensemble(
    ensemble_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    e = services.ensure_ensemble(db, ensemble_id)
    if e.discs:
        raise Conflict("Нельзя удалить ансамбль, у которого есть диски в каталоге")
    db.delete(e)
    db.commit()
    return Response(status_code=204)


@router.get(
    "/ensembles/{ensemble_id}/members", response_model=list[schemas.MemberOut], tags=["ensembles"]
)
def list_members(ensemble_id: int, db: Session = Depends(get_db)):
    return services.ensure_ensemble(db, ensemble_id).members


@router.post(
    "/ensembles/{ensemble_id}/members",
    response_model=schemas.MemberOut,
    status_code=201,
    tags=["ensembles"],
)
def add_member(
    ensemble_id: int,
    data: schemas.MemberIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    services.ensure_ensemble(db, ensemble_id)
    if db.get(Musician, data.musician_id) is None:
        raise NotFound(f"Музыкант с id={data.musician_id} не найден")
    exists = db.scalar(
        select(EnsembleMember).where(
            EnsembleMember.ensemble_id == ensemble_id,
            EnsembleMember.musician_id == data.musician_id,
        )
    )
    if exists:
        raise Conflict("Музыкант уже состоит в этом ансамбле")
    member = EnsembleMember(ensemble_id=ensemble_id, musician_id=data.musician_id, role=data.role)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


# --- Диски -----------------------------------------------------------------
@router.get("/discs", response_model=list[schemas.DiscOut], tags=["discs"])
def list_discs(
    q: str | None = Query(default=None, max_length=100, description="Поиск по названию"),
    ensemble_id: int | None = None,
    db: Session = Depends(get_db),
):
    return services.list_discs(db, q, ensemble_id)


@router.post("/discs", response_model=schemas.DiscOut, status_code=201, tags=["discs"])
def create_disc(
    data: schemas.DiscIn, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    services.ensure_ensemble(db, data.ensemble_id)
    if db.scalar(select(Disc).where(Disc.catalog_number == data.catalog_number)):
        raise Conflict("Диск с таким каталожным номером уже существует")
    disc = Disc(**data.model_dump())
    disc.stock = Stock(quantity=0)
    db.add(disc)
    db.commit()
    return services.disc_view(db, disc)


@router.get("/discs/{disc_id}", response_model=schemas.DiscOut, tags=["discs"])
def get_disc(disc_id: int, db: Session = Depends(get_db)):
    return services.disc_view(db, services.get_disc(db, disc_id))


@router.put("/discs/{disc_id}", response_model=schemas.DiscOut, tags=["discs"])
def update_disc(
    disc_id: int,
    data: schemas.DiscIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    disc = services.get_disc(db, disc_id)
    services.ensure_ensemble(db, data.ensemble_id)
    for k, v in data.model_dump().items():
        setattr(disc, k, v)
    db.commit()
    db.refresh(disc)
    return services.disc_view(db, disc)


@router.delete("/discs/{disc_id}", status_code=204, tags=["discs"])
def delete_disc(disc_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    disc = services.get_disc(db, disc_id)
    if disc.sales:
        raise Conflict("Нельзя удалить диск, по которому уже были продажи")
    db.delete(disc)
    db.commit()
    return Response(status_code=204)


# --- Цены ------------------------------------------------------------------
@router.get("/discs/{disc_id}/prices", response_model=list[schemas.PriceOut], tags=["prices"])
def list_prices(disc_id: int, db: Session = Depends(get_db)):
    return services.get_disc(db, disc_id).prices


@router.post(
    "/discs/{disc_id}/prices", response_model=schemas.PriceOut, status_code=201, tags=["prices"]
)
def add_price(
    disc_id: int,
    data: schemas.PriceIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    services.get_disc(db, disc_id)
    exists = db.scalar(
        select(Price).where(Price.disc_id == disc_id, Price.valid_from == data.valid_from)
    )
    if exists:
        raise Conflict("Цена на эту дату уже задана")
    price = Price(disc_id=disc_id, **data.model_dump())
    db.add(price)
    db.commit()
    return price


# --- Остатки ---------------------------------------------------------------
@router.get("/stock", response_model=list[schemas.StockOut], tags=["stock"])
def list_stock(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.execute(
        select(Disc.id, Disc.title, Stock.quantity)
        .join(Stock, Stock.disc_id == Disc.id, isouter=True)
        .order_by(Disc.title)
    )
    return [{"disc_id": r[0], "title": r[1], "quantity": r[2] or 0} for r in rows]


@router.post("/discs/{disc_id}/stock", response_model=schemas.StockOut, tags=["stock"])
def adjust_stock(
    disc_id: int,
    data: schemas.StockAdjustIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    stock = services.adjust_stock(db, disc_id, data.delta)
    return {"disc_id": disc_id, "title": stock.disc.title, "quantity": stock.quantity}


# --- Продажи ---------------------------------------------------------------
@router.get("/sales", response_model=list[schemas.SaleOut], tags=["sales"])
def list_sales(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Sale).options(joinedload(Sale.disc)).order_by(Sale.sold_at.desc()).limit(limit)
    return db.scalars(stmt).all()


@router.post("/sales", response_model=schemas.SaleOut, status_code=201, tags=["sales"])
def create_sale(
    data: schemas.SaleIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return services.register_sale(db, data.disc_id, data.quantity, user)


# --- Отчёты ----------------------------------------------------------------
@router.get("/reports/top-sellers", response_model=list[schemas.TopSellerOut], tags=["reports"])
def top_sellers(
    limit: int = Query(default=10, ge=1, le=100),
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return services.top_sellers(db, limit, date_from, date_to)


@router.get("/reports/low-stock", response_model=list[schemas.LowStockOut], tags=["reports"])
def low_stock(
    threshold: int = Query(default=3, ge=0, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return services.low_stock(db, threshold)
