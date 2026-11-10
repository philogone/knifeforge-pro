"""created_at NOT NULL on customers, sales documents and stock movements

Migration 006 created these three columns nullable while the models require a value (always
set by the application). Batch mode rebuilds the table on SQLite, which cannot alter a column;
on PostgreSQL it is a plain ALTER COLUMN.

Revision ID: 007
Revises: 006
Create Date: 2026-11-10

"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

TABLES = ("customers", "sales_documents", "stock_movements")


def upgrade() -> None:
    for table in TABLES:
        # rows written outside the app (none expected) get their creation time now rather than fail
        op.execute(f"UPDATE {table} SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        with op.batch_alter_table(table) as batch:
            batch.alter_column("created_at", existing_type=sa.DateTime(timezone=True), nullable=False)


def downgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.alter_column("created_at", existing_type=sa.DateTime(timezone=True), nullable=True)
