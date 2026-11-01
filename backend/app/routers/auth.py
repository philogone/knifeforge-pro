from fastapi import APIRouter, Depends, HTTPException, status

from app.config import get_settings
from app.core.rate_limit import rate_limit_login
from app.core.security import create_access_token, verify_password
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, _rl=Depends(rate_limit_login)) -> TokenResponse:
    if payload.email != settings.admin_email or not verify_password(payload.password, settings.admin_password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(payload.email))
