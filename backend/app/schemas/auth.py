from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    # Plain string, not EmailStr: the address is only compared to ADMIN_EMAIL, and EmailStr rejects
    # reserved domains (admin@shop.local, admin@test.local) that are legitimate for a self-hosted admin.
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SetupRequest(BaseModel):
    """First-run account of the desktop build."""

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=10, max_length=72)  # bcrypt reads 72 bytes at most


class AuthStatus(BaseModel):
    needs_setup: bool
    demo: bool = False
