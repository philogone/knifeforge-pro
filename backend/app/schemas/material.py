from datetime import datetime

from pydantic import BaseModel, Field

from app.models.material import DimensionType, MaterialCategory, MetalType


class MaterialCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    category: MaterialCategory
    dimension_type: DimensionType
    metal_type: MetalType | None = None
    steel_grade: str | None = Field(default=None, max_length=50)
    wood_species: str | None = Field(default=None, max_length=100)
    wood_grade: str | None = Field(default=None, max_length=100)
    piece_type: str | None = Field(default=None, max_length=150)
    standard_length_mm: float | None = Field(default=None, gt=0)
    standard_width_mm: float | None = Field(default=None, gt=0)
    standard_thickness_mm: float | None = Field(default=None, gt=0)
    kerf_mm: float = Field(default=2.0, ge=0)
    saw_blade_id: int | None = None
    quantity_in_stock: float = Field(default=0.0, ge=0)
    low_stock_threshold: float = Field(default=0.0, ge=0)
    unit_cost: float = Field(
        default=0.0, ge=0, description="Landed cost per base unit: EUR/mm for length, EUR/mm^2 for area, EUR/unit for count."
    )


class MaterialUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    category: MaterialCategory | None = None
    metal_type: MetalType | None = None
    steel_grade: str | None = Field(default=None, max_length=50)
    wood_species: str | None = Field(default=None, max_length=100)
    wood_grade: str | None = Field(default=None, max_length=100)
    piece_type: str | None = Field(default=None, max_length=150)
    standard_length_mm: float | None = Field(default=None, gt=0)
    standard_width_mm: float | None = Field(default=None, gt=0)
    standard_thickness_mm: float | None = Field(default=None, gt=0)
    kerf_mm: float | None = Field(default=None, ge=0)
    saw_blade_id: int | None = None
    low_stock_threshold: float | None = Field(default=None, ge=0)
    unit_cost: float | None = Field(default=None, ge=0)


class MaterialRestock(BaseModel):
    quantity_delta: float = Field(description="Amount to add to stock, in the material's own unit (mm / mm^2 / count). Use a negative value to correct stock downward.")
    purchase_price: float | None = Field(
        default=None, ge=0, description="Total price paid for this batch (before shipping). Provide together with a positive quantity_delta to update the weighted-average unit_cost."
    )
    shipping_cost: float | None = Field(default=None, ge=0, description="Total shipping cost for this batch, blended into the weighted-average unit_cost alongside purchase_price.")


class MaterialOut(BaseModel):
    id: int
    name: str
    category: MaterialCategory
    dimension_type: DimensionType
    metal_type: MetalType | None
    steel_grade: str | None
    wood_species: str | None
    wood_grade: str | None
    piece_type: str | None
    standard_length_mm: float | None
    standard_width_mm: float | None
    standard_thickness_mm: float | None
    kerf_mm: float
    saw_blade_id: int | None
    saw_blade_name: str | None = None
    quantity_in_stock: float
    low_stock_threshold: float
    unit_cost: float
    is_mock: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class YieldCalcRequest(BaseModel):
    blank_length_mm: float = Field(gt=0)
    blank_width_mm: float | None = Field(default=None, gt=0, description="Required for AREA materials")
    quantity_needed: int = Field(default=1, ge=1)


class YieldCalcResult(BaseModel):
    pieces_per_stock_unit: int
    waste_per_stock_unit: float
    waste_percentage: float
    stock_units_needed: int
    total_consumption: float
    unit: str
    # Layout info for rendering a visual cutting diagram. Populated for
    # LENGTH (grid_cols = pieces_per_stock_unit, grid_rows = 1) and AREA
    # (grid_cols x grid_rows = simple shelf-packing grid); null for COUNT.
    grid_cols: int | None = None
    grid_rows: int | None = None
    rotated: bool = False
