from pydantic import BaseModel, Field, field_validator

LOGO_PREFIXES = ("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/svg+xml;base64,")
# ~300 KB of image once base64-decoded: plenty for a title-block logo, small enough to embed
LOGO_MAX_CHARS = 400_000


class ShopSettingsUpdate(BaseModel):
    hourly_rate: float | None = Field(default=None, ge=0)
    default_margin_percent: float | None = Field(default=None, ge=0, lt=100)
    workshop_name: str | None = Field(default=None, max_length=120)
    workshop_contact: str | None = Field(default=None, max_length=200)
    # "" removes the logo
    workshop_logo: str | None = Field(default=None, max_length=LOGO_MAX_CHARS)
    onboarding_done: bool | None = None

    @field_validator("workshop_logo")
    @classmethod
    def _logo_is_an_image(cls, value: str | None) -> str | None:
        if value and not value.startswith(LOGO_PREFIXES):
            raise ValueError("logo must be a base64 PNG, JPEG or SVG data URL")
        return value


class ShopSettingsOut(BaseModel):
    hourly_rate: float
    default_margin_percent: float
    workshop_name: str | None = None
    workshop_contact: str | None = None
    workshop_logo: str | None = None
    onboarding_done: bool = False

    model_config = {"from_attributes": True}
