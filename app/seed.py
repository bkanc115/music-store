"""Начальные данные: администратор (из ADMIN_USERNAME / ADMIN_PASSWORD) и демо-каталог.

Запуск: python -m app.seed [--demo]
Повторный запуск безопасен: существующие записи не дублируются.
"""

import logging
import sys
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Disc, Ensemble, EnsembleMember, Musician, Price, Stock, User
from app.security import hash_password

log = logging.getLogger("app.seed")

DEMO = [
    # ансамбль, жанр, год, [(музыкант, инструмент)], [(диск, кат.№, год, цена, остаток)]
    (
        "Северный ветер",
        "рок",
        1998,
        [("Иван Петров", "вокал"), ("Олег Смирнов", "гитара")],
        [
            ("Первый снег", "SV-001", 2001, "990.00", 12),
            ("Огни города", "SV-002", 2005, "1190.00", 5),
        ],
    ),
    (
        "Квартет Ля",
        "классика",
        2010,
        [("Анна Соколова", "скрипка"), ("Мария Орлова", "виолончель")],
        [("Времена года", "KL-101", 2014, "1490.00", 8)],
    ),
    (
        "Блюз-бэнд Полночь",
        "блюз",
        2003,
        [("Сергей Волков", "губная гармоника")],
        [("После полуночи", "BP-011", 2012, "890.00", 0)],
    ),
]


def ensure_admin(db) -> None:
    settings = get_settings()
    if not settings.admin_password:
        log.warning("ADMIN_PASSWORD не задан — администратор не создан")
        return
    if db.scalar(select(User).where(User.username == settings.admin_username)):
        log.info("Администратор %s уже существует", settings.admin_username)
        return
    db.add(
        User(
            username=settings.admin_username,
            password_hash=hash_password(settings.admin_password),
            role="admin",
        )
    )
    db.commit()
    log.info("Создан администратор %s", settings.admin_username)


def load_demo(db) -> None:
    start = date.today() - timedelta(days=30)
    for name, genre, year, people, discs in DEMO:
        if db.scalar(select(Ensemble).where(Ensemble.name == name)):
            continue
        ensemble = Ensemble(name=name, genre=genre, founded_year=year)
        db.add(ensemble)
        for full_name, instrument in people:
            musician = Musician(full_name=full_name, country="Россия", instrument=instrument)
            ensemble.members.append(EnsembleMember(musician=musician, role=instrument))
        for title, cat, released, price, qty in discs:
            disc = Disc(title=title, catalog_number=cat, release_year=released, ensemble=ensemble)
            disc.prices.append(Price(amount=Decimal(price), valid_from=start))
            disc.stock = Stock(quantity=qty)
            db.add(disc)
    db.commit()
    log.info("Демо-каталог загружен")


def main(argv: list[str]) -> None:
    logging.basicConfig(level="INFO", format="%(levelname)s %(message)s")
    with SessionLocal() as db:
        ensure_admin(db)
        if "--demo" in argv:
            load_demo(db)


if __name__ == "__main__":
    main(sys.argv[1:])
