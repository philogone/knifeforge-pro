from pydantic import BaseModel, EmailStr, Field, field_validator

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
    account_customers: str | None = Field(default=None, pattern=r"^[0-9A-Za-z]{1,20}$")
    account_sales_goods: str | None = Field(default=None, pattern=r"^[0-9A-Za-z]{1,20}$")
    account_sales_services: str | None = Field(default=None, pattern=r"^[0-9A-Za-z]{1,20}$")
    account_vat: str | None = Field(default=None, pattern=r"^[0-9A-Za-z]{1,20}$")
    account_deposits: str | None = Field(default=None, pattern=r"^[0-9A-Za-z]{1,20}$")
    account_bank: str | None = Field(default=None, pattern=r"^[0-9A-Za-z]{1,20}$")
    # "" goes back to the built-in wording
    email_send_template: str | None = Field(default=None, max_length=4000)
    reminder_templates: dict[str, str] | None = None
    trade: str | None = Field(default=None, pattern="^(knifemaker|blacksmith)$")

    @field_validator("reminder_templates")
    @classmethod
    def _three_levels(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return value
        if set(value) - {"1", "2", "3"} or any(len(v) > 4000 for v in value.values()):
            raise ValueError("reminder templates: levels 1, 2 and 3, 4000 characters at most")
        return {k: v for k, v in value.items() if v.strip()}

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
    account_customers: str = "411000"
    account_sales_goods: str = "707000"
    account_sales_services: str = "706000"
    account_vat: str = "445710"
    account_deposits: str = "419100"
    account_bank: str = "512000"
    email_send_template: str | None = None
    reminder_templates: dict[str, str] | None = None
    trade: str = "knifemaker"

    model_config = {"from_attributes": True}


class AutoBackupOut(BaseModel):
    enabled: bool
    directory: str
    keep_days: int
    last_at: str | None = None
    last_file: str | None = None
    last_error: str | None = None


class AutoBackupUpdate(BaseModel):
    enabled: bool = True
    directory: str = Field(min_length=1, max_length=1000)
    keep_days: int = Field(default=30, ge=1, le=3650)


class MailSettingsOut(BaseModel):
    configured: bool
    # desktop build: set from Settings; Docker: from the server's environment (read-only here)
    editable: bool
    host: str
    port: int
    security: str
    user: str
    from_address: str
    from_name: str
    password_set: bool


class MailSettingsUpdate(BaseModel):
    host: str = Field(max_length=255)
    port: int = Field(default=587, ge=1, le=65535)
    security: str = Field(default="starttls", pattern="^(starttls|ssl|none)$")
    user: str = Field(default="", max_length=255)
    # None keeps the stored password; "" removes it
    password: str | None = Field(default=None, max_length=500)
    from_address: str = Field(default="", max_length=255)
    from_name: str = Field(default="", max_length=120)


class MailTestIn(BaseModel):
    to: EmailStr


class StageIn(BaseModel):
    key: str | None = Field(default=None, max_length=40)  # None: a new stage, key made from the label
    label: str | None = Field(default=None, max_length=60)  # None: a built-in stage, translated


class StagesIn(BaseModel):
    stages: list[StageIn] = Field(min_length=2, max_length=16)


class StageOut(BaseModel):
    key: str
    label: str | None
    used: int = 0  # active orders at this stage
