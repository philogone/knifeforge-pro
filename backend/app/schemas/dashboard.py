from datetime import date

from pydantic import BaseModel


class DueOrderOut(BaseModel):
    order_id: int
    customer_name: str
    due_date: date
    stage: str
    late: bool


class OrdersSummaryOut(BaseModel):
    by_status: dict[str, int]  # every status, zeros included
    by_stage: dict[str, int]  # active orders (draft + confirmed) per workshop stage
    active: int
    drafts_feasible: int  # drafts buildable with the current stock, each judged alone
    drafts_short: int
    late: int  # active orders past their promised date
    due_this_week: int  # due today or within 7 days
    upcoming: list[DueOrderOut]  # late first, then by due date


class MonthAmountOut(BaseModel):
    month: str  # YYYY-MM
    amount_ht: float


class FinanceSummaryOut(BaseModel):
    pipeline_revenue: float  # sale price of every active order line
    pipeline_cost: float  # materials + labour at the current costing
    pipeline_margin: float
    unpriced_lines: int  # active lines whose model has no sale price: the pipeline is understated
    invoiced_month_ht: float  # issued invoices minus credit notes, this calendar month
    invoiced_year_ht: float
    monthly: list[MonthAmountOut]  # the last 6 months, oldest first
    unpaid_count: int
    unpaid_ttc: float
    unpaid_overdue: int
    quotes_pending_count: int  # issued quotes neither accepted nor refused
    quotes_pending_ht: float


class StockLevelOut(BaseModel):
    material_id: int
    name: str
    unit: str
    quantity: float
    threshold: float
    value: float
    low: bool


class StockSummaryOut(BaseModel):
    total_value: float
    low_count: int
    materials: list[StockLevelOut]  # lowest relative level first


class DashboardOut(BaseModel):
    today: date
    orders: OrdersSummaryOut
    finance: FinanceSummaryOut
    stock: StockSummaryOut
