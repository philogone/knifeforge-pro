from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.database import get_db
from app.services import accounting_service as acc
from app.services.billing_service import is_franchise
from app.services.shop_settings_service import get_shop_settings

router = APIRouter(prefix="/api/admin/accounting", tags=["accounting"], dependencies=[Depends(require_admin)])

MAX_DAYS = 3 * 366 + 1


class RateOut(BaseModel):
    rate: float
    base: float
    vat: float


class PeriodOut(BaseModel):
    key: str
    start: date
    end: date
    invoiced_ht: float
    collected_goods: float
    collected_services: float
    vat: list[RateOut]


class SummaryOut(BaseModel):
    franchise: bool
    periods: list[PeriodOut]


def _range(start: date, end: date) -> None:
    if end < start:
        raise HTTPException(status_code=422, detail="The end date is before the start date")
    if (end - start).days > MAX_DAYS:
        raise HTTPException(status_code=422, detail="Three years at most per export")


def _file(content: str, name: str, media: str) -> Response:
    return Response(content.encode("utf-8"), media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/summary", response_model=SummaryOut)
def summary(start: date, end: date, granularity: Literal["month", "quarter"] = "month", db: Session = Depends(get_db)):
    """Turnover invoiced and collected, VAT due per rate, per month or quarter."""
    _range(start, end)
    periods = acc.period_summary(db, start, end, granularity)
    return {
        "franchise": is_franchise(get_shop_settings(db)),
        "periods": [
            {**{k: getattr(p, k) for k in ("key", "start", "end", "invoiced_ht", "collected_goods", "collected_services")},
             "vat": [{"rate": line.rate, "base": line.base, "vat": line.vat} for _, line in sorted(p.vat.items())]}
            for p in periods
        ],
    }


@router.get("/journal.txt")
def journal(start: date, end: date, payments: bool = Query(default=True), db: Session = Depends(get_db)):
    """Sales journal (and payments) in the FEC column layout, for the accountant's software."""
    _range(start, end)
    rows = acc.journal_rows(db, get_shop_settings(db), start, end, with_payments=payments)
    return _file(acc.journal_fec(rows), f"journal-ventes_{start:%Y%m%d}-{end:%Y%m%d}.txt", "text/plain; charset=utf-8")


@router.get("/sales.csv")
def sales(start: date, end: date, db: Session = Depends(get_db)):
    """One row per invoice / credit note, for a spreadsheet."""
    _range(start, end)
    return _file(acc.sales_csv(db, start, end), f"ventes_{start:%Y%m%d}-{end:%Y%m%d}.csv", "text/csv; charset=utf-8")
