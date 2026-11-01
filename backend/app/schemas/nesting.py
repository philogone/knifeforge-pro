from typing import Literal

from pydantic import BaseModel, Field


class NestingItemIn(BaseModel):
    design_id: int
    quantity: int = Field(default=1, ge=1, le=200)


class NestingRequest(BaseModel):
    material_id: int
    # Extra designs to cut, on top of whatever the selected orders need.
    items: list[NestingItemIn] = Field(default_factory=list, max_length=100)
    # None = every draft/confirmed order; [] = none on purpose (same convention
    # as the 1-D cutting optimizer).
    order_ids: list[int] | None = None
    spacing_mm: float = Field(default=2.0, ge=0, le=50)
    margin_mm: float = Field(default=3.0, ge=0, le=100)
    # Allowed part rotations in degrees. Restrict to [0, 180] to respect the
    # grain / rolling direction of the stock.
    rotations: list[float] | None = Field(default=None, max_length=12)


class NestingExportRequest(BaseModel):
    request: NestingRequest
    format: Literal["svg", "dxf"] = "svg"
    sheet_index: int = Field(default=0, ge=0)


class PlacementOut(BaseModel):
    design_id: int
    design_name: str
    part_name: str
    instance: int
    order_id: int | None
    customer_name: str | None
    x: float
    y: float
    rotation_deg: float
    # Exterior ring first, then interior rings (holes), each as [[x, y], ...]
    outline: list[list[list[float]]]


class SheetOut(BaseModel):
    index: int
    used_area_mm2: float
    utilization_pct: float
    placements: list[PlacementOut]


class UnplacedOut(BaseModel):
    design_id: int
    design_name: str
    part_name: str
    reason: Literal["too_large", "sheet_limit"]


class NestingResultOut(BaseModel):
    material_id: int
    material_name: str
    sheet_length_mm: float
    sheet_width_mm: float
    spacing_mm: float
    margin_mm: float
    total_parts: int
    placed_parts: int
    sheets_needed: int
    utilization_pct: float
    waste_area_mm2: float
    stock_sheets_available: float
    stock_sufficient: bool
    sheets: list[SheetOut]
    unplaced: list[UnplacedOut]


class NestingCandidateOrderOut(BaseModel):
    order_id: int
    customer_name: str
    status: str
    part_count: int


class NestingCandidateDesignOut(BaseModel):
    id: int
    name: str
    part_count: int
    knife_model_name: str | None

    model_config = {"from_attributes": True}


class NestingCandidatesOut(BaseModel):
    orders: list[NestingCandidateOrderOut]
    designs: list[NestingCandidateDesignOut]
