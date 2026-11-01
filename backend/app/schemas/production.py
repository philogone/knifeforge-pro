from pydantic import BaseModel


class MaterialDemandOut(BaseModel):
    material_id: int
    material_name: str
    unit: str
    available: float
    demand: float
    shortfall: float


class OrderSummaryOut(BaseModel):
    order_id: int
    customer_name: str
    feasible: bool
    lines: list[str]


class ProductionOverviewOut(BaseModel):
    materials: list[MaterialDemandOut]
    orders: list[OrderSummaryOut]
