from pathlib import Path

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status

from app.config import get_settings
from app.core import desktop
from app.core.rate_limit import rate_limit_login
from app.core.security import create_access_token, verify_password
from app.schemas.auth import AuthStatus, LoginRequest, SetupRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


def _needs_setup() -> bool:
    # only the desktop build creates its account in the app; Docker reads it from the environment
    return settings.desktop and not settings.admin_password_hash


@router.get("/status", response_model=AuthStatus)
def auth_status() -> AuthStatus:
    return AuthStatus(needs_setup=_needs_setup(), demo=settings.demo)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, _rl=Depends(rate_limit_login)) -> TokenResponse:
    if _needs_setup():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Create the account first")
    if settings.demo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Read-only demo")
    if payload.email != settings.admin_email or not verify_password(payload.password, settings.admin_password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(payload.email))


@router.post("/demo", response_model=TokenResponse)
def demo(_rl=Depends(rate_limit_login)) -> TokenResponse:
    """Public demo only: enter the fictitious workshop without a password (read-only)."""
    if not settings.demo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return TokenResponse(access_token=create_access_token(settings.admin_email))


@router.post("/setup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def setup(payload: SetupRequest, _rl=Depends(rate_limit_login)) -> TokenResponse:
    """Create the workshop's account on the first launch of the desktop build. Refused once an
    account exists: the server only listens on 127.0.0.1, and from then on the password is
    changed by whoever can edit the data folder (see the README)."""
    if not _needs_setup():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The account already exists")
    email = payload.email.strip()
    password_hash = bcrypt.hashpw(payload.password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")
    desktop.update_config(Path(settings.data_dir), admin_email=email, admin_password_hash=password_hash)
    # the settings object is shared (cached): login and token checks see the account at once
    settings.admin_email = email
    settings.admin_password_hash = password_hash
    return TokenResponse(access_token=create_access_token(email))
