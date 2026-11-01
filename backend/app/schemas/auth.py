from pydantic import BaseModel


class LoginRequest(BaseModel):
    # Plain string, not EmailStr: the address is only compared to ADMIN_EMAIL, and EmailStr rejects
    # reserved domains (admin@shop.local, admin@test.local) that are legitimate for a self-hosted admin.
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
