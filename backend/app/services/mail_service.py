"""Sending documents and payment reminders by e-mail, through the workshop's own SMTP account.

The account (server, user, password) comes from the environment (Docker) or config.json
(desktop build), never from the database or a backup. Messages are plain text in the
workshop's words: built-in wording, replaced by Settings › E-mail when filled in. Placeholders
in braces ({client}, {numero}…) are filled from the document; an unknown one stays as typed.
"""

from __future__ import annotations

import smtplib
import ssl
from datetime import date
from decimal import Decimal
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app.config import Settings
from app.models.sales_document import DocumentKind, SalesDocument
from app.models.shop_settings import ShopSettings
from app.services.billing_service import balance_due, overdue_days

TIMEOUT_S = 20

PLACEHOLDERS = ("client", "type", "numero", "date", "montant", "reste", "echeance", "jours_retard", "atelier", "iban")

DEFAULT_SEND = """Bonjour {client},

Veuillez trouver ci-joint {type} {numero} du {date}, d'un montant de {montant}.
{echeance_phrase}
Je reste à votre disposition pour toute question.

Cordialement,
{atelier}"""

DEFAULT_REMINDERS = {
    "1": """Bonjour {client},

Sauf erreur ou omission de notre part, la facture {numero} du {date}, arrivée à échéance le {echeance}, n'a pas encore été réglée : il reste {reste} à payer.

Si le règlement est déjà parti, merci de ne pas tenir compte de ce message. Vous trouverez la facture en pièce jointe.

Cordialement,
{atelier}""",
    "2": """Bonjour {client},

Malgré notre précédent rappel, la facture {numero} du {date} reste impayée : {reste}, échue depuis {jours_retard} jours (échéance du {echeance}).

Merci de procéder au règlement dans les meilleurs délais{iban_phrase}. Passé ce délai, des pénalités de retard pourront être appliquées, comme le prévoient nos conditions.

Cordialement,
{atelier}""",
    "3": """Madame, Monsieur,

Malgré nos relances, la facture {numero} du {date} reste impayée à ce jour : {reste}, échue depuis le {echeance}.

Par la présente, nous vous mettons en demeure de régler cette somme sous huit jours à compter de la réception de ce courrier{iban_phrase}. À défaut, nous engagerons les démarches de recouvrement, et les pénalités de retard prévues sur la facture seront dues{indemnite_phrase}.

{atelier}""",
}

SUBJECTS = {
    "send": "{type_titre} {numero} — {atelier}",
    "1": "Rappel : facture {numero}",
    "2": "Deuxième rappel : facture {numero} impayée",
    "3": "Mise en demeure de payer : facture {numero}",
}

ARTICLE = {"Facture": "la facture", "Facture d'acompte": "la facture d'acompte", "Avoir": "l'avoir", "Devis": "le devis"}


class MailError(RuntimeError):
    pass


class _Keep(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _fr_money(value: Decimal) -> str:
    return f"{value:,.2f}".replace(",", " ").replace(".", ",") + " €"


def _fr_date(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def fields(doc: SalesDocument, shop: ShopSettings) -> dict[str, str]:
    from app.services.facturx_service import title_of

    title = title_of(doc)
    buyer = doc.buyer_snapshot or {}
    seller = doc.seller_snapshot or {}
    due = balance_due(doc)
    iban = seller.get("iban") or shop.iban or ""
    values = {
        "client": buyer.get("name") or "",
        "type": ARTICLE.get(title, title.lower()),
        "type_titre": title,
        "numero": doc.number or "",
        "date": _fr_date(doc.issue_date),
        "montant": _fr_money(doc.total_ttc - (doc.prepaid_amount or 0)),
        "reste": _fr_money(due),
        "echeance": _fr_date(doc.due_date),
        "jours_retard": str(overdue_days(doc)),
        "atelier": seller.get("name") or shop.legal_name or shop.workshop_name or "",
        "iban": iban,
    }
    values["echeance_phrase"] = (
        f"Règlement attendu au plus tard le {values['echeance']}." if doc.kind == DocumentKind.INVOICE and doc.due_date else ""
    )
    values["iban_phrase"] = f", par virement sur le compte IBAN {iban}" if iban else ""
    values["indemnite_phrase"] = (
        ", ainsi que l'indemnité forfaitaire pour frais de recouvrement de 40 €" if buyer.get("is_business") else ""
    )
    return values


def draft(doc: SalesDocument, shop: ShopSettings, purpose: str) -> tuple[str, str]:
    """(subject, body) for "send" or a reminder level "1" / "2" / "3"."""
    if purpose == "send":
        body = shop.email_send_template or DEFAULT_SEND
    else:
        body = (shop.reminder_templates or {}).get(purpose) or DEFAULT_REMINDERS[purpose]
    values = _Keep(fields(doc, shop))
    return SUBJECTS[purpose].format_map(values), body.format_map(values).strip() + "\n"


def configured(settings: Settings) -> bool:
    return bool(settings.smtp_host and (settings.smtp_from or settings.smtp_user))


def send(settings: Settings, to: list[str], subject: str, body: str, cc: list[str] | None = None,
         attachments: list[tuple[str, bytes, str]] | None = None) -> str:
    """Send one message; returns its Message-ID. Raises MailError with a readable reason."""
    if not configured(settings):
        raise MailError("E-mail is not set up")
    sender = settings.smtp_from or settings.smtp_user
    msg = EmailMessage()
    msg["From"] = formataddr((settings.smtp_from_name, sender)) if settings.smtp_from_name else sender
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=sender.split("@")[-1] if "@" in sender else None)
    msg.set_content(body)
    for name, data, mime in attachments or []:
        main, sub = mime.split("/", 1)
        msg.add_attachment(data, maintype=main, subtype=sub, filename=name)
    try:
        if settings.smtp_security == "ssl":
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=TIMEOUT_S, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=TIMEOUT_S)
        with server:
            if settings.smtp_security == "starttls":
                server.starttls(context=ssl.create_default_context())
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        raise MailError("The mail server refused the user name or password") from exc
    except smtplib.SMTPRecipientsRefused as exc:
        raise MailError("The mail server refused the recipient address") from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise MailError(f"Could not send through {settings.smtp_host}:{settings.smtp_port} ({exc.__class__.__name__}: {exc})") from exc
    return msg["Message-ID"]
