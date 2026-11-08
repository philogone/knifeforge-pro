"""customers, order tracking, stock ledger, quotes / invoices / credit notes, seller identity

Revision ID: 006
Revises: 005
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

ORDER_STAGE = ("todo", "forging", "heat_treatment", "grinding", "handle", "finishing", "ready", "delivered")


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("is_business", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("company_name", sa.String(150)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(40)),
        sa.Column("address_line1", sa.String(200)),
        sa.Column("address_line2", sa.String(200)),
        sa.Column("postal_code", sa.String(20)),
        sa.Column("city", sa.String(100)),
        sa.Column("country", sa.String(2), nullable=False, server_default="FR"),
        sa.Column("delivery_line1", sa.String(200)),
        sa.Column("delivery_postal_code", sa.String(20)),
        sa.Column("delivery_city", sa.String(100)),
        sa.Column("delivery_country", sa.String(2)),
        sa.Column("siren", sa.String(9)),
        sa.Column("vat_number", sa.String(20)),
        sa.Column("notes", sa.Text()),
        sa.Column("anonymized_at", sa.DateTime(timezone=True)),
        sa.Column("is_mock", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    # add_column does not create a PostgreSQL enum type by itself (create_table does)
    sa.Enum(*ORDER_STAGE, name="order_stage").create(op.get_bind(), checkfirst=True)
    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="SET NULL", name="fk_orders_customer_id")))
        batch.add_column(sa.Column("due_date", sa.Date()))
        batch.add_column(sa.Column("stage", sa.Enum(*ORDER_STAGE, name="order_stage"), nullable=False, server_default="todo"))
        batch.create_index("ix_orders_customer_id", ["customer_id"])

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("delta", sa.Float(), nullable=False),
        sa.Column("balance_after", sa.Float(), nullable=False),
        sa.Column(
            "reason",
            sa.Enum("restock", "correction", "order_confirmed", "order_cancelled", "initial", name="movement_reason"),
            nullable=False,
        ),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="SET NULL")),
        sa.Column("cost", sa.Float()),
        sa.Column("note", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), index=True),
    )

    op.create_table(
        "sales_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.Enum("quote", "invoice", "credit_note", name="document_kind"), nullable=False),
        sa.Column("status", sa.Enum("draft", "issued", "accepted", "refused", "paid", name="document_status"), nullable=False),
        sa.Column("number", sa.String(30)),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="SET NULL")),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="SET NULL")),
        sa.Column("corrects_id", sa.Integer(), sa.ForeignKey("sales_documents.id", ondelete="RESTRICT")),
        sa.Column("issue_date", sa.Date()),
        sa.Column("due_date", sa.Date()),
        sa.Column("delivery_date", sa.Date()),
        sa.Column("valid_until", sa.Date()),
        sa.Column("nature", sa.Enum("goods", "services", "mixed", name="operation_nature"), nullable=False),
        sa.Column("vat_on_debits", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text()),
        sa.Column("seller_snapshot", sa.JSON()),
        sa.Column("buyer_snapshot", sa.JSON()),
        sa.Column("total_ht", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_vat", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_ttc", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("paid_at", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("issued_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("kind", "number", name="uq_sales_document_number"),
    )
    op.create_table(
        "sales_document_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("sales_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False, server_default="1"),
        sa.Column("unit", sa.String(10), nullable=False, server_default="C62"),
        sa.Column("unit_price_ht", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
    )
    op.create_table(
        "document_counters",
        sa.Column("kind", sa.String(20), primary_key=True),
        sa.Column("year", sa.Integer(), primary_key=True),
        sa.Column("last", sa.Integer(), nullable=False, server_default="0"),
    )

    with op.batch_alter_table("shop_settings") as batch:
        batch.add_column(sa.Column("legal_name", sa.String(150)))
        batch.add_column(sa.Column("address_line1", sa.String(200)))
        batch.add_column(sa.Column("postal_code", sa.String(20)))
        batch.add_column(sa.Column("city", sa.String(100)))
        batch.add_column(sa.Column("country", sa.String(2), nullable=False, server_default="FR"))
        batch.add_column(sa.Column("siren", sa.String(9)))
        batch.add_column(sa.Column("siret", sa.String(14)))
        batch.add_column(sa.Column("vat_regime", sa.String(10), nullable=False, server_default="franchise"))
        batch.add_column(sa.Column("vat_number", sa.String(20)))
        batch.add_column(sa.Column("default_vat_rate", sa.Float(), nullable=False, server_default="20"))
        batch.add_column(sa.Column("trade_register", sa.String(120)))
        batch.add_column(sa.Column("iban", sa.String(34)))
        batch.add_column(sa.Column("bic", sa.String(11)))
        batch.add_column(sa.Column("payment_terms_days", sa.Integer(), nullable=False, server_default="30"))
        batch.add_column(sa.Column("late_penalty_text", sa.String(300)))
        batch.add_column(sa.Column("quote_validity_days", sa.Integer(), nullable=False, server_default="30"))


def downgrade() -> None:
    with op.batch_alter_table("shop_settings") as batch:
        for col in (
            "quote_validity_days", "late_penalty_text", "payment_terms_days", "bic", "iban", "trade_register",
            "default_vat_rate", "vat_number", "vat_regime", "siret", "siren", "country", "city", "postal_code",
            "address_line1", "legal_name",
        ):
            batch.drop_column(col)
    op.drop_table("document_counters")
    op.drop_table("sales_document_lines")
    op.drop_table("sales_documents")
    op.drop_table("stock_movements")
    with op.batch_alter_table("orders") as batch:
        batch.drop_index("ix_orders_customer_id")
        batch.drop_column("stage")
        batch.drop_column("due_date")
        batch.drop_constraint("fk_orders_customer_id", type_="foreignkey")
        batch.drop_column("customer_id")
    op.drop_table("customers")
    for enum_name in ("order_stage", "movement_reason", "document_kind", "document_status", "operation_nature"):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
