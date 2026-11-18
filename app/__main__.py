"""Запуск сервера: python -m app (адрес и порт берутся из APP_HOST / APP_PORT)."""

import uvicorn

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
        proxy_headers=True,
    )


if __name__ == "__main__":
    main()
