"""Точка входа приложения: uvicorn app.main:app"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from app import __version__
from app.config import DEFAULT_SECRET_KEY, get_settings
from app.db import engine
from app.errors import register_error_handlers
from app.logging_config import RequestLoggingMiddleware, setup_logging
from app.routers import api, web

settings = get_settings()
setup_logging(settings.log_level, settings.log_file)
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.secret_key == DEFAULT_SECRET_KEY:
        log.warning("SECRET_KEY не задан — используется небезопасное значение по умолчанию")
    log.info("application_started env=%s version=%s", settings.app_env, __version__)
    yield
    log.info("application_stopped")


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Учёт музыкантов, ансамблей, дисков, цен, продаж и остатков.",
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    max_age=settings.session_max_age,
    same_site="lax",
    https_only=settings.session_https_only,
)
app.add_middleware(RequestLoggingMiddleware)
register_error_handlers(app)

app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent / "static"),
    name="static",
)
app.include_router(api.router)
app.include_router(web.router)


@app.get("/health", tags=["service"])
def health():
    """Проверка работоспособности: приложение запущено и база данных отвечает."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        log.exception("health_check_failed")
        return JSONResponse(status_code=503, content={"status": "error", "database": "unavailable"})
    return {"status": "ok", "database": "ok", "version": __version__}
