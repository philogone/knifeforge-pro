"""workshop identity on the client plan

Revision ID: 004
Revises: 003
Create Date: 2026-11-07

"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shop_settings", sa.Column("workshop_name", sa.String(120), nullable=True))
    op.add_column("shop_settings", sa.Column("workshop_contact", sa.String(200), nullable=True))
    op.add_column("shop_settings", sa.Column("workshop_logo", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("shop_settings", "workshop_logo")
    op.drop_column("shop_settings", "workshop_contact")
    op.drop_column("shop_settings", "workshop_name")
