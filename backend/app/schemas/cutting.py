from pydantic import BaseModel


class CutPieceOut(BaseModel):
    length_mm: float
    order_id: int
    customer_name: str
    knife_model_name: str


class CutBarOut(BaseModel):
    pieces: list[CutPieceOut]
    waste_mm: float


class CuttingPlanOut(BaseModel):
    material_id: int
    material_name: str
    kerf_mm: float
    stock_length_mm: float
    total_pieces: int
    bars_needed: int
    total_waste_mm: float
    waste_percentage: float
    bars: list[CutBarOut]


class CuttingOptimizeRequest(BaseModel):
    order_ids: list[int] | None = None


class CandidateOrderOut(BaseModel):
    order_id: int
    customer_name: str
    status: str
    piece_count: int
    total_length_mm: float
