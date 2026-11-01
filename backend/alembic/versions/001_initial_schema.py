"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-08-19

"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saw_blades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("saw_type", sa.Enum("band_saw", "circular_saw", "abrasive_cutoff", "hacksaw", "other", name="saw_type"), nullable=False),
        sa.Column("diameter_mm", sa.Float(), nullable=True),
        sa.Column("kerf_mm", sa.Float(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_mock", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("category", sa.Enum("blade_steel", "handle_material", "fitting", "hardware", "consumable", name="material_category"), nullable=False),
        sa.Column("dimension_type", sa.Enum("length", "area", "count", name="dimension_type"), nullable=False),
        sa.Column("metal_type", sa.Enum("stainless_steel", "carbon_steel", "titanium", "mokume_gane", "brass", "copper", "nickel_silver", "other", name="metal_type"), nullable=True),
        sa.Column("steel_grade", sa.String(50), nullable=True),
        sa.Column("wood_species", sa.String(100), nullable=True),
        sa.Column("wood_grade", sa.String(100), nullable=True),
        sa.Column("piece_type", sa.String(150), nullable=True),
        sa.Column("standard_length_mm", sa.Float(), nullable=True),
        sa.Column("standard_width_mm", sa.Float(), nullable=True),
        sa.Column("standard_thickness_mm", sa.Float(), nullable=True),
        sa.Column("kerf_mm", sa.Float(), nullable=False, server_default="2.0"),
        sa.Column("saw_blade_id", sa.Integer(), sa.ForeignKey("saw_blades.id", ondelete="SET NULL"), nullable=True),
        sa.Column("quantity_in_stock", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("low_stock_threshold", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("unit_cost", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("is_mock", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "treatment_recipes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column(
            "treatment_type",
            sa.Enum("heat_treatment", "damascus_etch", "bluing", "browning", "acid_patina", "other", name="treatment_type"),
            nullable=False,
        ),
        sa.Column("applies_to", sa.String(150), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_mock", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "treatment_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("treatment_recipes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("temperature_c", sa.Float(), nullable=True),
        sa.Column("duration_minutes", sa.Float(), nullable=True),
        sa.Column("medium", sa.String(150), nullable=True),
    )

    op.create_table(
        "knife_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("knife_type", sa.Enum("fixed", "folder", "kitchen", "table", "japanese", "other", name="knife_type"), nullable=False, server_default="fixed"),
        sa.Column("base_labor_hours", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("sale_price", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("margin_percent_override", sa.Float(), nullable=True),
        sa.Column("is_mock", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "knife_model_materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("knife_model_id", sa.Integer(), sa.ForeignKey("knife_models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("role", sa.Enum("blade", "handle", "fitting", "hardware", "other", name="material_role"), nullable=False, server_default="other"),
        sa.Column("blank_length_mm", sa.Float(), nullable=True),
        sa.Column("blank_width_mm", sa.Float(), nullable=True),
        sa.Column("blank_thickness_mm", sa.Float(), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="1.0"),
    )

    op.create_table(
        "knife_model_treatments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("knife_model_id", sa.Integer(), sa.ForeignKey("knife_models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("treatment_recipe_id", sa.Integer(), sa.ForeignKey("treatment_recipes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_name", sa.String(150), nullable=False),
        sa.Column("customer_email", sa.String(255), nullable=True),
        sa.Column("status", sa.Enum("draft", "confirmed", "completed", "cancelled", name="order_status"), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_mock", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_orders_status", "orders", ["status"])

    op.create_table(
        "order_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knife_model_id", sa.Integer(), sa.ForeignKey("knife_models.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
    )

    op.create_table(
        "shop_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hourly_rate", sa.Float(), nullable=False, server_default="35.0"),
        sa.Column("default_margin_percent", sa.Float(), nullable=False, server_default="30.0"),
        sa.CheckConstraint("id = 1", name="shop_settings_singleton"),
    )


def downgrade() -> None:
    op.drop_table("shop_settings")
    op.drop_table("order_lines")
    op.drop_table("orders")
    op.drop_table("knife_model_treatments")
    op.drop_table("knife_model_materials")
    op.drop_table("knife_models")
    op.drop_table("treatment_steps")
    op.drop_table("treatment_recipes")
    op.drop_table("materials")
    op.drop_table("saw_blades")
    sa.Enum(name="order_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="material_role").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="knife_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="treatment_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="metal_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="dimension_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="material_category").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="saw_type").drop(op.get_bind(), checkfirst=True)
