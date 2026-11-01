from pydantic import BaseModel


class CostLineOut(BaseModel):
    material_id: int
    material_name: str
    role: str
    consumption: float
    unit: str
    unit_cost: float
    line_cost: float


class CostBreakdownOut(BaseModel):
    knife_model_id: int
    knife_model_name: str
    lines: list[CostLineOut]
    total_material_cost: float
    labor_hours: float
    hourly_rate: float
    labor_cost: float
    cost_price: float
    margin_percent: float
    suggested_sale_price: float
    current_sale_price: float
