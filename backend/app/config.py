from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# the public demo's only "account": nobody signs in with it, visitors enter without a password
DEMO_EMAIL = "demo@knifeforge.invalid"


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

    # Docker passes the admin account through the environment. The desktop build leaves both
    # empty until the first-run screen creates them (see app/core/desktop.py).
    admin_email: str = ""
    admin_password_hash: str = ""

    rate_limit_per_minute: int = 60

    seed_mock_data_on_startup: bool = True

    # desktop build (Windows installer): one workshop, one machine, SQLite, no Docker
    desktop: bool = False
    data_dir: str = ""
    # built interface served by the backend itself (desktop); nginx serves it under Docker
    frontend_dist: str = ""

    # outgoing mail (the workshop's own SMTP account: its provider, its address). Docker: the
    # environment; desktop build: config.json, set from Settings. Never stored in the database.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_security: str = "starttls"  # starttls · ssl · none
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""  # sender address; the user name when empty
    smtp_from_name: str = ""

    # public demo: fictitious data rebuilt at each start, entered without a password, read-only
    # (app/services/demo_service.py)
    demo: bool = False

    @field_validator("secret_key")
    @classmethod
    def _secret_is_real(cls, value: str) -> str:
        """Tokens are signed with this key: a guessable one lets anyone forge an admin session."""
        placeholders = {"change-me", "changeme", "secret", "your-secret-key", "<64 caractères hexadécimaux aléatoires>"}
        if value.strip().lower() in placeholders or value.strip().lower().startswith("change-me") or len(value.strip()) < 16:
            raise ValueError("SECRET_KEY is too short or a placeholder: generate one with `python -c \"import secrets; print(secrets.token_hex(32))\"`")
        return value


    @model_validator(mode="after")
    def _admin_account_outside_desktop(self) -> "Settings":
        if self.demo:
            self.admin_email, self.admin_password_hash = DEMO_EMAIL, ""
            return self
        if not self.desktop and not (self.admin_email and self.admin_password_hash):
            raise ValueError("ADMIN_EMAIL and ADMIN_PASSWORD_HASH are required (see .env.example)")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
