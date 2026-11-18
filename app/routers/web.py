"""Веб-интерфейс (HTML-страницы на Jinja2).

Страницы только отображают данные; изменения отправляются формами в JSON API
(см. static/app.js), поэтому правила и проверки едины для API и интерфейса.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app import services
from app.db import get_db
from app.models import Ensemble, Musician, Sale, User
from app.security import get_optional_user

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


def render(request: Request, name: str, user: User | None, **ctx):
    return templates.TemplateResponse(request, name, {"user": user, **ctx})


def login_redirect(request: Request) -> RedirectResponse:
    return RedirectResponse(f"/login?next={request.url.path}", status_code=303)


@router.get("/")
def catalog(
    request: Request,
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    return render(request, "catalog.html", user, discs=services.list_discs(db, q), q=q or "")


@router.get("/discs/{disc_id}")
def disc_page(
    disc_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    disc = services.get_disc(db, disc_id)
    return render(
        request,
        "disc.html",
        user,
        disc=services.disc_view(db, disc),
        prices=list(reversed(disc.prices)),
        members=disc.ensemble.members,
    )


@router.get("/login")
def login_page(request: Request, user: User | None = Depends(get_optional_user)):
    return render(request, "login.html", user, next=request.query_params.get("next", "/"))


@router.get("/sales")
def sales_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    if user is None:
        return login_redirect(request)
    sales = db.scalars(
        select(Sale)
        .options(joinedload(Sale.disc), joinedload(Sale.seller))
        .order_by(Sale.sold_at.desc())
        .limit(50)
    ).all()
    return render(request, "sales.html", user, sales=sales, discs=services.list_discs(db))


@router.get("/reports")
def reports_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    if user is None:
        return login_redirect(request)
    return render(
        request,
        "reports.html",
        user,
        top=services.top_sellers(db, 10),
        low=services.low_stock(db, 3),
    )


@router.get("/admin")
def admin_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    if user is None:
        return login_redirect(request)
    if user.role != "admin":
        return RedirectResponse("/", status_code=303)
    return render(
        request,
        "admin.html",
        user,
        ensembles=db.scalars(select(Ensemble).order_by(Ensemble.name)).all(),
        musicians=db.scalars(select(Musician).order_by(Musician.full_name)).all(),
        users=db.scalars(select(User).order_by(User.id)).all(),
    )
