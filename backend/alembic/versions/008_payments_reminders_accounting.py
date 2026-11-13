"""payments, deposit invoices, sending / reminder history, accounting accounts, e-mail wording

Revision ID: 008
Revises: 007
Create Date: 2026-11-13

"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None

PAYMENT_METHOD = ("transfer", "card", "cheque", "cash", "other")
EVENT_KIND = ("sent", "reminder")


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("sales_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("method", sa.Enum(*PAYMENT_METHOD, name="payment_method"), nullable=False, server_default="transfer"),
        sa.Column("reference", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_payments_document_id", "payments", ["document_id"])
    op.create_table(
        "document_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("sales_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.Enum(*EVENT_KIND, name="document_event_kind"), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("channel", sa.String(10), nullable=False, server_default="email"),
        sa.Column("level", sa.Integer()),
        sa.Column("recipient", sa.String(255)),
        sa.Column("subject", sa.String(255)),
        sa.Column("note", sa.Text()),
    )
    op.create_index("ix_document_events_document_id", "document_events", ["document_id"])

    with op.batch_alter_table("sales_documents") as batch:
        batch.add_column(sa.Column("is_deposit", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("prepaid_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("prepaid_refs", sa.JSON()))

    with op.batch_alter_table("shop_settings") as batch:
        batch.add_column(sa.Column("account_customers", sa.String(20), nullable=False, server_default="411000"))
        batch.add_column(sa.Column("account_sales_goods", sa.String(20), nullable=False, server_default="707000"))
        batch.add_column(sa.Column("account_sales_services", sa.String(20), nullable=False, server_default="706000"))
        batch.add_column(sa.Column("account_vat", sa.String(20), nullable=False, server_default="445710"))
        batch.add_column(sa.Column("account_deposits", sa.String(20), nullable=False, server_default="419100"))
        batch.add_column(sa.Column("account_bank", sa.String(20), nullable=False, server_default="512000"))
        batch.add_column(sa.Column("email_send_template", sa.Text()))
        batch.add_column(sa.Column("reminder_templates", sa.JSON()))
        batch.add_column(sa.Column("last_backup_at", sa.DateTime(timezone=True)))

    # invoices already marked paid keep a trace of that payment (date known, method not)
    op.execute(
        "INSERT INTO payments (document_id, paid_on, amount, method, reference, created_at) "
        "SELECT id, paid_at, total_ttc, 'other', 'avant la version 0.10', CURRENT_TIMESTAMP "
        "FROM sales_documents WHERE status = 'paid' AND paid_at IS NOT NULL AND total_ttc > 0"
    )


def downgrade() -> None:
    with op.batch_alter_table("shop_settings") as batch:
        for col in ("last_backup_at", "reminder_templates", "email_send_template", "account_bank", "account_deposits", "account_vat", "account_sales_services", "account_sales_goods", "account_customers"):
            batch.drop_column(col)
    with op.batch_alter_table("sales_documents") as batch:
        for col in ("prepaid_refs", "prepaid_amount", "is_deposit"):
            batch.drop_column(col)
    op.drop_index("ix_document_events_document_id", "document_events")
    op.drop_table("document_events")
    op.drop_index("ix_payments_document_id", "payments")
    op.drop_table("payments")
    sa.Enum(name="document_event_kind").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="payment_method").drop(op.get_bind(), checkfirst=True)
