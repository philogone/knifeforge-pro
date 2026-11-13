"""What the accountant needs, from the issued documents and the payments.

1. **Journal des ventes** in the column layout of the FEC (fichier des écritures comptables,
   art. A47 A-1 du LPF), which every French accounting package imports: one balanced entry per
   invoice / credit note (journal VE), and optionally one per payment (journal BQ). It is the
   sales part of the books, not a legal FEC (that one comes from the accounting software and
   holds every journal).
2. **Sales list** (CSV for a spreadsheet): one row per document, HT and VAT per rate, deposits
   deducted, paid, still due.
3. **Period summary**: turnover invoiced and **collected** (what a micro-entrepreneur declares to
   the URSSAF, split goods / services), and the VAT due per rate in the period:
   - goods: due on delivery (delivery date), less the VAT of the deposits already declared;
   - services, and every deposit (goods too, since 2023): due on payment, pro rata;
   - an invoice under the "débits" option: due on issue;
   - mixed invoices are counted as goods (lines do not say which part is a service): to be
     checked with the accountant; credit notes are counted on their issue date.

Amounts are Decimals rounded to the cent; nothing here writes to the database.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.sales_document import DocumentKind, DocumentStatus, OperationNature, PaymentMethod, SalesDocument
from app.models.shop_settings import ShopSettings
from app.services.billing_service import money, vat_breakdown

ZERO = Decimal("0")
FEC_COLUMNS = [
    "JournalCode", "JournalLib", "EcritureNum", "EcritureDate", "CompteNum", "CompteLib", "CompAuxNum", "CompAuxLib",
    "PieceRef", "PieceDate", "EcritureLib", "Debit", "Credit", "EcritureLet", "DateLet", "ValidDate", "Montantdevise", "Idevise",
]
METHOD_LABEL = {
    PaymentMethod.TRANSFER: "virement",
    PaymentMethod.CARD: "carte",
    PaymentMethod.CHEQUE: "chèque",
    PaymentMethod.CASH: "espèces",
    PaymentMethod.OTHER: "autre",
}


def _fr(value: Decimal) -> str:
    return f"{money(value):.2f}".replace(".", ",")


def _ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


def issued_documents(db: Session, start: date, end: date) -> list[SalesDocument]:
    return (
        db.query(SalesDocument)
        .filter(
            SalesDocument.kind != DocumentKind.QUOTE,
            SalesDocument.status != DocumentStatus.DRAFT,
            SalesDocument.issue_date >= start,
            SalesDocument.issue_date <= end,
        )
        .order_by(SalesDocument.issue_date, SalesDocument.number)
        .all()
    )


def _buyer(doc: SalesDocument) -> str:
    return (doc.buyer_snapshot or {}).get("name") or ""


def _aux(doc: SalesDocument) -> str:
    return f"C{doc.customer_id:05d}" if doc.customer_id else "C00000"


def _deposits(db: Session, doc: SalesDocument) -> list[SalesDocument]:
    numbers = [ref["number"] for ref in doc.prepaid_refs or []]
    if not numbers:
        return []
    return db.query(SalesDocument).filter(SalesDocument.kind == DocumentKind.INVOICE, SalesDocument.number.in_(numbers)).all()


# ------------------------------------------------------------------------------------------
# 1. Sales journal, FEC layout
# ------------------------------------------------------------------------------------------


def journal_rows(db: Session, settings: ShopSettings, start: date, end: date, with_payments: bool = True) -> list[dict]:
    rows: list[dict] = []
    entry = 0

    def add(journal: str, journal_label: str, num: str, on: date, account: str, account_label: str, piece: str, label: str,
            debit: Decimal, credit: Decimal, aux: str = "", aux_label: str = "") -> None:
        rows.append({
            "JournalCode": journal, "JournalLib": journal_label, "EcritureNum": num, "EcritureDate": _ymd(on),
            "CompteNum": account, "CompteLib": account_label, "CompAuxNum": aux, "CompAuxLib": aux_label,
            "PieceRef": piece, "PieceDate": _ymd(on), "EcritureLib": label[:100],
            "Debit": _fr(debit), "Credit": _fr(credit), "EcritureLet": "", "DateLet": "", "ValidDate": "",
            "Montantdevise": "", "Idevise": "",
        })

    for doc in issued_documents(db, start, end):
        entry += 1
        num = f"VE{entry:05d}"
        sign = -1 if doc.kind == DocumentKind.CREDIT_NOTE else 1
        title = ("Avoir" if sign < 0 else "Facture d'acompte" if doc.is_deposit else "Facture") + f" {doc.number} {_buyer(doc)}"

        def side(amount: Decimal, debit_when_invoice: bool) -> tuple[Decimal, Decimal]:
            amount = money(amount)
            debit = (sign > 0) == debit_when_invoice
            return (amount, ZERO) if debit else (ZERO, amount)

        add("VE", "Ventes", num, doc.issue_date, settings.account_customers, "Clients", doc.number, title,
            *side(doc.total_ttc, True), _aux(doc), _buyer(doc))
        if doc.is_deposit:
            sales_account, sales_label = settings.account_deposits, "Avances et acomptes reçus"
        elif doc.nature == OperationNature.SERVICES:
            sales_account, sales_label = settings.account_sales_services, "Prestations de services"
        else:
            sales_account, sales_label = settings.account_sales_goods, "Ventes de marchandises"
        for b in vat_breakdown(doc):
            if b.base:
                add("VE", "Ventes", num, doc.issue_date, sales_account, sales_label, doc.number, title, *side(b.base, False))
            if b.amount:
                add("VE", "Ventes", num, doc.issue_date, settings.account_vat, f"TVA collectée {b.rate:g} %", doc.number, title,
                    *side(b.amount, False))
        # a final invoice clears the deposits it deducts: their HT leaves the advances account,
        # their VAT (declared when the deposit was paid) is not collected twice
        for deposit in _deposits(db, doc):
            label = f"Acompte {deposit.number} déduit"
            add("VE", "Ventes", num, doc.issue_date, settings.account_customers, "Clients", doc.number, label,
                *side(deposit.total_ttc, False), _aux(doc), _buyer(doc))
            for b in vat_breakdown(deposit):
                if b.base:
                    add("VE", "Ventes", num, doc.issue_date, settings.account_deposits, "Avances et acomptes reçus", doc.number,
                        label, *side(b.base, True))
                if b.amount:
                    add("VE", "Ventes", num, doc.issue_date, settings.account_vat, f"TVA collectée {b.rate:g} %", doc.number,
                        label, *side(b.amount, True))

    if with_payments:
        payments = [(p, d) for d in _documents_with_payments(db) for p in d.payments if start <= p.paid_on <= end]
        for p, doc in sorted(payments, key=lambda x: (x[0].paid_on, x[0].id)):
            entry += 1
            num = f"BQ{entry:05d}"
            refund = doc.kind == DocumentKind.CREDIT_NOTE
            label = f"{'Remboursement' if refund else 'Règlement'} {doc.number} {_buyer(doc)} ({METHOD_LABEL[p.method]})"
            amount = money(p.amount)
            add("BQ", "Banque", num, p.paid_on, settings.account_bank, "Banque", doc.number, label,
                *((ZERO, amount) if refund else (amount, ZERO)))
            add("BQ", "Banque", num, p.paid_on, settings.account_customers, "Clients", doc.number, label,
                *((amount, ZERO) if refund else (ZERO, amount)), _aux(doc), _buyer(doc))
    return rows


def _documents_with_payments(db: Session) -> list[SalesDocument]:
    return db.query(SalesDocument).filter(SalesDocument.payments.any()).all()


def journal_fec(rows: list[dict]) -> str:
    """Pipe-separated, decimal comma, one header line: the FEC text layout."""
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=FEC_COLUMNS, delimiter="|", lineterminator="\r\n", quoting=csv.QUOTE_NONE, escapechar="\\")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: str(v).replace("|", "/") for k, v in row.items()})
    return out.getvalue()


# ------------------------------------------------------------------------------------------
# 2. Sales list
# ------------------------------------------------------------------------------------------


def sales_csv(db: Session, start: date, end: date) -> str:
    from app.services.billing_service import amount_paid, balance_due

    docs = issued_documents(db, start, end)
    rates = sorted({b.rate for d in docs for b in vat_breakdown(d)})
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", lineterminator="\r\n")
    header = ["Date", "Numéro", "Type", "Client", "SIREN client", "Nature"]
    for r in rates:
        header += [f"Base HT {r:g} %", f"TVA {r:g} %"]
    header += ["Total HT", "Total TVA", "Total TTC", "Acomptes déduits", "Encaissé", "Reste dû", "Échéance", "Statut"]
    writer.writerow(header)
    kind_label = {DocumentKind.INVOICE: "Facture", DocumentKind.CREDIT_NOTE: "Avoir"}
    nature_label = {OperationNature.GOODS: "Biens", OperationNature.SERVICES: "Services", OperationNature.MIXED: "Mixte"}
    status_label = {DocumentStatus.ISSUED: "À encaisser", DocumentStatus.PAID: "Payée"}
    for d in docs:
        sign = -1 if d.kind == DocumentKind.CREDIT_NOTE else 1
        by_rate = {b.rate: b for b in vat_breakdown(d)}
        row = [d.issue_date.strftime("%d/%m/%Y"), d.number, "Facture d'acompte" if d.is_deposit else kind_label[d.kind],
               _buyer(d), (d.buyer_snapshot or {}).get("siren") or "", nature_label[d.nature]]
        for r in rates:
            b = by_rate.get(r)
            row += [_fr(sign * b.base) if b else "", _fr(sign * b.amount) if b else ""]
        row += [_fr(sign * d.total_ht), _fr(sign * d.total_vat), _fr(sign * d.total_ttc), _fr(d.prepaid_amount or ZERO),
                _fr(amount_paid(d)), _fr(balance_due(d)), d.due_date.strftime("%d/%m/%Y") if d.due_date else "",
                status_label.get(d.status, d.status.value)]
        writer.writerow(row)
    # a BOM so a spreadsheet opens the accents right
    return "﻿" + out.getvalue()


# ------------------------------------------------------------------------------------------
# 3. Period summary
# ------------------------------------------------------------------------------------------


@dataclass
class RateLine:
    rate: Decimal
    base: Decimal = ZERO
    vat: Decimal = ZERO


@dataclass
class Period:
    key: str  # 2026-11 or 2026-T4
    start: date
    end: date
    invoiced_ht: Decimal = ZERO
    collected_goods: Decimal = ZERO  # TTC received, sales of goods (deposits included)
    collected_services: Decimal = ZERO
    vat: dict = field(default_factory=dict)  # rate -> RateLine

    def add_vat(self, rate: Decimal, base: Decimal, vat: Decimal) -> None:
        line = self.vat.setdefault(rate, RateLine(rate))
        line.base += base
        line.vat += vat


def _period_key(d: date, granularity: str) -> tuple[str, date, date]:
    if granularity == "quarter":
        q = (d.month - 1) // 3
        start = date(d.year, 3 * q + 1, 1)
        end_month = 3 * q + 3
    else:
        start = date(d.year, d.month, 1)
        end_month = d.month
    nxt = date(d.year + (end_month == 12), end_month % 12 + 1, 1)
    end = date.fromordinal(nxt.toordinal() - 1)
    key = f"{d.year}-T{(d.month - 1) // 3 + 1}" if granularity == "quarter" else f"{d.year}-{d.month:02d}"
    return key, start, end


def _on_payment(doc: SalesDocument) -> bool:
    if doc.is_deposit:
        return True  # deposits: VAT due on payment, goods included (since 1 January 2023)
    if doc.vat_on_debits or doc.kind == DocumentKind.CREDIT_NOTE:
        return False
    return doc.nature == OperationNature.SERVICES


def period_summary(db: Session, start: date, end: date, granularity: str = "month") -> list[Period]:
    periods: dict[str, Period] = {}

    def period(d: date) -> Period:
        key, ps, pe = _period_key(d, granularity)
        if key not in periods:
            periods[key] = Period(key, ps, pe)
        return periods[key]

    # invoiced, and VAT due on delivery / issue
    for doc in issued_documents(db, start, end):
        sign = -1 if doc.kind == DocumentKind.CREDIT_NOTE else 1
        if not doc.is_deposit:  # a deposit is part of the final invoice's turnover, not extra
            period(doc.issue_date).invoiced_ht += sign * doc.total_ht
        if _on_payment(doc):
            continue
        when = doc.delivery_date or doc.issue_date if doc.kind == DocumentKind.INVOICE else doc.issue_date
        if not start <= when <= end:
            continue
        deducted = {b.rate: b for dep in _deposits(db, doc) for b in vat_breakdown(dep)}
        for b in vat_breakdown(doc):
            already = deducted.get(b.rate)
            base = b.base - (already.base if already else ZERO)
            vat = b.amount - (already.amount if already else ZERO)
            period(when).add_vat(b.rate, sign * base, sign * vat)

    # collected, and VAT due on payment
    for doc in _documents_with_payments(db):
        sign = -1 if doc.kind == DocumentKind.CREDIT_NOTE else 1
        payable = doc.total_ttc - (doc.prepaid_amount or ZERO)
        deducted = {b.rate: b for dep in _deposits(db, doc) for b in vat_breakdown(dep)}
        for p in doc.payments:
            if not start <= p.paid_on <= end:
                continue
            per = period(p.paid_on)
            if doc.nature == OperationNature.SERVICES:
                per.collected_services += sign * p.amount
            else:
                per.collected_goods += sign * p.amount
            if not _on_payment(doc) or payable <= 0:
                continue
            share = p.amount / payable
            for b in vat_breakdown(doc):
                already = deducted.get(b.rate)
                base = b.base - (already.base if already else ZERO)
                vat = b.amount - (already.amount if already else ZERO)
                per.add_vat(b.rate, sign * base * share, sign * vat * share)

    result = sorted(periods.values(), key=lambda p: p.start)
    for p in result:
        p.invoiced_ht = money(p.invoiced_ht)
        p.collected_goods = money(p.collected_goods)
        p.collected_services = money(p.collected_services)
        for line in p.vat.values():
            line.base, line.vat = money(line.base), money(line.vat)
    return result
