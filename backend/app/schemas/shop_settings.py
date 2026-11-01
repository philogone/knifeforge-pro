from pydantic import BaseModel, Field


class ShopSettingsUpdate(BaseModel):
    hourly_rate: float | None = Field(default=None, ge=0)
    default_margin_percent: float | None = Field(default=None, ge=0, lt=100)


class ShopSettingsOut(BaseModel):
    hourly_rate: float
    default_margin_percent: float

    model_config = {"from_attributes": True}
