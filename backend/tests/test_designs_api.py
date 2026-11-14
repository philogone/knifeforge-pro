import copy

from app.core.security import require_admin
from app.main import app
from app.models.knife_model import KnifeModel, KnifeModelMaterial, MaterialRole
from app.models.material import DimensionType, Material, MaterialCategory
from app.models.order import Order, OrderLine, OrderStatus
from app.services import design_templates as tpl
from tests.helpers import simple_blade
from fastapi.testclient import TestClient


def make_material(db, **overrides):
    values = dict(
        name="Barre 1095",
        category=MaterialCategory.BLADE_STEEL,
        dimension_type=DimensionType.LENGTH,
        standard_length_mm=1000,
        standard_width_mm=50,
        standard_thickness_mm=4,
        quantity_in_stock=3000,
    )
    values.update(overrides)
    material = Material(**values)
    db.add(material)
    db.commit()
    return material


def make_model(db, name="Bushcraft"):
    model = KnifeModel(name=name)
    db.add(model)
    db.commit()
    return model


def create_design(client, name="Lame", document=None, **extra):
    body = {"name": name, "kind": "blade", "document": document or simple_blade(), **extra}
    response = client.post("/api/admin/designs", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_requires_admin_auth():
    app.dependency_overrides.pop(require_admin, None)
    assert TestClient(app).get("/api/admin/designs").status_code == 401
    assert TestClient(app).post("/api/admin/nesting/run", json={"material_id": 1}).status_code == 401


def test_create_computes_metrics_and_lists_summaries(client, db):
    material = make_material(db)
    model = make_model(db)
    created = create_design(client, "Lame bushcraft", knife_model_id=model.id, material_id=material.id)
    assert created["width_mm"] == 182 and created["height_mm"] == 32
    assert 4000 < created["area_mm2"] < 4800
    assert created["part_count"] == 1
    assert created["knife_model_name"] == "Bushcraft" and created["material_name"] == "Barre 1095"

    listing = client.get("/api/admin/designs").json()
    assert [d["name"] for d in listing] == ["Lame bushcraft"]
    assert "document" not in listing[0]
    assert client.get(f"/api/admin/designs?material_id={material.id}").json()[0]["id"] == created["id"]
    assert client.get("/api/admin/designs?material_id=999").json() == []


def test_get_update_recomputes_metrics_and_duplicate_and_delete(client):
    created = create_design(client)
    got = client.get(f"/api/admin/designs/{created['id']}").json()
    assert got["document"]["objects"][0]["id"] == "blade"

    bigger = copy.deepcopy(got["document"])
    for node in bigger["objects"][0]["contours"][0]:
        node["x"] *= 2
    patched = client.patch(f"/api/admin/designs/{created['id']}", json={"document": bigger, "name": "Lame XL"}).json()
    assert patched["name"] == "Lame XL" and patched["width_mm"] == 364

    copy_ = client.post(f"/api/admin/designs/{created['id']}/duplicate").json()
    assert copy_["id"] != created["id"] and copy_["name"] == "Lame XL (copie)" and copy_["width_mm"] == 364

    assert client.delete(f"/api/admin/designs/{created['id']}").status_code == 204
    assert client.get(f"/api/admin/designs/{created['id']}").status_code == 404
    assert client.get(f"/api/admin/designs/{copy_['id']}").status_code == 200


def test_rejects_invalid_documents_and_unknown_references(client):
    bad_layer = simple_blade()
    bad_layer["objects"][0]["layer"] = "nope"
    assert client.post("/api/admin/designs", json={"name": "x", "document": bad_layer}).status_code == 422

    no_layers = tpl.blank_document()
    no_layers["layers"] = []
    assert client.post("/api/admin/designs", json={"name": "x", "document": no_layers}).status_code == 422

    huge = simple_blade()
    huge["objects"][0]["contours"][0][0]["x"] = 1e12
    assert client.post("/api/admin/designs", json={"name": "x", "document": huge}).status_code == 422

    assert client.post("/api/admin/designs", json={"name": "x", "document": tpl.blank_document(), "material_id": 99}).status_code == 400
    assert client.get("/api/admin/designs/12345").status_code == 404


def test_deleting_a_material_keeps_the_design(client, db):
    material = make_material(db)
    design = create_design(client, material_id=material.id)
    db.delete(material)
    db.commit()
    got = client.get(f"/api/admin/designs/{design['id']}").json()
    assert got["material_id"] is None


def test_templates_endpoint(client):
    templates = client.get("/api/admin/designs/templates").json()
    assert {t["key"] for t in templates} >= {"blank", "drop-point-blade", "handle-scale"}
    created = client.post("/api/admin/designs", json={"name": "t", "document": templates[1]["document"]})
    assert created.status_code == 201


def test_offset_endpoint(client):
    square = [tpl.node(0, 0), tpl.node(10, 0), tpl.node(10, 10), tpl.node(0, 10)]
    ok = client.post("/api/admin/designs/geometry/offset", json={"contours": [square], "distance_mm": 2, "join": "mitre"})
    assert ok.status_code == 200
    xs = [n["x"] for n in ok.json()["contours"][0]]
    assert min(xs) == -2 and max(xs) == 12
    collapsed = client.post("/api/admin/designs/geometry/offset", json={"contours": [square], "distance_mm": -8})
    assert collapsed.status_code == 422


def test_export_endpoints(client):
    design = create_design(client, "Lame / test")
    svg = client.get(f"/api/admin/designs/{design['id']}/export.svg")
    assert svg.status_code == 200 and svg.headers["content-type"].startswith("image/svg+xml")
    assert 'filename="Lame___test.svg"' in svg.headers["content-disposition"]
    dxf = client.get(f"/api/admin/designs/{design['id']}/export.dxf")
    assert dxf.status_code == 200 and b"LWPOLYLINE" in dxf.content

    plan = client.get(f"/api/admin/designs/{design['id']}/plan.svg", params={"customer": "Alex", "order_ref": "C-1", "paper": "A3"})
    assert plan.status_code == 200 and "Alex" in plan.text and 'width="420mm"' in plan.text
    assert "content-disposition" not in plan.headers
    assert "attachment" in client.get(f"/api/admin/designs/{design['id']}/plan.svg?download=true").headers["content-disposition"]
    assert client.get(f"/api/admin/designs/{design['id']}/plan.svg?paper=B7").status_code == 422

    empty = create_design(client, "Vide", document=tpl.blank_document())
    assert client.get(f"/api/admin/designs/{empty['id']}/export.svg").status_code == 400
    assert client.get(f"/api/admin/designs/{empty['id']}/plan.svg").status_code == 400


def make_order(db, model, quantity, status=OrderStatus.DRAFT, customer="Alex"):
    order = Order(customer_name=customer, status=status)
    order.lines.append(OrderLine(knife_model_id=model.id, quantity=quantity))
    db.add(order)
    db.commit()
    return order


def test_nesting_from_orders_and_explicit_items(client, db):
    steel = make_material(db)
    model = make_model(db)
    other_model = make_model(db, "Autre")
    design = create_design(client, material_id=steel.id, knife_model_id=model.id)
    create_design(client, "Pas la même matière", knife_model_id=model.id)  # no material -> never nested
    make_order(db, model, 3)
    make_order(db, other_model, 5, customer="Sans design")
    make_order(db, model, 4, status=OrderStatus.CANCELLED, customer="Annulée")

    candidates = client.get(f"/api/admin/nesting/candidates?material_id={steel.id}").json()
    assert [(o["customer_name"], o["part_count"]) for o in candidates["orders"]] == [("Alex", 3)]
    assert [d["id"] for d in candidates["designs"]] == [design["id"]]

    result = client.post("/api/admin/nesting/run", json={"material_id": steel.id}).json()
    assert result["total_parts"] == 3 and result["placed_parts"] == 3
    assert result["sheets_needed"] == 1 and result["stock_sufficient"] is True
    assert result["stock_sheets_available"] == 3.0  # 3000 mm of 1000 mm bars
    placement = result["sheets"][0]["placements"][0]
    assert placement["customer_name"] == "Alex" and len(placement["outline"]) == 3  # outline + 2 holes
    assert 0 < result["utilization_pct"] < 100

    none_selected = client.post("/api/admin/nesting/run", json={"material_id": steel.id, "order_ids": []}).json()
    assert none_selected["total_parts"] == 0 and none_selected["sheets_needed"] == 0

    explicit = client.post(
        "/api/admin/nesting/run",
        json={"material_id": steel.id, "order_ids": [], "items": [{"design_id": design["id"], "quantity": 12}]},
    ).json()
    assert explicit["total_parts"] == 12 and explicit["sheets_needed"] == 3
    assert explicit["stock_sufficient"] is True

    short = client.post(
        "/api/admin/nesting/run",
        json={"material_id": steel.id, "order_ids": [], "items": [{"design_id": design["id"], "quantity": 20}]},
    ).json()
    assert short["sheets_needed"] == 4 and short["stock_sufficient"] is False


def test_nesting_errors_and_unplaced_parts(client, db):
    steel = make_material(db)
    count_material = make_material(db, name="Rivets", dimension_type=DimensionType.COUNT)
    no_dims = make_material(db, name="Sans largeur", standard_width_mm=None)
    narrow = make_material(db, name="Étroit", standard_width_mm=20)
    design = create_design(client, material_id=steel.id)

    assert client.post("/api/admin/nesting/run", json={"material_id": 999}).status_code == 400
    assert client.post("/api/admin/nesting/run", json={"material_id": count_material.id}).status_code == 400
    assert client.post("/api/admin/nesting/run", json={"material_id": no_dims.id}).status_code == 400
    bad_design = client.post("/api/admin/nesting/run", json={"material_id": steel.id, "items": [{"design_id": 999}]})
    assert bad_design.status_code == 400

    too_narrow = client.post(
        "/api/admin/nesting/run", json={"material_id": narrow.id, "order_ids": [], "items": [{"design_id": design["id"]}]}
    ).json()
    assert too_narrow["placed_parts"] == 0 and too_narrow["unplaced"][0]["reason"] == "too_large"

    assert client.post("/api/admin/nesting/run", json={"material_id": steel.id, "spacing_mm": -1}).status_code == 422


def test_nesting_export_returns_requested_sheet(client, db):
    steel = make_material(db)
    design = create_design(client, material_id=steel.id)
    request = {"material_id": steel.id, "order_ids": [], "items": [{"design_id": design["id"], "quantity": 7}]}
    svg = client.post("/api/admin/nesting/export", json={"request": request, "format": "svg", "sheet_index": 1})
    assert svg.status_code == 200 and svg.text.count("<path") == 2 + 0  # 7 blades = 5 + 2
    dxf = client.post("/api/admin/nesting/export", json={"request": request, "format": "dxf", "sheet_index": 0})
    assert dxf.status_code == 200 and "nesting_sheet_1.dxf" in dxf.headers["content-disposition"]
    missing = client.post("/api/admin/nesting/export", json={"request": request, "format": "svg", "sheet_index": 9})
    assert missing.status_code == 400


def test_seed_creates_demo_designs_that_nest(db):
    from app.services.seed_service import seed_mock_data, seed_mock_designs

    seed_mock_data(db)
    assert seed_mock_designs(db) == 3
    assert seed_mock_designs(db) == 0  # idempotent
    from app.models.design import Design

    assert all(d.area_mm2 > 0 and d.part_count == 1 for d in db.query(Design).all())


def test_demo_data_controls_include_designs_and_backup_export(client, db):
    seed = client.post("/api/admin/settings/mock-data/seed").json()
    assert seed["seeded"] > 0
    assert len(client.get("/api/admin/designs").json()) == 3
    backup = client.get("/api/admin/settings/export").json()
    assert len(backup["designs"]) == 3 and backup["designs"][0]["document"]["layers"]

    client.post("/api/admin/settings/mock-data/clear")
    assert client.get("/api/admin/designs").json() == []


# --------------------------------------------------------------------------- background image
PNG_1PX = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def background(**overrides):
    values = dict(image=PNG_1PX, cx=90, cy=16, width_mm=200, height_mm=150, rotation_deg=-2.5, opacity=0.4, calibrated=True)
    values.update(overrides)
    return values


def test_background_is_saved_returned_and_kept_out_of_lists_and_exports(client):
    design = create_design(client)
    svg_before = client.get(f"/api/admin/designs/{design['id']}/export.svg").text

    response = client.patch(f"/api/admin/designs/{design['id']}", json={"background": background()})
    assert response.status_code == 200, response.text
    saved = response.json()["background"]
    assert saved["width_mm"] == 200 and saved["rotation_deg"] == -2.5 and saved["calibrated"] is True
    assert saved["locked"] is True and saved["visible"] is True  # defaults

    assert "background" not in client.get("/api/admin/designs").json()[0]  # lists stay light
    # never exported: the SVG is byte-for-byte what it was without a background
    assert client.get(f"/api/admin/designs/{design['id']}/export.svg").text == svg_before
    # geometry metrics untouched
    assert client.get(f"/api/admin/designs/{design['id']}").json()["width_mm"] == 182


def test_background_omitted_is_unchanged_and_null_removes_it(client):
    design = create_design(client)
    client.patch(f"/api/admin/designs/{design['id']}", json={"background": background()})
    renamed = client.patch(f"/api/admin/designs/{design['id']}", json={"name": "Renommée"}).json()
    assert renamed["background"]["width_mm"] == 200

    cleared = client.patch(f"/api/admin/designs/{design['id']}", json={"background": None}).json()
    assert cleared["background"] is None


def test_background_rejects_non_raster_or_remote_images(client):
    design = create_design(client)
    for image in (
        "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciLz4=",
        "https://example.com/photo-de-lame-tres-nette.jpg",
        "data:image/png;base64,not base64 at all !!!!!!!!!!!!!!!!",
    ):
        response = client.patch(f"/api/admin/designs/{design['id']}", json={"background": background(image=image)})
        assert response.status_code == 422, image
    for bad in ({"width_mm": 0}, {"opacity": 0}, {"cx": float("1e9")}):
        assert client.patch(f"/api/admin/designs/{design['id']}", json={"background": background(**bad)}).status_code == 422


def test_duplicate_keeps_the_background(client):
    design = create_design(client)
    client.patch(f"/api/admin/designs/{design['id']}", json={"background": background()})
    copy = client.post(f"/api/admin/designs/{design['id']}/duplicate").json()
    assert copy["background"]["image"] == PNG_1PX


def test_nesting_candidates_flag_order_lines_without_a_linked_design(client, db):
    steel = make_material(db)
    linked, unlinked, unrelated = make_model(db), make_model(db, "Sans gabarit"), make_model(db, "Autre matière")
    for model in (linked, unlinked):
        db.add(KnifeModelMaterial(knife_model_id=model.id, material_id=steel.id, role=MaterialRole.BLADE, blank_length_mm=200))
    db.commit()
    create_design(client, material_id=steel.id, knife_model_id=linked.id)
    make_order(db, linked, 2)
    make_order(db, unlinked, 3, customer="Camille")
    make_order(db, unrelated, 1, customer="Ignoré")  # does not use this steel: not a missing design

    candidates = client.get(f"/api/admin/nesting/candidates?material_id={steel.id}").json()
    assert [(o["customer_name"], o["part_count"]) for o in candidates["orders"]] == [("Alex", 2)]
    assert [(u["customer_name"], u["knife_model_name"], u["quantity"]) for u in candidates["unlinked"]] == [
        ("Camille", "Sans gabarit", 3)
    ]
