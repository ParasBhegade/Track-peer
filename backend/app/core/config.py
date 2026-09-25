"""Application configuration via pydantic-settings.

Reads from environment variables / .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings.

    All values can be overridden by environment variables or a .env file
    in the backend/ directory.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────
    APP_ENV: str = "development"
    DEBUG: bool = True
    APP_VERSION: str = "0.1.0"

    # ── Database ─────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://habittracker:habittracker_dev@localhost:5432/habittracker"
    )

    # ── Redis ────────────────────────────────────────────
    REDIS_URL: str = "redis://127.0.0.1:6379/0"

    # ── JWT / Security ───────────────────────────────────
    JWT_SECRET: str = "CHANGE-ME-generate-a-random-64-char-string"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── CORS ─────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:8081", "http://localhost:19006"]

    # ── Email (Mailpit in dev) ───────────────────────────
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_FROM: str = "noreply@habittracker.dev"

    # ── Google OAuth ─────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""


# Singleton — import this everywhere
settings = Settings()
