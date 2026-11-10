"""The home dashboard: one read-only summary of orders, money and stock.

Every figure is derived from the services the rest of the app already trusts, so the dashboard
never disagrees with the page it summarises:
- draft feasibility is `check_feasibility` (each draft judged alone, as on the Production page);
- the pipeline cost is `compute_full_costing` (materials + labour, as on a knife model);
- invoiced amounts are issued invoices minus issued credit notes, excluding tax, by issue date.
"""

from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.material import Material
from app.models.order import Order, OrderStage, OrderStatus
from app.models.sales_document import DocumentKind, DocumentStatus, SalesDocument
from app.schemas.dashboard import (
    DashboardOut,
    DueOrderOut,
    FinanceSummaryOut,
    MonthAmountOut,
    OrdersSummaryOut,
    StockLevelOut,
    StockSummaryOut,
)
from app.services.costing_service import compute_full_costing
from app.services.order_service import _UNIT_BY_DIMENSION, check_feasibility, load_order_with_relations
from app.services.shop_settings_service import get_shop_settings

ACTIVE = (OrderStatus.DRAFT, OrderStatus.CONFIRMED)
UPCOMING_LIMIT = 6


def _orders(db: Session, today: date, active: list[Order]) -> OrdersSummaryOut:
    by_status = Counter(status for (status,) in db.query(Order.status).all())
    by_stage = Counter(o.stage for o in active)

    feasible = short = 0
    for order in active:
        if order.status == OrderStatus.DRAFT and order.lines:
            if check_feasibility(db, order).feasible:
                feasible += 1
            else:
                short += 1

    dated = [o for o in active if o.due_date and o.stage != OrderStage.DELIVERED]
    late = [o for o in dated if o.due_date < today]
    week = [o for o in dated if today <= o.due_date <= today + timedelta(days=7)]
    upcoming = sorted(dated, key=lambda o: o.due_date)[:UPCOMING_LIMIT]

    return OrdersSummaryOut(
        by_status={s.value: by_status.get(s, 0) for s in OrderStatus},
        by_stage={s.value: by_stage.get(s, 0) for s in OrderStage},
        active=len(active),
        drafts_feasible=feasible,
        drafts_short=short,
        late=len(late),
        due_this_week=len(week),
        upcoming=[
            DueOrderOut(order_id=o.id, customer_name=o.customer_name, due_date=o.due_date, stage=o.stage.value, late=o.due_date < today)
            for o in upcoming
        ],
    )


def _months_back(today: date, n: int) -> list[str]:
    y, m = today.year, today.month
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out[::-1]


def _finance(db: Session, today: date, active: list[Order]) -> FinanceSummaryOut:
    shop = get_shop_settings(db)
    revenue = cost = 0.0
    unpriced = 0
    costing_cache: dict[int, float] = {}
    for order in active:
        for line in order.lines:
            model = line.knife_model
            if model.id not in costing_cache:
                costing_cache[model.id] = compute_full_costing(model, shop).cost_price
            revenue += line.quantity * (model.sale_price or 0.0)
            cost += line.quantity * costing_cache[model.id]
            if not model.sale_price:
                unpriced += 1

    issued = (
        db.query(SalesDocument)
        .filter(SalesDocument.status != DocumentStatus.DRAFT, SalesDocument.issue_date.isnot(None))
        .all()
    )
    months = _months_back(today, 6)
    per_month: dict[str, Decimal] = {m: Decimal("0") for m in months}
    month_key = f"{today.year:04d}-{today.month:02d}"
    year_total = Decimal("0")
    for doc in issued:
        if doc.kind == DocumentKind.QUOTE:
            continue
        signed = doc.total_ht if doc.kind == DocumentKind.INVOICE else -doc.total_ht
        key = f"{doc.issue_date.year:04d}-{doc.issue_date.month:02d}"
        if key in per_month:
            per_month[key] += signed
        if doc.issue_date.year == today.year:
            year_total += signed

    unpaid = [d for d in issued if d.kind == DocumentKind.INVOICE and d.status == DocumentStatus.ISSUED]
    quotes = [d for d in issued if d.kind == DocumentKind.QUOTE and d.status == DocumentStatus.ISSUED]

    return FinanceSummaryOut(
        pipeline_revenue=round(revenue, 2),
        pipeline_cost=round(cost, 2),
        pipeline_margin=round(revenue - cost, 2),
        unpriced_lines=unpriced,
        invoiced_month_ht=float(per_month[month_key]),
        invoiced_year_ht=float(year_total),
        monthly=[MonthAmountOut(month=m, amount_ht=float(per_month[m])) for m in months],
        unpaid_count=len(unpaid),
        unpaid_ttc=float(sum((d.total_ttc for d in unpaid), Decimal("0"))),
        unpaid_overdue=sum(1 for d in unpaid if d.due_date and d.due_date < today),
        quotes_pending_count=len(quotes),
        quotes_pending_ht=float(sum((d.total_ht for d in quotes), Decimal("0"))),
    )


def _stock(db: Session) -> StockSummaryOut:
    materials = db.query(Material).all()
    levels = [
        StockLevelOut(
            material_id=m.id,
            name=m.name,
            unit=_UNIT_BY_DIMENSION[m.dimension_type],
            quantity=round(m.quantity_in_stock, 4),
            threshold=round(m.low_stock_threshold, 4),
            value=round(m.quantity_in_stock * m.unit_cost, 2),
            low=m.low_stock_threshold > 0 and m.quantity_in_stock <= m.low_stock_threshold,
        )
        for m in materials
    ]

    def relative(level: StockLevelOut) -> float:
        # level against the alert threshold; materials without a threshold sort last
        return level.quantity / level.threshold if level.threshold > 0 else float("inf")

    levels.sort(key=lambda lv: (relative(lv), lv.name))
    return StockSummaryOut(
        total_value=round(sum(lv.value for lv in levels), 2),
        low_count=sum(1 for lv in levels if lv.low),
        materials=levels,
    )


def build_dashboard(db: Session, today: date | None = None) -> DashboardOut:
    today = today or date.today()
    ids = [oid for (oid,) in db.query(Order.id).filter(Order.status.in_(ACTIVE)).all()]
    active = [load_order_with_relations(db, oid) for oid in ids]
    return DashboardOut(today=today, orders=_orders(db, today, active), finance=_finance(db, today, active), stock=_stock(db))
