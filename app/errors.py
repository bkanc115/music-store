"""Ошибки приложения и единый формат ответа об ошибке.

Любая ошибка API возвращается как JSON:
    {"error": {"code": "not_found", "message": "...", "details": ...}}
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("app.errors")


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, details: object | None = None):
        super().__init__(message)
        self.message = message
        self.details = details


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class BusinessRuleError(AppError):
    """Нарушено правило предметной области (например, недостаточно дисков на складе)."""

    status_code = 422
    code = "business_rule_violation"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


def _body(code: str, message: str, details: object | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        log.warning("app_error code=%s path=%s message=%s", exc.code, request.url.path, exc.message)
        return JSONResponse(
            status_code=exc.status_code, content=_body(exc.code, exc.message, exc.details)
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]}
            for e in exc.errors()
        ]
        log.info("validation_error path=%s details=%s", request.url.path, details)
        return JSONResponse(
            status_code=422,
            content=_body("validation_error", "Некорректные данные запроса", details),
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error(request: Request, exc: IntegrityError):
        log.warning("integrity_error path=%s error=%s", request.url.path, exc.orig)
        return JSONResponse(
            status_code=409,
            content=_body("conflict", "Запись нарушает ограничения целостности данных"),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(status_code=exc.status_code, content=_body(code, str(exc.detail)))

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception):
        log.exception("unhandled_error path=%s", request.url.path)
        return JSONResponse(
            status_code=500, content=_body("internal_error", "Внутренняя ошибка сервера")
        )
