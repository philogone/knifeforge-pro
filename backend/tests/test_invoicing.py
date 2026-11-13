from decimal import Decimal

from facturx import get_xml_from_pdf
from lxml import etree

from tests.test_designs_api import make_material, make_model, make_order

SELLER = {
    "legal_name": "Atelier Dupont",
    "address_line1": "1 rue des Forges",
    "postal_code": "87000",
    "city": "Limoges",
    "siren": "123456789",
    "iban": "FR7630006000011234567890189",
}
CII = {"ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
       "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"}


def seller(client, **extra):
    response = client.patch("/api/admin/settings/shop", json={**SELLER, **extra})
    assert response.status_code == 200, response.text


def customer(client, **extra):
    body = {"name": "Camille Martin", "email": "camille@example.com", "address_line1": "2 place du Marché",
            "postal_code": "69001", "city": "Lyon", **extra}
    response = client.post("/api/admin/customers", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def invoice(client, customer_id, lines=None, **extra):
    body = {"kind": "invoice", "customer_id": customer_id, "nature": "goods",
            "lines": lines or [{"description": "Couteau Bushcraft", "quantity": "1", "unit_price_ht": "180.00", "vat_rate": "0"}], **extra}
    response = client.post("/api/admin/documents", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_issuing_numbers_invoices_continuously_and_freezes_them(client):
    seller(client)
    c = customer(client)
    first, second = invoice(client, c["id"]), invoice(client, c["id"])
    assert first["number"] is None and first["status"] == "draft"

    a = client.post(f"/api/admin/documents/{second['id']}/issue").json()
    b = client.post(f"/api/admin/documents/{first['id']}/issue").json()
    year = a["issue_date"][:4]
    assert (a["number"], b["number"]) == (f"F-{year}-0001", f"F-{year}-0002")  # in issue order, no gap
    assert a["frozen"] and a["due_date"] and a["delivery_date"]

    # frozen: no edit, no delete, no second issue
    assert client.put(f"/api/admin/documents/{a['id']}", json={"kind": "invoice", "lines": []}).status_code == 409
    assert client.delete(f"/api/admin/documents/{a['id']}").status_code == 409
    assert client.post(f"/api/admin/documents/{a['id']}/issue").status_code == 400
    # and the customer's later edits do not rewrite it
    client.put(f"/api/admin/customers/{c['id']}", json={**{k: c[k] for k in ("name", "address_line1", "postal_code", "city")}, "city": "Paris"})
    pdf = client.get(f"/api/admin/documents/{a['id']}/pdf").content
    assert b"Lyon" in get_xml_from_pdf(pdf, check_xsd=False)[1]


def test_issue_refuses_an_incomplete_invoice_and_says_what_is_missing(client):
    c = customer(client, is_business=True, company_name="Coutellerie SARL")
    doc = invoice(client, c["id"])
    assert set(doc["missing"]) >= {"seller_address", "seller_siren", "customer_siren"}
    response = client.post(f"/api/admin/documents/{doc['id']}/issue")
    assert response.status_code == 400 and "seller_siren" in response.json()["detail"]


def test_franchise_and_vat_totals(client):
    seller(client)
    c = customer(client)
    franchise = invoice(client, c["id"], lines=[
        {"description": "Couteau", "quantity": "2", "unit_price_ht": "150.00", "vat_rate": "0"},
        {"description": "Étui cuir", "quantity": "1", "unit_price_ht": "45.50", "vat_rate": "0"},
    ])
    assert (franchise["total_ht"], franchise["total_vat"], franchise["total_ttc"]) == ("345.50", "0.00", "345.50")

    seller(client, vat_regime="normal", vat_number="FR12123456789")
    taxed = invoice(client, c["id"], lines=[
        {"description": "Couteau", "quantity": "3", "unit_price_ht": "33.33", "vat_rate": "20"},
        {"description": "Affûtage", "quantity": "1", "unit_price_ht": "10.00", "vat_rate": "20"},
    ])
    # VAT on the sum per rate, rounded once: (99.99 + 10.00) * 20 % = 21.998 -> 22.00
    assert (taxed["total_ht"], taxed["total_vat"], taxed["total_ttc"]) == ("109.99", "22.00", "131.99")


def test_issued_invoice_is_a_valid_factur_x_with_the_new_mentions(client):
    seller(client, vat_regime="normal", vat_number="FR12123456789")
    c = customer(client, is_business=True, company_name="Coutellerie SARL", siren="987654321",
                 delivery_line1="Entrepôt, 3 rue Basse", delivery_postal_code="69007", delivery_city="Lyon")
    doc = invoice(client, c["id"], lines=[{"description": "Couteau", "quantity": "1", "unit_price_ht": "150.00", "vat_rate": "20"}],
                  vat_on_debits=False)
    client.post(f"/api/admin/documents/{doc['id']}/issue")
    pdf = client.get(f"/api/admin/documents/{doc['id']}/pdf").content
    assert pdf.startswith(b"%PDF")
    name, xml = get_xml_from_pdf(pdf, check_xsd=True)  # raises if the EN 16931 XML is invalid
    assert name == "factur-x.xml"
    root = etree.fromstring(xml)
    text = lambda path: root.xpath(path, namespaces=CII)  # noqa: E731
    assert text("//rsm:ExchangedDocument/ram:TypeCode/text()") == ["380"]
    assert text("//ram:BusinessProcessSpecifiedDocumentContextParameter/ram:ID/text()") == ["B1"]  # nature: goods
    assert text("//ram:BuyerTradeParty/ram:SpecifiedLegalOrganization/ram:ID/text()") == ["987654321"]  # buyer SIREN
    assert text("//ram:ShipToTradeParty//ram:LineOne/text()") == ["Entrepôt, 3 rue Basse"]  # delivery address
    assert text("//ram:GrandTotalAmount/text()") == ["180.00"]
    assert "PMT" in text("//ram:IncludedNote/ram:SubjectCode/text()")  # 40 € recovery fee, B2B


def test_micro_entreprise_invoice_states_the_vat_exemption(client):
    seller(client)
    c = customer(client)
    doc = invoice(client, c["id"])
    client.post(f"/api/admin/documents/{doc['id']}/issue")
    pdf = client.get(f"/api/admin/documents/{doc['id']}/pdf").content
    root = etree.fromstring(get_xml_from_pdf(pdf, check_xsd=True)[1])
    assert root.xpath("//ram:ApplicableHeaderTradeSettlement/ram:ApplicableTradeTax/ram:CategoryCode/text()", namespaces=CII) == ["E"]
    assert "293 B" in root.xpath("//ram:ExemptionReason/text()", namespaces=CII)[0]


def test_credit_note_references_the_invoice_it_corrects(client):
    seller(client)
    c = customer(client)
    doc = invoice(client, c["id"])
    issued = client.post(f"/api/admin/documents/{doc['id']}/issue").json()
    assert client.post(f"/api/admin/documents/{doc['id']}/credit-note").status_code == 201
    note = [d for d in client.get("/api/admin/documents?kind=credit_note").json()][0]
    assert note["corrects_number"] == issued["number"] and note["total_ttc"] == issued["total_ttc"]
    note = client.post(f"/api/admin/documents/{note['id']}/issue").json()
    assert note["number"].startswith("A-")
    root = etree.fromstring(get_xml_from_pdf(client.get(f"/api/admin/documents/{note['id']}/pdf").content, check_xsd=True)[1])
    assert root.xpath("//rsm:ExchangedDocument/ram:TypeCode/text()", namespaces=CII) == ["381"]
    assert root.xpath("//ram:InvoiceReferencedDocument/ram:IssuerAssignedID/text()", namespaces=CII) == [issued["number"]]


def test_quote_from_order_then_invoice(client, db):
    seller(client)
    model = make_model(db)
    model.sale_price = 180
    db.commit()
    c = customer(client)
    order = make_order(db, model, 2)
    client.patch(f"/api/admin/orders/{order.id}", json={"customer_id": c["id"]})
    quote = client.post(f"/api/admin/documents/from-order/{order.id}?kind=quote").json()
    assert quote["kind"] == "quote" and quote["lines"][0]["quantity"] == "2.000" and quote["total_ttc"] == "360.00"
    issued = client.post(f"/api/admin/documents/{quote['id']}/issue").json()
    assert issued["number"].startswith("D-") and issued["valid_until"]
    inv = client.post(f"/api/admin/documents/{quote['id']}/to-invoice").json()
    assert inv["kind"] == "invoice" and inv["total_ttc"] == "360.00"
    assert client.get(f"/api/admin/documents/{quote['id']}").json()["status"] == "accepted"


def test_customer_gdpr_export_and_erasure_keep_invoices(client):
    seller(client)
    c = customer(client, phone="0600000000")
    doc = invoice(client, c["id"])
    client.post(f"/api/admin/documents/{doc['id']}/issue")
    export = client.get(f"/api/admin/customers/{c['id']}/export").json()
    assert export["customer"]["email"] == "camille@example.com" and len(export["documents"]) == 1

    assert client.delete(f"/api/admin/customers/{c['id']}").status_code == 409  # has documents
    erased = client.post(f"/api/admin/customers/{c['id']}/erase").json()
    assert erased["anonymized_at"] and erased["email"] is None and erased["phone"] is None
    # the issued invoice still names the buyer: legal retention beats erasure
    assert client.get(f"/api/admin/documents/{doc['id']}").json()["customer_name"] == "Camille Martin"


def test_stock_ledger_explains_every_change(client, db):
    steel = make_material(db)
    from app.models.knife_model import KnifeModelMaterial, MaterialRole

    model = make_model(db)
    db.add(KnifeModelMaterial(knife_model_id=model.id, material_id=steel.id, role=MaterialRole.BLADE, blank_length_mm=200))
    db.commit()
    client.post(f"/api/admin/materials/{steel.id}/restock", json={"quantity_delta": 1000, "purchase_price": 45})
    order = make_order(db, model, 2)
    client.post(f"/api/admin/orders/{order.id}/confirm")
    client.post(f"/api/admin/orders/{order.id}/cancel")
    moves = client.get(f"/api/admin/materials/{steel.id}/movements").json()
    reasons = [m["reason"] for m in moves]
    assert reasons == ["order_cancelled", "order_confirmed", "restock"]
    kerf = steel.kerf_mm or 0
    assert moves[1]["delta"] == -(200 + kerf) * 2 and moves[1]["order_id"] == order.id
    assert moves[0]["balance_after"] == 4000.0  # 3000 + 1000 restocked, deducted then given back
    assert Decimal(str(moves[2]["cost"])) == Decimal("45")


def test_independent_validator_requirements(client):
    """What the Mustang validator asked for (CI job "Factur-X"): sRGB output intent (PDF/A-3),
    electronic addresses (BR-FR-12/13), seller VAT number on an exempt invoice (BR-E-02),
    date of the corrected invoice on a credit note (BR-FR-CO-05)."""
    from pypdf import PdfReader
    import io

    seller(client, vat_regime="franchise", vat_number="FR12123456789")
    c = customer(client)  # a private buyer: no SIREN, an e-mail
    doc = invoice(client, c["id"])
    issued = client.post(f"/api/admin/documents/{doc['id']}/issue").json()
    pdf = client.get(f"/api/admin/documents/{doc['id']}/pdf").content
    intents = PdfReader(io.BytesIO(pdf)).trailer["/Root"]["/OutputIntents"]
    assert intents[0].get_object()["/S"] == "/GTS_PDFA1"
    root = etree.fromstring(get_xml_from_pdf(pdf, check_xsd=True)[1])
    x = lambda path: root.xpath(path, namespaces=CII)  # noqa: E731
    assert x("//ram:SellerTradeParty/ram:URIUniversalCommunication/ram:URIID[@schemeID='0225']/text()") == ["123456789"]
    assert x("//ram:BuyerTradeParty/ram:URIUniversalCommunication/ram:URIID[@schemeID='EM']/text()") == ["camille@example.com"]
    assert x("//ram:SellerTradeParty/ram:SpecifiedTaxRegistration/ram:ID[@schemeID='VA']/text()") == ["FR12123456789"]

    note = client.post(f"/api/admin/documents/{doc['id']}/credit-note").json()
    client.post(f"/api/admin/documents/{note['id']}/issue")
    root = etree.fromstring(get_xml_from_pdf(client.get(f"/api/admin/documents/{note['id']}/pdf").content, check_xsd=True)[1])
    ref = "//ram:InvoiceReferencedDocument"
    assert root.xpath(f"{ref}/ram:IssuerAssignedID/text()", namespaces=CII) == [issued["number"]]
    qdt = {"qdt": "urn:un:unece:uncefact:data:standard:QualifiedDataType:100", **CII}
    assert root.xpath(f"{ref}/ram:FormattedIssueDateTime/qdt:DateTimeString/text()", namespaces=qdt) == [issued["issue_date"].replace("-", "")]
