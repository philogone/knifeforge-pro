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
    legal_name: str | None = Field(default=None, max_length=150)
    address_line1: str | None = Field(default=None, max_length=200)
    postal_code: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    siren: str | None = Field(default=None, pattern=r"^(\d{9})?$")
    siret: str | None = Field(default=None, pattern=r"^(\d{14})?$")
    vat_regime: str | None = Field(default=None, pattern="^(franchise|normal)$")
    vat_number: str | None = Field(default=None, max_length=20)
    default_vat_rate: float | None = Field(default=None, ge=0, le=100)
    trade_register: str | None = Field(default=None, max_length=120)
    iban: str | None = Field(default=None, max_length=34)
    bic: str | None = Field(default=None, max_length=11)
    payment_terms_days: int | None = Field(default=None, ge=0, le=120)
    late_penalty_text: str | None = Field(default=None, max_length=300)
    quote_validity_days: int | None = Field(default=None, ge=1, le=365)

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
    legal_name: str | None = None
    address_line1: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country: str = "FR"
    siren: str | None = None
    siret: str | None = None
    vat_regime: str = "franchise"
    vat_number: str | None = None
    default_vat_rate: float = 20.0
    trade_register: str | None = None
    iban: str | None = None
    bic: str | None = None
    payment_terms_days: int = 30
    late_penalty_text: str | None = None
    quote_validity_days: int = 30

    model_config = {"from_attributes": True}
