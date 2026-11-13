"""Accounting exports: every entry balances, deposits are cleared once, VAT falls in the right
period (delivery for goods, payment for services and deposits)."""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from tests.test_designs_api import make_model, make_order
from tests.test_invoicing import customer, invoice, seller

D = Decimal


def issue(client, doc_id, **dates):
    if dates:
        assert client.put(f"/api/admin/documents/{doc_id}", json=dates).status_code == 200
    r = client.post(f"/api/admin/documents/{doc_id}/issue")
    assert r.status_code == 200, r.text
    return r.json()


def pay(client, doc_id, amount, on):
    r = client.post(f"/api/admin/documents/{doc_id}/payments", json={"paid_on": on, "amount": amount})
    assert r.status_code == 201, r.text


def journal(client, start="2026-01-01", end="2026-12-31"):
    r = client.get(f"/api/admin/accounting/journal.txt?start={start}&end={end}")
    assert r.status_code == 200
    lines = r.content.decode("utf-8").splitlines()
    header = lines[0].split("|")
    return [dict(zip(header, line.split("|"))) for line in lines[1:]]


def amount(text):
    return D(text.replace(",", ".")) if text else D(0)


def balanced(rows):
    by_entry = defaultdict(lambda: [D(0), D(0)])
    for r in rows:
        by_entry[r["EcritureNum"]][0] += amount(r["Debit"])
        by_entry[r["EcritureNum"]][1] += amount(r["Credit"])
    return all(d == c for d, c in by_entry.values()), by_entry


def account_total(rows, account):
    return sum((amount(r["Credit"]) - amount(r["Debit"]) for r in rows if r["CompteNum"] == account), D(0))


def make_vat_order(client, db, price=240, nature="goods"):
    seller(client, vat_regime="normal", vat_number="FR12123456789", default_vat_rate=20)
    c = customer(client, is_business=True, company_name="Coutellerie SARL", siren="987654321")
    model = make_model(db)
    model.sale_price = price
    order = make_order(db, model, 1)
    order.customer_id = c["id"]
    db.commit()
    return order, c


def test_journal_balances_and_clears_deposits(client, db):
    order, c = make_vat_order(client, db, price=600)  # 500.00 HT, 100.00 VAT
    dep = client.post(f"/api/admin/documents/from-order/{order.id}?kind=invoice&deposit_percent=30").json()
    dep = issue(client, dep["id"], **{"kind": "invoice", "customer_id": c["id"], "order_id": order.id, "issue_date": "2026-03-02",
                                       "lines": [{"description": "Acompte 30 %", "quantity": "1", "unit_price_ht": "150.00", "vat_rate": "20"}]})
    pay(client, dep["id"], "180.00", "2026-03-05")
    final = client.post(f"/api/admin/documents/from-order/{order.id}?kind=invoice").json()
    final = issue(client, final["id"])
    assert final["prepaid_amount"] == "180.00"

    rows = journal(client)
    ok, entries = balanced(rows)
    assert ok, entries
    # deposit: 4191 credited 150, then debited 150 by the final invoice -> cleared
    assert account_total(rows, "419100") == 0
    assert account_total(rows, "707000") == D("500.00")
    assert account_total(rows, "445710") == D("100.00")  # VAT once, not 100 + 30
    # customer account: 180 + 600 - 180 invoiced, 180 received -> 420 still due
    assert -account_total(rows, "411000") == D("420.00")
    assert {r["JournalCode"] for r in rows} == {"VE", "BQ"}
    assert all(len(r["EcritureDate"]) == 8 for r in rows)


def test_vat_on_payment_for_services_on_delivery_for_goods(client, db):
    seller(client, vat_regime="normal", vat_number="FR12123456789", default_vat_rate=20)
    c = customer(client, is_business=True, company_name="Coutellerie SARL", siren="987654321")
    line = [{"description": "Affûtage", "quantity": "1", "unit_price_ht": "100.00", "vat_rate": "20"}]
    services = invoice(client, c["id"], lines=line, nature="services", issue_date="2026-01-20")
    services = issue(client, services["id"])
    pay(client, services["id"], "60.00", "2026-02-10")
    pay(client, services["id"], "60.00", "2026-03-10")
    goods = invoice(client, c["id"], lines=[{**line[0], "description": "Couteau"}], issue_date="2026-01-25", delivery_date="2026-01-25")
    goods = issue(client, goods["id"])
    pay(client, goods["id"], "120.00", "2026-04-02")

    r = client.get("/api/admin/accounting/summary?start=2026-01-01&end=2026-06-30&granularity=month").json()
    by = {p["key"]: p for p in r["periods"]}
    assert by["2026-01"]["vat"] == [{"rate": 20.0, "base": 100.0, "vat": 20.0}]  # goods: delivered in January
    assert by["2026-01"]["invoiced_ht"] == 200.0
    assert by["2026-02"]["vat"] == [{"rate": 20.0, "base": 50.0, "vat": 10.0}]  # services: half paid in February
    assert by["2026-03"]["vat"] == [{"rate": 20.0, "base": 50.0, "vat": 10.0}]
    assert by["2026-04"]["vat"] == []  # paying for goods changes nothing to their VAT
    assert by["2026-02"]["collected_services"] == 60.0 and by["2026-04"]["collected_goods"] == 120.0

    quarters = client.get("/api/admin/accounting/summary?start=2026-01-01&end=2026-06-30&granularity=quarter").json()["periods"]
    assert [p["key"] for p in quarters] == ["2026-T1", "2026-T2"]
    assert quarters[0]["vat"] == [{"rate": 20.0, "base": 200.0, "vat": 40.0}]


def test_micro_entrepreneur_turnover_collected(client):
    seller(client)  # franchise
    c = customer(client)
    doc = issue(client, invoice(client, c["id"], issue_date="2026-05-28")["id"])  # 180.00
    pay(client, doc["id"], "80.00", "2026-05-30")
    pay(client, doc["id"], "100.00", "2026-06-03")
    r = client.get("/api/admin/accounting/summary?start=2026-05-01&end=2026-06-30").json()
    assert r["franchise"] is True
    by = {p["key"]: p for p in r["periods"]}
    assert by["2026-05"]["invoiced_ht"] == 180.0 and by["2026-05"]["collected_goods"] == 80.0
    assert by["2026-06"]["collected_goods"] == 100.0
    assert all(p["vat"] == [] or all(v["vat"] == 0 for v in p["vat"]) for p in r["periods"])


def test_credit_note_reverses_its_invoice(client):
    seller(client)
    doc = issue(client, invoice(client, customer(client)["id"])["id"])
    note = client.post(f"/api/admin/documents/{doc['id']}/credit-note").json()
    issue(client, note["id"])
    y = date.today().year
    rows = journal(client, f"{y}-01-01", f"{y}-12-31")
    assert balanced(rows)[0]
    assert account_total(rows, "707000") == 0 and account_total(rows, "411000") == 0


def test_sales_csv_and_validation(client):
    seller(client)
    doc = issue(client, invoice(client, customer(client)["id"])["id"])
    y = date.today().year
    r = client.get(f"/api/admin/accounting/sales.csv?start={y}-01-01&end={y}-12-31")
    text = r.content.decode("utf-8")
    assert text.startswith("﻿Date;Numéro;Type")
    assert doc["number"] in text and "180,00" in text
    assert client.get("/api/admin/accounting/summary?start=2026-02-01&end=2026-01-01").status_code == 422
    assert client.get("/api/admin/accounting/summary?start=2020-01-01&end=2026-01-01").status_code == 422
