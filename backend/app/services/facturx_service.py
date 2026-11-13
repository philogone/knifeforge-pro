"""Factur-X: a readable PDF/A-3 with the EN 16931 invoice embedded as Cross-Industry Invoice XML.

The PDF is what a person reads; the XML is what the buyer's software and the approved
platforms (plateformes agréées) process. Both are generated from the issued document's frozen
data. Quotes get the same PDF, without XML (they are not invoices).
"""

from __future__ import annotations

import io
import os
from datetime import date
from decimal import Decimal
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.models.sales_document import DocumentKind, OperationNature, SalesDocument
from app.services.billing_service import (
    B2B_RECOVERY_FEE,
    FRANCHISE_MENTION,
    VatBreakdown,
    line_total,
    money,
    vat_breakdown,
)

TYPE_CODE = {DocumentKind.INVOICE: "380", DocumentKind.CREDIT_NOTE: "381"}
# French billing framework (BT-23), from the nature of the operation
FRAMEWORK = {OperationNature.GOODS: "B1", OperationNature.SERVICES: "S1", OperationNature.MIXED: "M1"}
NATURE_LABEL = {
    OperationNature.GOODS: "Livraison de biens",
    OperationNature.SERVICES: "Prestation de services",
    OperationNature.MIXED: "Livraison de biens et prestation de services",
}
TITLE = {DocumentKind.QUOTE: "Devis", DocumentKind.INVOICE: "Facture", DocumentKind.CREDIT_NOTE: "Avoir"}
DEPOSIT_TYPE_CODE = "386"  # UNTDID 1001: prepayment invoice (facture d'acompte)
DEPOSIT_TITLE = "Facture d'acompte"


def title_of(doc: SalesDocument) -> str:
    return DEPOSIT_TITLE if doc.is_deposit and doc.kind == DocumentKind.INVOICE else TITLE[doc.kind]

# ------------------------------------------------------------------------------ XML (CII)

NS = (
    'xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100" '
    'xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100" '
    'xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100" '
    'xmlns:qdt="urn:un:unece:uncefact:data:standard:QualifiedDataType:100"'
)


def _x(value: object) -> str:
    return escape(str(value))


def _d(value: date) -> str:
    return f'<udt:DateTimeString format="102">{value.strftime("%Y%m%d")}</udt:DateTimeString>'


def _amount(value: Decimal) -> str:
    return f"{money(value):.2f}"


def _category(rate: Decimal, franchise: bool) -> str:
    return "E" if franchise or rate == 0 else "S"


def _address(prefix: str, line1: str | None, postal: str | None, city: str | None, country: str | None) -> str:
    parts = [f"<ram:{prefix}PostalTradeAddress>"]
    if postal:
        parts.append(f"<ram:PostcodeCode>{_x(postal)}</ram:PostcodeCode>")
    if line1:
        parts.append(f"<ram:LineOne>{_x(line1)}</ram:LineOne>")
    if city:
        parts.append(f"<ram:CityName>{_x(city)}</ram:CityName>")
    parts.append(f"<ram:CountryID>{_x(country or 'FR')}</ram:CountryID>")
    parts.append(f"</ram:{prefix}PostalTradeAddress>")
    return "".join(parts)


def _electronic_address(siren: str | None, email: str | None) -> str:
    """BT-34 / BT-49: where the invoice is delivered. French rules (XP Z12-012, BR-FR-12/13/21):
    the SIREN under scheme 0225 for a company; a private buyer has none, so their e-mail (EAS
    "EM")."""
    if siren:
        return f'<ram:URIUniversalCommunication><ram:URIID schemeID="0225">{_x(siren)}</ram:URIID></ram:URIUniversalCommunication>'
    if email:
        return f'<ram:URIUniversalCommunication><ram:URIID schemeID="EM">{_x(email)}</ram:URIID></ram:URIUniversalCommunication>'
    return ""


def build_cii_xml(doc: SalesDocument, corrected_number: str | None = None, corrected_date: date | None = None) -> str:
    """EN 16931 (Factur-X profile EN16931) for an issued invoice or credit note."""
    if doc.kind not in TYPE_CODE or not doc.number or not doc.issue_date:
        raise ValueError("Only an issued invoice or credit note has a Factur-X XML")
    seller = doc.seller_snapshot or {}
    buyer = doc.buyer_snapshot or {}
    franchise = seller.get("vat_regime", "franchise") == "franchise"
    breakdown: list[VatBreakdown] = vat_breakdown(doc)

    notes = []
    if doc.notes:
        notes.append(("", doc.notes))
    notes.append(("AAB", "Pas d'escompte pour paiement anticipé"))
    notes.append(("PMD", seller.get("late_penalty_text") or ""))
    if buyer.get("is_business"):
        notes.append(("PMT", B2B_RECOVERY_FEE))
    if seller.get("trade_register"):
        notes.append(("ABL", seller["trade_register"]))

    out: list[str] = [f'<?xml version="1.0" encoding="UTF-8"?><rsm:CrossIndustryInvoice {NS}>']
    out.append("<rsm:ExchangedDocumentContext>")
    out.append(
        f"<ram:BusinessProcessSpecifiedDocumentContextParameter><ram:ID>{FRAMEWORK[doc.nature]}</ram:ID>"
        "</ram:BusinessProcessSpecifiedDocumentContextParameter>"
    )
    out.append(
        "<ram:GuidelineSpecifiedDocumentContextParameter><ram:ID>urn:cen.eu:en16931:2017</ram:ID>"
        "</ram:GuidelineSpecifiedDocumentContextParameter>"
    )
    out.append("</rsm:ExchangedDocumentContext>")

    out.append("<rsm:ExchangedDocument>")
    type_code = DEPOSIT_TYPE_CODE if doc.is_deposit and doc.kind == DocumentKind.INVOICE else TYPE_CODE[doc.kind]
    out.append(f"<ram:ID>{_x(doc.number)}</ram:ID><ram:TypeCode>{type_code}</ram:TypeCode>")
    out.append(f"<ram:IssueDateTime>{_d(doc.issue_date)}</ram:IssueDateTime>")
    for subject, content in notes:
        if not content:
            continue
        out.append("<ram:IncludedNote>")
        out.append(f"<ram:Content>{_x(content)}</ram:Content>")
        if subject:
            out.append(f"<ram:SubjectCode>{subject}</ram:SubjectCode>")
        out.append("</ram:IncludedNote>")
    out.append("</rsm:ExchangedDocument>")

    out.append("<rsm:SupplyChainTradeTransaction>")
    for i, line in enumerate(doc.lines, start=1):
        rate = Decimal(line.vat_rate)
        out.append("<ram:IncludedSupplyChainTradeLineItem>")
        out.append(f"<ram:AssociatedDocumentLineDocument><ram:LineID>{i}</ram:LineID></ram:AssociatedDocumentLineDocument>")
        out.append(f"<ram:SpecifiedTradeProduct><ram:Name>{_x(line.description)}</ram:Name></ram:SpecifiedTradeProduct>")
        out.append(
            "<ram:SpecifiedLineTradeAgreement><ram:NetPriceProductTradePrice>"
            f"<ram:ChargeAmount>{_amount(line.unit_price_ht)}</ram:ChargeAmount>"
            "</ram:NetPriceProductTradePrice></ram:SpecifiedLineTradeAgreement>"
        )
        out.append(
            "<ram:SpecifiedLineTradeDelivery>"
            f'<ram:BilledQuantity unitCode="{_x(line.unit)}">{Decimal(line.quantity):f}</ram:BilledQuantity>'
            "</ram:SpecifiedLineTradeDelivery>"
        )
        out.append("<ram:SpecifiedLineTradeSettlement><ram:ApplicableTradeTax><ram:TypeCode>VAT</ram:TypeCode>")
        out.append(f"<ram:CategoryCode>{_category(rate, franchise)}</ram:CategoryCode>")
        out.append(f"<ram:RateApplicablePercent>{_amount(rate)}</ram:RateApplicablePercent>")
        out.append("</ram:ApplicableTradeTax><ram:SpecifiedTradeSettlementLineMonetarySummation>")
        out.append(f"<ram:LineTotalAmount>{_amount(line_total(line))}</ram:LineTotalAmount>")
        out.append("</ram:SpecifiedTradeSettlementLineMonetarySummation></ram:SpecifiedLineTradeSettlement>")
        out.append("</ram:IncludedSupplyChainTradeLineItem>")

    # ---- parties
    out.append("<ram:ApplicableHeaderTradeAgreement>")
    out.append(f"<ram:SellerTradeParty><ram:Name>{_x(seller.get('name') or '')}</ram:Name>")
    if seller.get("siren"):
        out.append(
            f'<ram:SpecifiedLegalOrganization><ram:ID schemeID="0002">{_x(seller["siren"])}</ram:ID>'
            + (f"<ram:TradingBusinessName>{_x(seller['trade_name'])}</ram:TradingBusinessName>" if seller.get("trade_name") and seller.get("trade_name") != seller.get("name") else "")
            + "</ram:SpecifiedLegalOrganization>"
        )
    out.append(_address("", seller.get("address_line1"), seller.get("postal_code"), seller.get("city"), seller.get("country")))
    out.append(_electronic_address(seller.get("siren"), seller.get("email")))
    # also under the VAT franchise: an exempt line (category E) needs the seller's VAT
    # identifier (EN 16931, BR-E-02); the PDF keeps the "TVA non applicable" mention
    if seller.get("vat_number"):
        out.append(f'<ram:SpecifiedTaxRegistration><ram:ID schemeID="VA">{_x(seller["vat_number"])}</ram:ID></ram:SpecifiedTaxRegistration>')
    out.append("</ram:SellerTradeParty>")
    out.append(f"<ram:BuyerTradeParty><ram:Name>{_x(buyer.get('name') or '')}</ram:Name>")
    if buyer.get("siren"):
        out.append(f'<ram:SpecifiedLegalOrganization><ram:ID schemeID="0002">{_x(buyer["siren"])}</ram:ID></ram:SpecifiedLegalOrganization>')
    out.append(_address("", buyer.get("address_line1"), buyer.get("postal_code"), buyer.get("city"), buyer.get("country")))
    out.append(_electronic_address(buyer.get("siren"), buyer.get("email")))
    if buyer.get("vat_number"):
        out.append(f'<ram:SpecifiedTaxRegistration><ram:ID schemeID="VA">{_x(buyer["vat_number"])}</ram:ID></ram:SpecifiedTaxRegistration>')
    out.append("</ram:BuyerTradeParty>")
    out.append("</ram:ApplicableHeaderTradeAgreement>")

    # ---- delivery (address only when it differs from the billing one: mandatory mention)
    out.append("<ram:ApplicableHeaderTradeDelivery>")
    delivery = buyer.get("delivery")
    if delivery:
        out.append(f"<ram:ShipToTradeParty><ram:Name>{_x(buyer.get('name') or '')}</ram:Name>")
        out.append(_address("", delivery.get("line1"), delivery.get("postal_code"), delivery.get("city"), delivery.get("country")))
        out.append("</ram:ShipToTradeParty>")
    if doc.delivery_date:
        out.append(
            "<ram:ActualDeliverySupplyChainEvent><ram:OccurrenceDateTime>"
            f"{_d(doc.delivery_date)}</ram:OccurrenceDateTime></ram:ActualDeliverySupplyChainEvent>"
        )
    out.append("</ram:ApplicableHeaderTradeDelivery>")

    # ---- settlement
    out.append("<ram:ApplicableHeaderTradeSettlement><ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>")
    if seller.get("iban"):
        out.append(
            "<ram:SpecifiedTradeSettlementPaymentMeans><ram:TypeCode>58</ram:TypeCode>"
            f"<ram:PayeePartyCreditorFinancialAccount><ram:IBANID>{_x(seller['iban'].replace(' ', ''))}</ram:IBANID>"
            "</ram:PayeePartyCreditorFinancialAccount></ram:SpecifiedTradeSettlementPaymentMeans>"
        )
    for b in breakdown:
        category = _category(b.rate, franchise)
        out.append(f"<ram:ApplicableTradeTax><ram:CalculatedAmount>{_amount(b.amount)}</ram:CalculatedAmount><ram:TypeCode>VAT</ram:TypeCode>")
        if category == "E":
            out.append(f"<ram:ExemptionReason>{_x(FRANCHISE_MENTION)}</ram:ExemptionReason>")
        out.append(f"<ram:BasisAmount>{_amount(b.base)}</ram:BasisAmount><ram:CategoryCode>{category}</ram:CategoryCode>")
        if doc.vat_on_debits and category == "S":
            # option pour le paiement de la TVA d'après les débits (mandatory mention): VAT point = invoice date
            out.append("<ram:DueDateTypeCode>5</ram:DueDateTypeCode>")
        out.append(f"<ram:RateApplicablePercent>{_amount(b.rate)}</ram:RateApplicablePercent></ram:ApplicableTradeTax>")
    if doc.due_date:
        out.append(f"<ram:SpecifiedTradePaymentTerms><ram:DueDateDateTime>{_d(doc.due_date)}</ram:DueDateDateTime></ram:SpecifiedTradePaymentTerms>")
    out.append("<ram:SpecifiedTradeSettlementHeaderMonetarySummation>")
    out.append(f"<ram:LineTotalAmount>{_amount(doc.total_ht)}</ram:LineTotalAmount>")
    out.append(f"<ram:TaxBasisTotalAmount>{_amount(doc.total_ht)}</ram:TaxBasisTotalAmount>")
    out.append(f'<ram:TaxTotalAmount currencyID="EUR">{_amount(doc.total_vat)}</ram:TaxTotalAmount>')
    out.append(f"<ram:GrandTotalAmount>{_amount(doc.total_ttc)}</ram:GrandTotalAmount>")
    prepaid = doc.prepaid_amount or Decimal("0")
    if prepaid:
        # deposits already invoiced (BT-113): BR-CO-16, due = total - prepaid
        out.append(f"<ram:TotalPrepaidAmount>{_amount(prepaid)}</ram:TotalPrepaidAmount>")
    out.append(f"<ram:DuePayableAmount>{_amount(doc.total_ttc - prepaid)}</ram:DuePayableAmount>")
    out.append("</ram:SpecifiedTradeSettlementHeaderMonetarySummation>")
    if corrected_number:
        out.append(
            f"<ram:InvoiceReferencedDocument><ram:IssuerAssignedID>{_x(corrected_number)}</ram:IssuerAssignedID>"
            # the date of the corrected invoice (BT-26, required with BT-25 by BR-FR-CO-05)
            + (f"<ram:FormattedIssueDateTime><qdt:DateTimeString format=\"102\">{corrected_date:%Y%m%d}</qdt:DateTimeString></ram:FormattedIssueDateTime>" if corrected_date else "")
            + "</ram:InvoiceReferencedDocument>"
        )
    out.append("</ram:ApplicableHeaderTradeSettlement>")
    out.append("</rsm:SupplyChainTradeTransaction></rsm:CrossIndustryInvoice>")
    return "".join(out)


# ------------------------------------------------------------------------------ PDF

_FONTS_READY = False


def _fonts() -> tuple[str, str]:
    """Embedded TrueType fonts (PDF/A forbids the 14 non-embedded base fonts)."""
    global _FONTS_READY
    if not _FONTS_READY:
        folder = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
        pdfmetrics.registerFont(TTFont("KF", os.path.join(folder, "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("KF-Bold", os.path.join(folder, "VeraBd.ttf")))
        _FONTS_READY = True
    return "KF", "KF-Bold"


INK = HexColor("#1c1b18")
MUTED = HexColor("#6f6a60")
RULE = HexColor("#cdc7ba")


def _fr_money(value: Decimal) -> str:
    text = f"{money(value):,.2f}".replace(",", " ").replace(".", ",")
    return f"{text} €"


def _fr_num(value: Decimal) -> str:
    text = f"{Decimal(value).normalize():f}"
    return text.replace(".", ",")


def _fr_date(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else "—"


def render_pdf(doc: SalesDocument, *, logo: str | None = None, corrected_number: str | None = None, draft: bool = False) -> bytes:
    regular, bold = _fonts()
    seller = doc.seller_snapshot or {}
    buyer = doc.buyer_snapshot or {}
    franchise = seller.get("vat_regime", "franchise") == "franchise"
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, pageCompression=1)
    title = f"{title_of(doc)} {doc.number}" if doc.number else f"{title_of(doc)} (brouillon)"
    c.setTitle(title)
    c.setAuthor(seller.get("name") or "KnifeForge Pro")
    c.setCreator("KnifeForge Pro")
    width, height = A4
    left, right = 18 * mm, width - 18 * mm
    y = height - 20 * mm

    # logo + seller block (left), title block (right)
    if logo:
        try:
            from reportlab.lib.utils import ImageReader
            import base64

            if logo.startswith("data:image/png") or logo.startswith("data:image/jpeg"):
                raw = base64.b64decode(logo.split(",", 1)[1])
                c.drawImage(ImageReader(io.BytesIO(raw)), left, y - 12 * mm, width=40 * mm, height=14 * mm, preserveAspectRatio=True, anchor="sw", mask="auto")
                y -= 16 * mm
        except Exception:  # noqa: BLE001 - a broken logo must not block an invoice
            pass
    c.setFillColor(INK)
    c.setFont(bold, 11)
    c.drawString(left, y, seller.get("name") or "")
    c.setFont(regular, 8.5)
    lines = [
        seller.get("trade_name") if seller.get("trade_name") and seller.get("trade_name") != seller.get("name") else None,
        seller.get("address_line1"),
        " ".join(p for p in (seller.get("postal_code"), seller.get("city")) if p),
        f"SIREN {seller['siren']}" + (f" · SIRET {seller['siret']}" if seller.get("siret") else "") if seller.get("siren") else None,
        seller.get("trade_register"),
        f"TVA intracommunautaire {seller['vat_number']}" if seller.get("vat_number") and not franchise else None,
        seller.get("contact"),
    ]
    yy = y - 5 * mm
    for text in filter(None, lines):
        c.drawString(left, yy, text)
        yy -= 4 * mm

    c.setFont(bold, 18)
    c.drawRightString(right, height - 22 * mm, title_of(doc))
    c.setFont(regular, 9)
    meta = [
        ("N°", doc.number or "brouillon"),
        ("Date", _fr_date(doc.issue_date)),
    ]
    if doc.kind == DocumentKind.QUOTE:
        meta.append(("Valable jusqu'au", _fr_date(doc.valid_until)))
    else:
        meta.append(("Échéance", _fr_date(doc.due_date)))
        meta.append(("Date de livraison", _fr_date(doc.delivery_date)))
    if corrected_number:
        meta.append(("Facture corrigée", corrected_number))
    my = height - 29 * mm
    for label, value in meta:
        c.setFillColor(MUTED)
        c.drawRightString(right - 32 * mm, my, label)
        c.setFillColor(INK)
        c.drawRightString(right, my, value)
        my -= 4.5 * mm

    # buyer block
    by = min(yy, my) - 8 * mm
    bx = width / 2 + 5 * mm
    c.setFillColor(MUTED)
    c.setFont(regular, 8)
    c.drawString(bx, by, "Client")
    c.setFillColor(INK)
    c.setFont(bold, 10)
    c.drawString(bx, by - 5 * mm, buyer.get("name") or "")
    c.setFont(regular, 8.5)
    blines = [
        buyer.get("contact"),
        buyer.get("address_line1"),
        buyer.get("address_line2"),
        " ".join(p for p in (buyer.get("postal_code"), buyer.get("city")) if p),
        f"SIREN {buyer['siren']}" if buyer.get("siren") else None,
        f"TVA {buyer['vat_number']}" if buyer.get("vat_number") else None,
    ]
    byy = by - 9.5 * mm
    for text in filter(None, blines):
        c.drawString(bx, byy, text)
        byy -= 4 * mm
    delivery = buyer.get("delivery")
    if delivery:
        byy -= 2 * mm
        c.setFillColor(MUTED)
        c.drawString(bx, byy, "Adresse de livraison")
        c.setFillColor(INK)
        byy -= 4 * mm
        for text in filter(None, [delivery.get("line1"), " ".join(p for p in (delivery.get("postal_code"), delivery.get("city")) if p)]):
            c.drawString(bx, byy, text)
            byy -= 4 * mm

    # nature of the operation (mandatory mention)
    ty = byy - 8 * mm
    c.setFont(regular, 8.5)
    c.setFillColor(MUTED)
    c.drawString(left, ty, f"Nature de l'opération : {NATURE_LABEL[doc.nature]}")
    if doc.vat_on_debits and not franchise:
        c.drawString(left + 90 * mm, ty, "Option pour le paiement de la TVA d'après les débits")
    ty -= 7 * mm

    # lines table
    cols = [left, left + 98 * mm, left + 118 * mm, left + 140 * mm, right]
    c.setFillColor(INK)
    c.setFont(bold, 8.5)
    headers = ["Désignation", "Qté", "PU HT" if not franchise else "Prix unit.", "TVA" if not franchise else "", "Total HT" if not franchise else "Total"]
    c.drawString(cols[0], ty, headers[0])
    c.drawRightString(cols[1] + 14 * mm, ty, headers[1])
    c.drawRightString(cols[2] + 18 * mm, ty, headers[2])
    if headers[3]:
        c.drawRightString(cols[3] + 12 * mm, ty, headers[3])
    c.drawRightString(cols[4], ty, headers[4])
    ty -= 2.5 * mm
    c.setStrokeColor(RULE)
    c.setLineWidth(0.5)
    c.line(left, ty, right, ty)
    ty -= 5 * mm
    c.setFont(regular, 9)
    for line in doc.lines:
        if ty < 60 * mm:
            c.showPage()
            ty = height - 25 * mm
            c.setFont(regular, 9)
        c.drawString(cols[0], ty, line.description[:70])
        c.drawRightString(cols[1] + 14 * mm, ty, _fr_num(line.quantity))
        c.drawRightString(cols[2] + 18 * mm, ty, _fr_money(line.unit_price_ht))
        if not franchise:
            c.drawRightString(cols[3] + 12 * mm, ty, f"{_fr_num(line.vat_rate)} %")
        c.drawRightString(cols[4], ty, _fr_money(line_total(line)))
        ty -= 6 * mm
    c.line(left, ty + 2 * mm, right, ty + 2 * mm)

    # totals
    ty -= 4 * mm
    rows: list[tuple[str, str, bool]] = []
    if franchise:
        rows.append(("Total", _fr_money(doc.total_ttc), True))
    else:
        rows.append(("Total HT", _fr_money(doc.total_ht), False))
        for b in vat_breakdown(doc):
            rows.append((f"TVA {_fr_num(b.rate)} % sur {_fr_money(b.base)}", _fr_money(b.amount), False))
        rows.append(("Total TTC", _fr_money(doc.total_ttc), True))
    # deposits already invoiced for this order, then what is left to pay
    for ref in doc.prepaid_refs or []:
        rows.append((f"Acompte facturé {ref['number']} du {_fr_date(date.fromisoformat(ref['date']))}", "− " + _fr_money(Decimal(ref["amount"])), False))
    if doc.prepaid_amount:
        rows.append(("Reste à payer", _fr_money(doc.total_ttc - doc.prepaid_amount), True))
    for label, value, strong in rows:
        c.setFont(bold if strong else regular, 10 if strong else 9)
        c.drawRightString(right - 35 * mm, ty, label)
        c.drawRightString(right, ty, value)
        ty -= 5.5 * mm
    if franchise:
        c.setFont(regular, 8.5)
        c.drawRightString(right, ty, FRANCHISE_MENTION)
        ty -= 5 * mm

    # notes and legal mentions (footer)
    fy = 42 * mm
    c.setFont(regular, 7.5)
    c.setFillColor(MUTED)
    legal = []
    if doc.notes:
        legal.append(doc.notes)
    if doc.kind != DocumentKind.QUOTE:
        legal.append("Pas d'escompte pour paiement anticipé.")
        legal.append((seller.get("late_penalty_text") or "") + ".")
        if buyer.get("is_business"):
            legal.append(B2B_RECOVERY_FEE + ".")
        if seller.get("iban"):
            legal.append(f"Règlement par virement : IBAN {seller['iban']}" + (f" · BIC {seller['bic']}" if seller.get("bic") else ""))
    else:
        legal.append("Devis gratuit. Bon pour accord : date et signature du client.")
    for text in legal:
        for chunk in _wrap(text, 130):
            c.drawString(left, fy, chunk)
            fy -= 3.6 * mm
    if draft:
        c.saveState()
        c.setFont(bold, 60)
        c.setFillColor(HexColor("#e3dfd5"))
        c.translate(width / 2, height / 2)
        c.rotate(35)
        c.drawCentredString(0, 0, "BROUILLON")
        c.restoreState()
    c.showPage()
    c.save()
    return buf.getvalue()


def _wrap(text: str, width: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines


def _with_srgb_output_intent(pdf: bytes) -> bytes:
    """PDF/A requires device colours to be tied to a colour profile (ISO 19005-3, 6.2.4.3): the
    page is drawn in DeviceRGB, so the file declares an sRGB output intent."""
    from PIL import ImageCms
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject, StreamObject, TextStringObject

    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf)))
    icc = StreamObject()
    icc.set_data(ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
    icc[NameObject("/N")] = NumberObject(3)
    intent = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/OutputIntent"),
            NameObject("/S"): NameObject("/GTS_PDFA1"),
            NameObject("/OutputConditionIdentifier"): TextStringObject("sRGB"),
            NameObject("/Info"): TextStringObject("sRGB IEC61966-2.1"),
            NameObject("/DestOutputProfile"): writer._add_object(icc),
        }
    )
    writer._root_object[NameObject("/OutputIntents")] = ArrayObject([writer._add_object(intent)])
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def facturx_pdf(doc: SalesDocument, *, logo: str | None = None, corrected_number: str | None = None, corrected_date: date | None = None) -> bytes:
    """The PDF/A-3 with the XML embedded, checked against the Factur-X EN 16931 schema."""
    from facturx import generate_from_binary

    pdf = _with_srgb_output_intent(render_pdf(doc, logo=logo, corrected_number=corrected_number))
    xml = build_cii_xml(doc, corrected_number=corrected_number, corrected_date=corrected_date).encode("utf-8")
    return generate_from_binary(
        pdf,
        xml,
        flavor="factur-x",
        level="en16931",
        check_xsd=True,
        pdf_metadata={
            "author": (doc.seller_snapshot or {}).get("name") or "KnifeForge Pro",
            "keywords": "Factur-X",
            "title": f"{title_of(doc)} {doc.number}",
            "subject": f"{title_of(doc)} {doc.number}",
        },
    )
