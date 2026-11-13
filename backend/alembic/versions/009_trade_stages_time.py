"""trade profile (knifemaker / blacksmith), workshop stages set by the workshop, time spent

Revision ID: 009
Revises: 008
Create Date: 2026-11-13

"""
from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None

ORDER_STAGE = ("todo", "forging", "heat_treatment", "grinding", "handle", "finishing", "ready", "delivered")


def upgrade() -> None:
    # the stage becomes a key of the workshop's own list (settings), no longer a fixed enum
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE orders ALTER COLUMN stage DROP DEFAULT")
        op.execute("ALTER TABLE orders ALTER COLUMN stage TYPE VARCHAR(40) USING stage::text")
        op.execute("ALTER TABLE orders ALTER COLUMN stage SET DEFAULT 'todo'")
        op.execute("DROP TYPE IF EXISTS order_stage")
    else:
        with op.batch_alter_table("orders") as batch:
            batch.alter_column("stage", existing_type=sa.Enum(*ORDER_STAGE, name="order_stage"), type_=sa.String(40),
                               existing_nullable=False, server_default="todo")

    with op.batch_alter_table("shop_settings") as batch:
        batch.add_column(sa.Column("trade", sa.String(20), nullable=False, server_default="knifemaker"))
        batch.add_column(sa.Column("workshop_stages", sa.JSON()))

    op.create_table(
        "time_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("worked_on", sa.Date(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(40)),
        sa.Column("note", sa.String(300)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_time_entries_order_id", "time_entries", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_time_entries_order_id", "time_entries")
    op.drop_table("time_entries")
    with op.batch_alter_table("shop_settings") as batch:
        batch.drop_column("workshop_stages")
        batch.drop_column("trade")
    # custom stages fall back to "todo" so the enum can come back
    op.execute("UPDATE orders SET stage = 'todo' WHERE stage NOT IN (" + ", ".join(f"'{s}'" for s in ORDER_STAGE) + ")")
    if op.get_bind().dialect.name == "postgresql":
        sa.Enum(*ORDER_STAGE, name="order_stage").create(op.get_bind(), checkfirst=True)
        op.execute("ALTER TABLE orders ALTER COLUMN stage DROP DEFAULT")
        op.execute("ALTER TABLE orders ALTER COLUMN stage TYPE order_stage USING stage::order_stage")
        op.execute("ALTER TABLE orders ALTER COLUMN stage SET DEFAULT 'todo'")
    else:
        with op.batch_alter_table("orders") as batch:
            batch.alter_column("stage", existing_type=sa.String(40), type_=sa.Enum(*ORDER_STAGE, name="order_stage"),
                               existing_nullable=False, server_default="todo")
