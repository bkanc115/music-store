# Описание HTTP API

Базовый адрес: `http://<host>:<port>`. Формат данных — JSON (UTF-8).
Интерактивная документация (OpenAPI/Swagger) генерируется автоматически: `/docs`, схема — `/openapi.json`.

## Авторизация

Вход: `POST /api/auth/login`. Сервер ставит подписанную cookie-сессию `session`, и её нужно
передавать в следующих запросах (браузер делает это сам, в curl — `-c cookies.txt -b cookies.txt`).

| Роль | Права |
|---|---|
| без входа | чтение каталога: диски, ансамбли, музыканты, цены |
| `seller` (продавец) | + оформление продаж, просмотр остатков, продаж и отчётов |
| `admin` (администратор) | + изменение каталога, цен, остатков, создание пользователей |

## Формат ошибок

Все ошибки возвращаются в одном формате:

```json
{"error": {"code": "business_rule_violation", "message": "Недостаточно дисков на складе",
           "details": {"available": 3, "requested": 5}}}
```

| HTTP | code | Когда |
|---|---|---|
| 401 | `unauthorized` | нет входа или неверный пароль |
| 403 | `forbidden` | не хватает прав (например, продавец меняет каталог) |
| 404 | `not_found` | объект или адрес не найден |
| 405 | `method_not_allowed` | неподдерживаемый HTTP-метод |
| 409 | `conflict` | дубликат (каталожный номер, имя) или удаление связанной записи |
| 422 | `validation_error` | некорректные данные; в `details` список `{field, message}` |
| 422 | `business_rule_violation` | нарушено правило предметной области |
| 500 | `internal_error` | непредвиденная ошибка (подробности в журнале по `X-Request-ID`) |

Каждый ответ содержит заголовок `X-Request-ID`. По нему запрос можно найти в журнале.

## Служебные адреса

| Метод | Адрес | Описание |
|---|---|---|
| GET | `/health` | `200 {"status":"ok","database":"ok","version":"0.1.0"}`; `503`, если БД недоступна |
| GET | `/docs` | Swagger UI |

## Эндпоинты

### Авторизация и пользователи
| Метод | Адрес | Доступ | Тело запроса |
|---|---|---|---|
| POST | `/api/auth/login` | все | `{"username": "admin", "password": "..."}` |
| POST | `/api/auth/logout` | все | — |
| GET | `/api/auth/me` | вход | — |
| GET | `/api/users` | admin | — |
| POST | `/api/users` | admin | `{"username": "ivan", "password": "min 8 символов", "role": "seller"}` |

### Музыканты
| Метод | Адрес | Доступ | Тело запроса |
|---|---|---|---|
| GET | `/api/musicians` | все | — |
| GET | `/api/musicians/{id}` | все | — |
| POST | `/api/musicians` | admin | `{"full_name": "...", "country": "...", "instrument": "..."}` |
| PUT | `/api/musicians/{id}` | admin | то же |
| DELETE | `/api/musicians/{id}` | admin | — |

### Ансамбли
| Метод | Адрес | Доступ | Тело запроса |
|---|---|---|---|
| GET | `/api/ensembles` | все | — |
| GET | `/api/ensembles/{id}` | все | — |
| POST | `/api/ensembles` | admin | `{"name": "...", "genre": "...", "founded_year": 1998}` |
| PUT | `/api/ensembles/{id}` | admin | то же |
| DELETE | `/api/ensembles/{id}` | admin | — (409, если есть диски) |
| GET | `/api/ensembles/{id}/members` | все | — |
| POST | `/api/ensembles/{id}/members` | admin | `{"musician_id": 1, "role": "вокал"}` |

### Диски, цены, остатки
| Метод | Адрес | Доступ | Тело / параметры |
|---|---|---|---|
| GET | `/api/discs?q=снег&ensemble_id=1` | все | поиск и фильтр |
| GET | `/api/discs/{id}` | все | — |
| POST | `/api/discs` | admin | `{"title", "catalog_number", "ensemble_id", "label"?, "release_year"?, "tracklist"?}` |
| PUT | `/api/discs/{id}` | admin | то же |
| DELETE | `/api/discs/{id}` | admin | — (409, если были продажи) |
| GET | `/api/discs/{id}/prices` | все | — |
| POST | `/api/discs/{id}/prices` | admin | `{"amount": "990.00", "valid_from": "2026-11-01"}` |
| GET | `/api/stock` | вход | — |
| POST | `/api/discs/{id}/stock` | admin | `{"delta": 10}` — поступление, `{"delta": -2}` — списание |

Ответ по диску:
```json
{"id": 1, "title": "Первый снег", "catalog_number": "SV-001", "ensemble_id": 1,
 "ensemble_name": "Северный ветер", "label": null, "release_year": 2001,
 "tracklist": null, "current_price": "990.00", "stock_quantity": 12}
```

### Продажи и отчёты
| Метод | Адрес | Доступ | Тело / параметры |
|---|---|---|---|
| GET | `/api/sales?limit=50` | вход | — |
| POST | `/api/sales` | вход | `{"disc_id": 1, "quantity": 2}` |
| GET | `/api/reports/top-sellers?limit=10&date_from=2026-11-01&date_to=2026-11-30` | вход | лидеры продаж |
| GET | `/api/reports/low-stock?threshold=3` | вход | диски с остатком ≤ threshold, сначала самые дефицитные |

## Пример сессии (curl)

```bash
curl -s -c c.txt -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"<пароль>"}' http://127.0.0.1:8000/api/auth/login
curl -s -b c.txt -H "Content-Type: application/json" \
     -d '{"disc_id":1,"quantity":2}' http://127.0.0.1:8000/api/sales
curl -s -b c.txt http://127.0.0.1:8000/api/reports/top-sellers
```
