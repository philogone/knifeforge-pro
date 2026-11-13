from typing import Literal

from pydantic import BaseModel, Field


class FeatureOut(BaseModel):
    key: str
    label: str
    nominal_mm: float
    kind: Literal["outside", "inside", "pitch"]
    how: str


class CalibrationIn(BaseModel):
    kerf_used_mm: float = Field(ge=0, le=3)
    measurements: dict[str, float] = Field(min_length=1, max_length=20)


class FeatureResultOut(BaseModel):
    key: str
    label: str
    kind: Literal["outside", "inside", "pitch"]
    nominal_mm: float
    measured_mm: float
    error_mm: float
    kerf_estimate_mm: float | None
    within_tolerance: bool


class AnalysisOut(BaseModel):
    kerf_used_mm: float
    features: list[FeatureResultOut]
    kerf_estimate_mm: float | None
    kerf_spread_mm: float | None
    suggested_kerf_mm: float | None
    scale_error_ppm: float | None
    max_error_mm: float
    residual_mm: float | None
    within_tolerance: bool
    # ok · use_suggested · inconsistent · scale · negative_kerf · recheck
    advice: list[str]
