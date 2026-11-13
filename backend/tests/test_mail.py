"""E-mail: documents and reminders sent through the workshop's SMTP account (a fake one here),
with the PDF attached, the wording filled in, and a trace kept."""

import email
from datetime import date, timedelta

import pytest

from app.config import get_settings
from tests.test_invoicing import customer, invoice, seller

SENT: list = []


class FakeSMTP:
    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        if password != "bon-mot-de-passe":
            import smtplib

            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

    def send_message(self, msg):
        SENT.append(email.message_from_bytes(msg.as_bytes()))


@pytest.fixture
def smtp(monkeypatch):
    SENT.clear()
    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)
    s = get_settings()
    saved = {k: getattr(s, k) for k in ("smtp_host", "smtp_user", "smtp_password", "smtp_from", "smtp_from_name")}
    s.smtp_host, s.smtp_user, s.smtp_password = "smtp.example.com", "atelier@example.com", "bon-mot-de-passe"
    s.smtp_from, s.smtp_from_name = "", "Atelier Dupont"
    yield SENT
    for k, v in saved.items():
        setattr(s, k, v)


def issued(client, **extra):
    seller(client)
    c = customer(client)
    doc = invoice(client, c["id"], **extra)
    return client.post(f"/api/admin/documents/{doc['id']}/issue").json()


def test_send_an_invoice_with_its_factur_x(client, smtp):
    doc = issued(client)
    draft = client.get(f"/api/admin/documents/{doc['id']}/mail").json()
    assert draft["to"] == ["camille@example.com"] and draft["configured"]
    assert doc["number"] in draft["subject"] and "Camille Martin" in draft["body"] and "180,00 €" in draft["body"]
    r = client.post(f"/api/admin/documents/{doc['id']}/send", json={"to": draft["to"], "subject": draft["subject"], "body": draft["body"]})
    assert r.status_code == 200, r.text
    msg = smtp[0]
    assert msg["To"] == "camille@example.com" and "Atelier Dupont" in msg["From"]
    attachment = [p for p in msg.walk() if p.get_filename()][0]
    assert attachment.get_filename() == f"facture-{doc['number']}.pdf"
    assert attachment.get_payload(decode=True).startswith(b"%PDF")
    events = r.json()["events"]
    assert events[0]["kind"] == "sent" and events[0]["recipient"] == "camille@example.com"


def test_a_draft_is_not_sent(client, smtp):
    seller(client)
    doc = invoice(client, customer(client)["id"])
    assert client.get(f"/api/admin/documents/{doc['id']}/mail").status_code == 400


def test_reminders_overdue_list_and_levels(client, smtp):
    old = (date.today() - timedelta(days=60)).isoformat()
    due = (date.today() - timedelta(days=30)).isoformat()
    doc = issued(client, issue_date=old, due_date=due)
    overdue = client.get("/api/admin/documents/overdue").json()
    assert [(o["number"], o["overdue_days"], o["next_level"]) for o in overdue] == [(doc["number"], 30, 1)]

    d1 = client.get(f"/api/admin/documents/{doc['id']}/mail?purpose=1").json()
    assert "Rappel" in d1["subject"] and "180,00 €" in d1["body"]
    r = client.post(f"/api/admin/documents/{doc['id']}/reminders", json={"level": 1, "to": d1["to"], "subject": d1["subject"], "body": d1["body"]})
    assert r.status_code == 201, r.text
    # second reminder made by phone: noted, nothing sent
    r = client.post(f"/api/admin/documents/{doc['id']}/reminders", json={"level": 2, "channel": "phone", "note": "Promet un virement vendredi"})
    assert r.status_code == 201 and len(smtp) == 1
    overdue = client.get("/api/admin/documents/overdue").json()
    assert overdue[0]["reminders"] == 2 and overdue[0]["last_reminder_level"] == 2 and overdue[0]["next_level"] == 3
    d3 = client.get(f"/api/admin/documents/{doc['id']}/mail?purpose=3").json()
    assert "mettons en demeure" in d3["body"] and "30 jours" not in d3["body"]

    # paid: no longer overdue, no more reminders
    client.post(f"/api/admin/documents/{doc['id']}/payments", json={"paid_on": date.today().isoformat(), "amount": "180.00"})
    assert client.get("/api/admin/documents/overdue").json() == []
    assert client.post(f"/api/admin/documents/{doc['id']}/reminders", json={"level": 3, "channel": "letter"}).status_code == 400


def test_workshop_wording_replaces_the_built_in_one(client, smtp):
    client.patch("/api/admin/settings/shop", json={"email_send_template": "Salut {client}, voici {type} {numero}. {inconnu}"})
    doc = issued(client)
    body = client.get(f"/api/admin/documents/{doc['id']}/mail").json()["body"]
    assert body.startswith(f"Salut Camille Martin, voici la facture {doc['number']}. {{inconnu}}")


def test_mail_errors_are_readable(client, smtp):
    get_settings().smtp_password = "mauvais"
    doc = issued(client)
    r = client.post(f"/api/admin/documents/{doc['id']}/send", json={"to": ["camille@example.com"], "subject": "x", "body": "y"})
    assert r.status_code == 502 and "password" in r.json()["detail"]
    assert client.get(f"/api/admin/documents/{doc['id']}").json()["events"] == []  # nothing logged when nothing left


def test_mail_settings_docker_is_read_only(client, smtp):
    out = client.get("/api/admin/settings/mail").json()
    assert out["configured"] and out["password_set"] and not out["editable"] and "password" not in out
    assert client.put("/api/admin/settings/mail", json={"host": "x"}).status_code == 409
    assert client.post("/api/admin/settings/mail/test", json={"to": "moi@example.com"}).status_code == 200
    assert smtp[-1]["Subject"] == "KnifeForge Pro : message d'essai"
