"""first-run wizard flag

Revision ID: 005
Revises: 004
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shop_settings", sa.Column("onboarding_done", sa.Boolean(), nullable=False, server_default=sa.false()))
    # installations that already have data were set up before the wizard existed
    op.execute("UPDATE shop_settings SET onboarding_done = true WHERE EXISTS (SELECT 1 FROM materials WHERE is_mock = false)")


def downgrade() -> None:
    op.drop_column("shop_settings", "onboarding_done")
