"""Sample Factur-X files for an independent validator.

The suite checks the XML against the EN 16931 schema (factur-x's XSD). The CI goes further: it
sets FACTURX_SAMPLES_DIR, this test writes one file per kind of document there, and the
Mustang validator (Java, independent of this code) checks the XML rules (schematron) and the
PDF/A-3 part. Its reports are kept with each version.
"""

import os
from pathlib import Path

from facturx import get_xml_from_pdf

from tests.test_invoicing import customer, invoice, seller


def _issue_pdf(client, doc_id: int) -> bytes:
    issued = client.post(f"/api/admin/documents/{doc_id}/issue")
    assert issued.status_code == 200, issued.text
    return client.get(f"/api/admin/documents/{doc_id}/pdf").content


def test_write_samples(client, db, tmp_path):
    out = Path(os.environ.get("FACTURX_SAMPLES_DIR") or tmp_path)
    out.mkdir(parents=True, exist_ok=True)
    samples: dict[str, bytes] = {}

    seller(client, vat_regime="normal", vat_number="FR12123456789")
    business = customer(client, is_business=True, company_name="Coutellerie SARL", siren="987654321")
    doc = invoice(
        client,
        business["id"],
        lines=[
            {"description": "Couteau de chef 210 mm", "quantity": "1", "unit_price_ht": "240.00", "vat_rate": "20"},
            {"description": "Affûtage", "quantity": "2", "unit_price_ht": "15.50", "vat_rate": "20"},
        ],
        nature="mixed",
        vat_on_debits=False,
    )
    samples["facture-tva-b2b"] = _issue_pdf(client, doc["id"])

    # an order invoiced in two steps: a 30 % deposit (type 386), then the final invoice that
    # deducts it (BT-113)
    from tests.test_designs_api import make_model, make_order

    model = make_model(db)
    model.sale_price = 360
    order = make_order(db, model, 1)
    order.customer_id = business["id"]
    db.commit()
    deposit = client.post(f"/api/admin/documents/from-order/{order.id}?kind=invoice&deposit_percent=30").json()
    samples["facture-acompte"] = _issue_pdf(client, deposit["id"])
    final = client.post(f"/api/admin/documents/from-order/{order.id}?kind=invoice").json()
    samples["facture-solde-apres-acompte"] = _issue_pdf(client, final["id"])

    note = client.post(f"/api/admin/documents/{doc['id']}/credit-note")
    assert note.status_code == 201, note.text
    samples["avoir"] = _issue_pdf(client, note.json()["id"])

    # a micro-entrepreneur under the VAT franchise who has an intra-EU VAT number (BR-E-02)
    seller(client, vat_regime="franchise", vat_number="FR12123456789")
    private = customer(client, name="Sam Petit", email="sam@example.com")
    samples["facture-franchise"] = _issue_pdf(client, invoice(client, private["id"])["id"])

    for name, pdf in samples.items():
        get_xml_from_pdf(pdf, check_xsd=True)
        (out / f"{name}.pdf").write_bytes(pdf)
    assert len(list(out.glob("*.pdf"))) >= 5
