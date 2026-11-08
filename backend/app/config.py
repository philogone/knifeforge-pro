from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "production"
    debug: bool = False
    frontend_url: str = "http://localhost:8080"

    secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24 * 7

    database_url: str
    redis_url: str = "redis://redis:6379/0"

    admin_email: str
    admin_password_hash: str

    rate_limit_per_minute: int = 60

    seed_mock_data_on_startup: bool = True

    @field_validator("secret_key")
    @classmethod
    def _secret_is_real(cls, value: str) -> str:
        """Tokens are signed with this key: a guessable one lets anyone forge an admin session."""
        placeholders = {"change-me", "changeme", "secret", "your-secret-key", "<64 caractères hexadécimaux aléatoires>"}
        if value.strip().lower() in placeholders or value.strip().lower().startswith("change-me") or len(value.strip()) < 16:
            raise ValueError("SECRET_KEY is too short or a placeholder: generate one with `python -c \"import secrets; print(secrets.token_hex(32))\"`")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
