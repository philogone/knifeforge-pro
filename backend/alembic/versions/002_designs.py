"""vector designs (patterns) for the built-in editor

Revision ID: 002
Revises: 001
Create Date: 2026-11-01

"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "designs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("blade", "handle_scale", "guard", "bolster", "sheath", "template", "other", name="design_kind"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("knife_model_id", sa.Integer(), sa.ForeignKey("knife_models.id", ondelete="SET NULL"), nullable=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id", ondelete="SET NULL"), nullable=True),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("width_mm", sa.Float(), nullable=False, server_default="0"),
        sa.Column("height_mm", sa.Float(), nullable=False, server_default="0"),
        sa.Column("area_mm2", sa.Float(), nullable=False, server_default="0"),
        sa.Column("perimeter_mm", sa.Float(), nullable=False, server_default="0"),
        sa.Column("part_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_mock", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_designs_knife_model_id", "designs", ["knife_model_id"])
    op.create_index("ix_designs_material_id", "designs", ["material_id"])


def downgrade() -> None:
    op.drop_index("ix_designs_material_id", table_name="designs")
    op.drop_index("ix_designs_knife_model_id", table_name="designs")
    op.drop_table("designs")
    sa.Enum(name="design_kind").drop(op.get_bind(), checkfirst=True)
