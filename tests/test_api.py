from datetime import date, timedelta

from app.models import Stock


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "X-Request-ID" in r.headers


def test_catalog_is_public(client, disc):
    r = client.get("/api/discs")
    assert r.status_code == 200
    [item] = r.json()
    assert item["title"] == "Тестовый диск"
    assert item["current_price"] == "500.00"
    assert item["stock_quantity"] == 3


def test_web_pages_render(client, disc):
    assert client.get("/").status_code == 200
    assert client.get(f"/discs/{disc.id}").status_code == 200
    assert client.get("/login").status_code == 200
    # без входа закрытые страницы перенаправляют на вход
    r = client.get("/sales", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].startswith("/login")


# --- Авторизация -----------------------------------------------------------
def test_login_wrong_password(client, db_session):
    from tests.conftest import _user

    _user(db_session, "bob", "seller")
    r = client.post("/api/auth/login", json={"username": "bob", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_me_requires_login(client):
    assert client.get("/api/auth/me").status_code == 401


def test_seller_cannot_modify_catalog(seller_client):
    r = seller_client.post("/api/ensembles", json={"name": "X"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_logout(seller_client):
    assert seller_client.get("/api/auth/me").status_code == 200
    seller_client.post("/api/auth/logout")
    assert seller_client.get("/api/auth/me").status_code == 401


# --- Каталог ---------------------------------------------------------------
def test_admin_creates_catalog(admin_client):
    e = admin_client.post("/api/ensembles", json={"name": "Новый", "genre": "джаз"})
    assert e.status_code == 201
    m = admin_client.post("/api/musicians", json={"full_name": "Пётр Иванов"})
    assert m.status_code == 201
    member = admin_client.post(
        f"/api/ensembles/{e.json()['id']}/members",
        json={"musician_id": m.json()["id"], "role": "саксофон"},
    )
    assert member.status_code == 201
    d = admin_client.post(
        "/api/discs",
        json={"title": "Альбом", "catalog_number": "N-1", "ensemble_id": e.json()["id"]},
    )
    assert d.status_code == 201
    assert d.json()["stock_quantity"] == 0
    assert d.json()["current_price"] is None


def test_duplicate_catalog_number(admin_client, disc):
    r = admin_client.post(
        "/api/discs",
        json={"title": "Дубль", "catalog_number": "T-1", "ensemble_id": disc.ensemble_id},
    )
    assert r.status_code == 409


def test_disc_with_unknown_ensemble(admin_client):
    r = admin_client.post(
        "/api/discs", json={"title": "A", "catalog_number": "Z-1", "ensemble_id": 999}
    )
    assert r.status_code == 404


def test_validation_error_format(admin_client):
    r = admin_client.post("/api/ensembles", json={"name": "", "founded_year": "abc"})
    assert r.status_code == 422
    body = r.json()["error"]
    assert body["code"] == "validation_error"
    fields = {d["field"] for d in body["details"]}
    assert {"name", "founded_year"} <= fields


def test_unknown_route_returns_json_404(client):
    r = client.get("/api/nothing")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


# --- Правила предметной области ----------------------------------------------
def test_sale_decreases_stock_and_uses_current_price(seller_client, disc, db_session):
    r = seller_client.post("/api/sales", json={"disc_id": disc.id, "quantity": 2})
    assert r.status_code == 201
    assert r.json()["unit_price"] == "500.00"
    assert r.json()["total"] == "1000.00"
    db_session.expire_all()
    assert db_session.get(Stock, disc.stock.id).quantity == 1


def test_cannot_sell_more_than_in_stock(seller_client, disc):
    r = seller_client.post("/api/sales", json={"disc_id": disc.id, "quantity": 4})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "business_rule_violation"
    assert err["details"] == {"available": 3, "requested": 4}


def test_cannot_sell_without_price(admin_client, disc, db_session):
    for p in list(disc.prices):
        db_session.delete(p)
    db_session.commit()
    r = admin_client.post("/api/sales", json={"disc_id": disc.id, "quantity": 1})
    assert r.status_code == 422


def test_future_price_is_not_applied_yet(admin_client, disc):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    r = admin_client.post(
        f"/api/discs/{disc.id}/prices", json={"amount": "700.00", "valid_from": tomorrow}
    )
    assert r.status_code == 201
    sale = admin_client.post("/api/sales", json={"disc_id": disc.id, "quantity": 1})
    assert sale.json()["unit_price"] == "500.00"


def test_new_price_applies_from_today(admin_client, disc):
    today = date.today().isoformat()
    admin_client.post(
        f"/api/discs/{disc.id}/prices", json={"amount": "650.00", "valid_from": today}
    )
    assert admin_client.get(f"/api/discs/{disc.id}").json()["current_price"] == "650.00"


def test_stock_cannot_go_negative(admin_client, disc):
    r = admin_client.post(f"/api/discs/{disc.id}/stock", json={"delta": -10})
    assert r.status_code == 422
    ok = admin_client.post(f"/api/discs/{disc.id}/stock", json={"delta": 5})
    assert ok.json()["quantity"] == 8


def test_cannot_delete_disc_with_sales(admin_client, disc):
    admin_client.post("/api/sales", json={"disc_id": disc.id, "quantity": 1})
    assert admin_client.delete(f"/api/discs/{disc.id}").status_code == 409


def test_top_sellers_report(seller_client, disc):
    seller_client.post("/api/sales", json={"disc_id": disc.id, "quantity": 2})
    seller_client.post("/api/sales", json={"disc_id": disc.id, "quantity": 1})
    [row] = seller_client.get("/api/reports/top-sellers").json()
    assert row["copies_sold"] == 3
    assert row["revenue"] == "1500.00"
