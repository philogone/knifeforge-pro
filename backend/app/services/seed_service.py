"""Demo data: saw blades, materials, treatment recipes (thermal and
chemical/finishing), knife models, and orders in different lifecycle
states — seeded through the real order_service functions (not raw INSERTs)
so the demo data is itself a live self-check that confirm/cancel and the
stock math behave correctly on every startup.
"""

import logging

from sqlalchemy.orm import Session

from app.models.knife_model import KnifeModel, KnifeModelMaterial, KnifeModelTreatment, KnifeType, MaterialRole
from app.models.material import DimensionType, Material, MaterialCategory, MetalType
from app.models.order import Order, OrderLine
from app.models.saw_blade import SawBlade, SawType
from app.models.treatment import TreatmentRecipe, TreatmentStep, TreatmentType
from app.services.order_service import cancel_order, confirm_order

logger = logging.getLogger("knifeforge")


def seed_mock_data(db: Session) -> int:
    if db.query(Material).filter(Material.is_mock.is_(True)).first() is not None:
        return 0

    bandsaw = SawBlade(
        name="Ruban bi-metal 0.65mm",
        saw_type=SawType.BAND_SAW,
        kerf_mm=1.0,
        notes="General-purpose bi-metal blade for steel bar stock.",
        is_mock=True,
    )
    abrasive_saw = SawBlade(
        name="Disque abrasif 355mm",
        saw_type=SawType.ABRASIVE_CUTOFF,
        diameter_mm=355,
        kerf_mm=2.0,
        notes="Chop saw — fast, but a wider kerf than the bandsaw.",
        is_mock=True,
    )
    db.add_all([bandsaw, abrasive_saw])
    db.flush()

    steel_1095 = Material(
        name="1095 High Carbon Steel Bar",
        category=MaterialCategory.BLADE_STEEL,
        dimension_type=DimensionType.LENGTH,
        metal_type=MetalType.CARBON_STEEL,
        steel_grade="XC100 (AISI 1095)",
        standard_length_mm=1000,
        standard_width_mm=50,
        standard_thickness_mm=4,
        kerf_mm=bandsaw.kerf_mm,
        saw_blade_id=bandsaw.id,
        quantity_in_stock=5000,
        low_stock_threshold=1000,
        unit_cost=0.045,  # EUR/mm -- a 1000mm bar costs 45 EUR landed
        is_mock=True,
    )
    damascus = Material(
        name="Damascus Pattern-Welded Billet (1080/15N20)",
        category=MaterialCategory.BLADE_STEEL,
        dimension_type=DimensionType.LENGTH,
        metal_type=MetalType.CARBON_STEEL,
        steel_grade="Damas 1080/15N20",
        standard_length_mm=800,
        standard_width_mm=45,
        standard_thickness_mm=5,
        kerf_mm=abrasive_saw.kerf_mm,
        saw_blade_id=abrasive_saw.id,
        quantity_in_stock=1600,
        low_stock_threshold=400,
        unit_cost=0.15,  # EUR/mm -- an 800mm billet costs 120 EUR landed
        is_mock=True,
    )
    walnut = Material(
        name="Walnut Handle Scales",
        category=MaterialCategory.HANDLE_MATERIAL,
        dimension_type=DimensionType.COUNT,
        wood_species="Noyer (Walnut)",
        wood_grade="AAA madre",
        piece_type="Jeu de plaquettes",
        standard_length_mm=130,
        standard_width_mm=40,
        standard_thickness_mm=10,
        quantity_in_stock=20,
        low_stock_threshold=5,
        unit_cost=12.0,
        is_mock=True,
    )
    g10 = Material(
        name="G10 Sheet, Black",
        category=MaterialCategory.HANDLE_MATERIAL,
        dimension_type=DimensionType.AREA,
        piece_type="Plaque",
        standard_length_mm=300,
        standard_width_mm=150,
        standard_thickness_mm=6,
        quantity_in_stock=90000,
        low_stock_threshold=45000,
        unit_cost=0.000778,  # EUR/mm^2 -- a 300x150mm sheet costs ~35 EUR landed
        is_mock=True,
    )
    pins = Material(
        name="Brass Pins 4mm",
        category=MaterialCategory.HARDWARE,
        dimension_type=DimensionType.COUNT,
        metal_type=MetalType.BRASS,
        piece_type="Rivet tubulaire",
        standard_length_mm=25,
        standard_thickness_mm=4,
        quantity_in_stock=200,
        low_stock_threshold=20,
        unit_cost=0.5,
        is_mock=True,
    )
    mitre = Material(
        name="Mitre Maillechort",
        category=MaterialCategory.FITTING,
        dimension_type=DimensionType.COUNT,
        metal_type=MetalType.NICKEL_SILVER,
        piece_type="Mitre",
        standard_length_mm=25,
        standard_width_mm=20,
        standard_thickness_mm=8,
        quantity_in_stock=10,
        low_stock_threshold=2,
        unit_cost=8.0,
        is_mock=True,
    )
    grinding_disc = Material(
        name="Disque de meulage Ø115mm",
        category=MaterialCategory.CONSUMABLE,
        dimension_type=DimensionType.COUNT,
        piece_type="Disque abrasif",
        # Stock is tracked as fractional "whole discs' worth of life
        # remaining", not a literal disc count -- see HANDOVER.md on how
        # tool wear (belts, grinding discs) folds into material costing.
        quantity_in_stock=1.0,
        low_stock_threshold=0.1,
        unit_cost=16.0,  # EUR per disc's full working life
        is_mock=True,
    )
    db.add_all([steel_1095, damascus, walnut, g10, pins, mitre, grinding_disc])
    db.flush()

    quench_temper_1095 = TreatmentRecipe(
        name="1095 Quench & Temper",
        treatment_type=TreatmentType.HEAT_TREATMENT,
        applies_to="1095 / high-carbon steel",
        notes="Standard non-stainless simple steel heat treat.",
        is_mock=True,
        steps=[
            TreatmentStep(step_order=1, description="Normalize three times, air cool between cycles", temperature_c=815, duration_minutes=10, medium="still air"),
            TreatmentStep(step_order=2, description="Austenitize and quench", temperature_c=815, duration_minutes=5, medium="fast quench oil"),
            TreatmentStep(step_order=3, description="Temper twice, 1h each, air cool between cycles", temperature_c=204, duration_minutes=60, medium="oven air"),
        ],
    )
    quench_temper_damascus = TreatmentRecipe(
        name="Damascus Quench & Temper (1080/15N20)",
        treatment_type=TreatmentType.HEAT_TREATMENT,
        applies_to="Pattern-welded 1080/15N20 damascus",
        notes="Heat-treat the composite billet as a single steel at 1080's parameters.",
        is_mock=True,
        steps=[
            TreatmentStep(step_order=1, description="Austenitize and quench", temperature_c=800, duration_minutes=5, medium="medium-speed quench oil"),
            TreatmentStep(step_order=2, description="Temper twice, 1h each, air cool between cycles", temperature_c=205, duration_minutes=60, medium="oven air"),
        ],
    )
    damascus_etch = TreatmentRecipe(
        name="Ferric Chloride Damascus Etch",
        treatment_type=TreatmentType.DAMASCUS_ETCH,
        applies_to="Pattern-welded damascus billets",
        notes="Reveals the pattern by etching the two steels at different rates.",
        is_mock=True,
        steps=[
            TreatmentStep(step_order=1, description="Degrease blade surface", temperature_c=None, duration_minutes=5, medium="acetone"),
            TreatmentStep(step_order=2, description="Immerse in etchant", temperature_c=20, duration_minutes=15, medium="ferric chloride 1:3 with water"),
            TreatmentStep(step_order=3, description="Neutralize, scrub, oil immediately", temperature_c=None, duration_minutes=5, medium="baking soda solution"),
        ],
    )
    forced_patina = TreatmentRecipe(
        name="Forced Vinegar Patina",
        treatment_type=TreatmentType.ACID_PATINA,
        applies_to="Carbon steel blades, post heat-treat",
        notes="Even gray patina that also protects against blotchy rust patina developing on its own.",
        is_mock=True,
        steps=[
            TreatmentStep(step_order=1, description="Wipe blade with vinegar-soaked cloth, repeat every 10 min", temperature_c=None, duration_minutes=60, medium="white vinegar"),
            TreatmentStep(step_order=2, description="Rinse, neutralize, oil blade", temperature_c=None, duration_minutes=5, medium="water + baking soda"),
        ],
    )
    db.add_all([quench_temper_1095, quench_temper_damascus, damascus_etch, forced_patina])
    db.flush()

    bushcraft = KnifeModel(
        name="Bushcraft 1095 Walnut",
        knife_type=KnifeType.FIXED,
        base_labor_hours=4,
        sale_price=180,
        is_mock=True,
        materials=[
            KnifeModelMaterial(material_id=steel_1095.id, role=MaterialRole.BLADE, blank_length_mm=180, blank_thickness_mm=4),
            KnifeModelMaterial(material_id=walnut.id, role=MaterialRole.HANDLE, quantity=1),
            KnifeModelMaterial(material_id=pins.id, role=MaterialRole.HARDWARE, quantity=2),
            # Grinding one blade profile uses ~1% of one disc's working life.
            KnifeModelMaterial(material_id=grinding_disc.id, role=MaterialRole.OTHER, quantity=0.01),
        ],
        treatments=[
            KnifeModelTreatment(treatment_recipe_id=quench_temper_1095.id, step_order=1),
            KnifeModelTreatment(treatment_recipe_id=forced_patina.id, step_order=2),
        ],
    )
    folder = KnifeModel(
        name="Damascus Gentleman's Folder",
        knife_type=KnifeType.FOLDER,
        base_labor_hours=7,
        sale_price=420,
        # A folder is fussier to build and sells at a higher margin than
        # the shop default -- demonstrates the per-model override.
        margin_percent_override=40.0,
        is_mock=True,
        materials=[
            KnifeModelMaterial(material_id=damascus.id, role=MaterialRole.BLADE, blank_length_mm=120, blank_thickness_mm=5),
            KnifeModelMaterial(material_id=g10.id, role=MaterialRole.HANDLE, blank_length_mm=110, blank_width_mm=25, blank_thickness_mm=6),
            KnifeModelMaterial(material_id=mitre.id, role=MaterialRole.FITTING, quantity=1),
            KnifeModelMaterial(material_id=pins.id, role=MaterialRole.HARDWARE, quantity=2),
        ],
        treatments=[
            KnifeModelTreatment(treatment_recipe_id=quench_temper_damascus.id, step_order=1),
            KnifeModelTreatment(treatment_recipe_id=damascus_etch.id, step_order=2),
        ],
    )
    db.add_all([bushcraft, folder])
    db.flush()

    draft_order = Order(
        customer_name="Alex Dupont",
        customer_email="alex.dupont@example.com",
        notes="Wants a leather sheath included — quote separately.",
        is_mock=True,
        lines=[OrderLine(knife_model_id=bushcraft.id, quantity=2)],
    )
    confirmed_order = Order(
        customer_name="Camille Martin",
        customer_email="camille.martin@example.com",
        is_mock=True,
        lines=[OrderLine(knife_model_id=folder.id, quantity=1)],
    )
    to_cancel_order = Order(
        customer_name="Jordan Leroy",
        customer_email="jordan.leroy@example.com",
        is_mock=True,
        lines=[OrderLine(knife_model_id=bushcraft.id, quantity=1)],
    )
    db.add_all([draft_order, confirmed_order, to_cancel_order])
    db.commit()

    confirm_order(db, confirmed_order)
    confirm_order(db, to_cancel_order)
    cancel_order(db, to_cancel_order)

    logger.info("Seeded mock data: 2 saw blades, 7 materials, 4 treatment recipes, 2 knife models, 3 orders")
    return 7


def clear_mock_data(db: Session) -> int:
    removed = 0
    for model in (Order, KnifeModel, TreatmentRecipe, Material, SawBlade):
        rows = db.query(model).filter(model.is_mock.is_(True)).all()
        removed += len(rows)
        for row in rows:
            db.delete(row)
        db.flush()
    db.commit()
    return removed


def seed_mock_designs(db: Session) -> int:
    """Demo vector patterns for the mock knife models. Separate from
    seed_mock_data so existing demo databases pick the designs up too."""
    from app.models.design import Design, DesignKind
    from app.schemas.design import DesignDocument
    from app.services import design_templates as tpl
    from app.services.geometry_service import compute_metrics

    if db.query(Design).filter(Design.is_mock.is_(True)).first() is not None:
        return 0

    def material(prefix: str):
        return db.query(Material).filter(Material.is_mock.is_(True), Material.name.like(f"{prefix}%")).first()

    def model(prefix: str):
        return db.query(KnifeModel).filter(KnifeModel.is_mock.is_(True), KnifeModel.name.like(f"{prefix}%")).first()

    steel, damascus, g10 = material("1095"), material("Damascus"), material("G10")
    bushcraft, folder = model("Bushcraft"), model("Damascus")
    if steel is None or bushcraft is None:
        return 0

    specs = [
        ("Bushcraft — profil de lame", DesignKind.BLADE, bushcraft, steel, tpl.drop_point_blade()),
        ("Pliant — lame damas", DesignKind.BLADE, folder, damascus, tpl.drop_point_blade(75, 35, 26, 12)),
        ("Pliant — plaquettes G10", DesignKind.HANDLE_SCALE, folder, g10, tpl.handle_scale(110, 25)),
    ]
    created = 0
    for name, kind, knife_model, mat, doc in specs:
        if knife_model is None or mat is None:
            continue
        document = DesignDocument.model_validate(doc)
        metrics = compute_metrics(document)
        db.add(
            Design(
                name=name,
                kind=kind,
                knife_model_id=knife_model.id,
                material_id=mat.id,
                document=document.model_dump(mode="json"),
                width_mm=metrics.width_mm,
                height_mm=metrics.height_mm,
                area_mm2=metrics.area_mm2,
                perimeter_mm=metrics.perimeter_mm,
                part_count=metrics.part_count,
                is_mock=True,
            )
        )
        created += 1
    db.commit()
    return created
