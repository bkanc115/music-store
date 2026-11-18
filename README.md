# Музыкальный магазин

Веб-приложение для учёта музыкантов, ансамблей, дисков, цен, продаж и остатков.
Есть каталог, оформление продаж с контролем остатков, история цен и отчёт «лидеры продаж».

**Стек:** Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 17, Jinja2, pytest, ruff.

## Возможности

- Каталог дисков с поиском, ценой и остатком (доступен без входа).
- Музыканты, ансамбли и их состав (связь многие-ко-многим).
- История цен: цена задаётся с даты начала действия.
- Продажи: проверяется остаток, остаток уменьшается, фиксируется действующая цена.
- Отчёт «лидеры продаж» за период.
- Авторизация: роли `admin` (управление каталогом, ценами, остатками, пользователями) и
  `seller` (продажи, отчёты).
- Единый формат ошибок, журналирование с идентификатором запроса, `/health`.

## Быстрый старт

Нужны Python 3.12+, Docker (для PostgreSQL) и GNU make.

```bash
make setup     # venv, зависимости, .env из .env.example
# отредактируйте .env: POSTGRES_PASSWORD, DATABASE_URL, SECRET_KEY, ADMIN_PASSWORD
make up        # PostgreSQL в контейнере (только 127.0.0.1:5432)
make migrate   # создать схему БД
make seed      # администратор из .env + демо-каталог
make run       # http://127.0.0.1:8000
```

Без make (Windows):
```powershell
py -m venv .venv; .\.venv\Scripts\pip install -r requirements-dev.txt
docker compose up -d --wait db
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m app.seed --demo
.\.venv\Scripts\python -m app
```

## Команды

| Команда | Назначение |
|---|---|
| `make setup` | первоначальная настройка |
| `make run` | локальный запуск |
| `make test` | автотесты |
| `make quality` | форматирование и статический анализ |
| `make format` | автоформатирование |
| `make migrate` | применение миграций |
| `make seed` | администратор и демо-данные |
| `make verify` | **полный набор обязательных проверок** (перед каждым PR) |
| `make up` / `make down` | запуск / остановка PostgreSQL в Docker |

## Конфигурация

Все настройки задаются переменными окружения (или файлом `.env`, который **не хранится в
репозитории**). Шаблон — [`.env.example`](.env.example).

| Переменная | По умолчанию | Описание |
|---|---|---|
| `APP_ENV` | `development` | `development` / `production` (в production нет автоперезагрузки кода) |
| `SESSION_HTTPS_ONLY` | `false` | cookie сессии только по HTTPS (включить при наличии TLS) |
| `APP_HOST`, `APP_PORT` | `127.0.0.1`, `8000` | адрес и порт сервера |
| `DATABASE_URL` | `sqlite:///./musicstore.db` | строка подключения SQLAlchemy |
| `SECRET_KEY` | заглушка | ключ подписи сессий (**обязательно задать**) |
| `LOG_LEVEL` | `INFO` | уровень журналирования |
| `LOG_FILE` | `logs/app.log` | файл журнала (пусто — только консоль) |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | `admin`, — | администратор для `make seed` |

## Журналирование

Журнал пишется в stdout и в `logs/app.log` (ротация: 5 файлов по 5 МБ). Формат:

```
2026-11-19 02:00:44 INFO    [3f9c1a2b7d4e] app.http: method=POST path=/api/sales status=201 duration_ms=12.4
2026-11-19 02:00:51 WARNING [a81d0c55e210] app.errors: app_error code=business_rule_violation path=/api/sales ...
```

В квадратных скобках идентификатор запроса. Он же возвращается клиенту в заголовке
`X-Request-ID`, поэтому по ответу с ошибкой легко найти нужные записи в журнале.
Необработанные исключения пишутся с полным стеком (уровень `ERROR`).

## Структура

```
app/
  main.py            создание приложения, middleware, /health
  config.py          настройки из переменных окружения
  db.py, models.py   подключение к БД и ORM-модели
  schemas.py         валидация запросов и формат ответов
  services.py        бизнес-логика и правила предметной области
  security.py        пароли, сессии, проверка ролей
  errors.py          ошибки и единый формат ответов об ошибках
  logging_config.py  журналирование и X-Request-ID
  routers/api.py     JSON API
  routers/web.py     HTML-страницы
  templates/, static/
alembic/             миграции БД
tests/               автотесты
docs/                описание API и схема данных
```

## Документация

- [Описание API](docs/api.md), интерактивно: `/docs`
- [Схема данных](docs/schema.md)
- [Правила внесения изменений](CONTRIBUTING.md)
- [История версий](CHANGELOG.md)
