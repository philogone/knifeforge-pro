from functools import lru_cache

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
