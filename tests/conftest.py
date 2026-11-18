"""Тестовое окружение: отдельная БД SQLite в памяти, пересоздаётся для каждого теста."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("LOG_FILE", "")

from datetime import date, timedelta  # noqa: E402
from decimal import Decimal  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Disc, Ensemble, Price, Stock, User  # noqa: E402
from app.security import hash_password  # noqa: E402


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _user(db, username, role):
    user = User(username=username, password_hash=hash_password("password123"), role=role)
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def admin_client(client, db_session):
    _user(db_session, "admin", "admin")
    r = client.post("/api/auth/login", json={"username": "admin", "password": "password123"})
    assert r.status_code == 200
    return client


@pytest.fixture
def seller_client(client, db_session):
    _user(db_session, "seller", "seller")
    r = client.post("/api/auth/login", json={"username": "seller", "password": "password123"})
    assert r.status_code == 200
    return client


@pytest.fixture
def disc(db_session):
    """Диск с ценой 500 ₽ и остатком 3 шт."""
    ensemble = Ensemble(name="Тестовый ансамбль")
    d = Disc(title="Тестовый диск", catalog_number="T-1", ensemble=ensemble)
    d.prices.append(Price(amount=Decimal("500.00"), valid_from=date.today() - timedelta(days=1)))
    d.stock = Stock(quantity=3)
    db_session.add(d)
    db_session.commit()
    return d
