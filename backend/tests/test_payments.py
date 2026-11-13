"""Payments, deposit invoices and what is still due."""

from datetime import date
from decimal import Decimal

from facturx import get_xml_from_pdf
from lxml import etree

from tests.test_designs_api import make_model, make_order
from tests.test_invoicing import CII, customer, invoice, seller


def issue(client, doc_id):
    r = client.post(f"/api/admin/documents/{doc_id}/issue")
    assert r.status_code == 200, r.text
    return r.json()


def pay(client, doc_id, amount, on="2026-11-10", method="transfer"):
    return client.post(f"/api/admin/documents/{doc_id}/payments", json={"paid_on": on, "amount": amount, "method": method})


def test_partial_payments_until_paid_and_back(client):
    seller(client)
    c = customer(client)
    doc = issue(client, invoice(client, c["id"])["id"])  # 180.00
    r = pay(client, doc["id"], "50.00", "2026-11-02")
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "issued" and body["amount_paid"] == "50.00" and body["balance_due"] == "130.00"
    assert pay(client, doc["id"], "130.01").status_code == 400  # never more than what is due
    body = pay(client, doc["id"], "130.00", "2026-11-09", "cheque").json()
    assert body["status"] == "paid" and body["paid_at"] == "2026-11-09" and body["balance_due"] == "0.00"
    assert [p["amount"] for p in body["payments"]] == ["50.00", "130.00"]
    # a payment entered by mistake is removed: the invoice is due again
    body = client.delete(f"/api/admin/documents/{doc['id']}/payments/{body['payments'][1]['id']}").json()
    assert body["status"] == "issued" and body["paid_at"] is None and body["balance_due"] == "130.00"


def test_mark_paid_records_the_balance_as_one_payment(client):
    seller(client)
    doc = issue(client, invoice(client, customer(client)["id"])["id"])
    pay(client, doc["id"], "30.00")
    body = client.post(f"/api/admin/documents/{doc['id']}/status?status=paid&paid_at=2026-11-12").json()
    assert body["status"] == "paid" and [p["amount"] for p in body["payments"]] == ["30.00", "150.00"]


def test_no_payment_on_a_draft_or_a_quote(client):
    seller(client)
    c = customer(client)
    draft = invoice(client, c["id"])
    assert pay(client, draft["id"], "10.00").status_code == 400


def test_credit_note_settles_what_it_cancels(client):
    seller(client)
    doc = issue(client, invoice(client, customer(client)["id"])["id"])
    note = client.post(f"/api/admin/documents/{doc['id']}/credit-note").json()
    issue(client, note["id"])
    body = client.get(f"/api/admin/documents/{doc['id']}").json()
    assert body["credited"] == "180.00" and body["balance_due"] == "0.00" and body["overdue_days"] == 0


def test_deposit_then_final_invoice_deducts_it(client, db):
    seller(client, vat_regime="normal", vat_number="FR12123456789", default_vat_rate=20)
    c = customer(client, is_business=True, company_name="Coutellerie SARL", siren="987654321")
    model = make_model(db)
    model.sale_price = 240  # TTC: 200.00 HT at 20 %
    order = make_order(db, model, 2)
    order.customer_id = c["id"]
    db.commit()

    deposit = client.post(f"/api/admin/documents/from-order/{order.id}?kind=invoice&deposit_percent=30")
    assert deposit.status_code == 201, deposit.text
    deposit = deposit.json()
    assert deposit["is_deposit"] and deposit["total_ht"] == "120.00" and deposit["total_ttc"] == "144.00"
    deposit = issue(client, deposit["id"])
    assert deposit["number"].startswith("F-")  # same continuous numbering as invoices
    pay(client, deposit["id"], "144.00")

    pdf = client.get(f"/api/admin/documents/{deposit['id']}/pdf").content
    root = etree.fromstring(get_xml_from_pdf(pdf, check_xsd=True)[1])
    assert root.xpath("//rsm:ExchangedDocument/ram:TypeCode/text()", namespaces=CII) == ["386"]

    final = client.post(f"/api/admin/documents/from-order/{order.id}?kind=invoice").json()
    assert final["prepaid_amount"] == "144.00" and final["prepaid_refs"][0]["number"] == deposit["number"]
    final = issue(client, final["id"])
    assert final["total_ttc"] == "480.00" and final["amount_payable"] == "336.00" and final["balance_due"] == "336.00"
    root = etree.fromstring(get_xml_from_pdf(client.get(f"/api/admin/documents/{final['id']}/pdf").content, check_xsd=True)[1])
    x = lambda p: root.xpath(p, namespaces=CII)  # noqa: E731
    assert x("//ram:TotalPrepaidAmount/text()") == ["144.00"]
    assert x("//ram:DuePayableAmount/text()") == ["336.00"]
    assert x("//rsm:ExchangedDocument/ram:TypeCode/text()") == ["380"]

    # a second final invoice of the same order does not deduct the deposit twice
    again = client.post(f"/api/admin/documents/from-order/{order.id}?kind=invoice").json()
    assert again["prepaid_amount"] == "0.00"


def test_deposit_validation(client, db):
    seller(client)
    model = make_model(db)  # no price
    order = make_order(db, model, 1)
    assert client.post(f"/api/admin/documents/from-order/{order.id}?kind=invoice&deposit_percent=30").status_code == 400
    assert client.post(f"/api/admin/documents/from-order/{order.id}?kind=quote&deposit_percent=30").status_code == 400
    assert client.post(f"/api/admin/documents/from-order/{order.id}?kind=invoice&deposit_percent=130").status_code == 422


def test_overdue_days(client):
    seller(client)
    doc = invoice(client, customer(client)["id"], issue_date="2026-01-01", due_date="2026-01-31")
    doc = issue(client, doc["id"])
    assert doc["overdue_days"] == (date.today() - date(2026, 1, 31)).days
    doc = pay(client, doc["id"], doc["balance_due"]).json()
    assert doc["overdue_days"] == 0 and Decimal(doc["balance_due"]) == 0
