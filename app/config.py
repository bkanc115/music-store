"""Настройки приложения. Все значения берутся из переменных окружения (или файла .env)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Небезопасное значение-заглушка: при его использовании приложение пишет предупреждение в журнал.
DEFAULT_SECRET_KEY = "change-me-please"  # noqa: S105


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Music Store"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    # Строка подключения SQLAlchemy, например:
    # postgresql+psycopg://musicstore:secret@localhost:5432/musicstore
    database_url: str = "sqlite:///./musicstore.db"

    # Ключ подписи cookie-сессий. Обязательно переопределить в окружении.
    secret_key: str = Field(default=DEFAULT_SECRET_KEY, min_length=8)
    session_max_age: int = 8 * 60 * 60  # секунд

    log_level: str = "INFO"
    log_file: str | None = "logs/app.log"

    # Учётная запись администратора, создаваемая командой `make seed`
    admin_username: str = "admin"
    admin_password: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
