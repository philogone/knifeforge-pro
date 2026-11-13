from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.core.security import require_admin
from app.database import get_db
from app.models.design import Design
from app.models.knife_model import KnifeModel
from app.models.material import Material
from app.models.order import Order
from app.models.saw_blade import SawBlade
from app.models.treatment import TreatmentRecipe
from app.routers.knife_models import _query as _knife_model_query
from app.routers.knife_models import _to_out as _knife_model_to_out
from app.routers.orders import _to_out as _order_to_out
from app.schemas.design import DesignOut
from app.schemas.knife_model import KnifeModelOut
from app.schemas.material import MaterialOut
from app.schemas.order import OrderOut
from app.schemas.saw_blade import SawBladeOut
from app.schemas.shop_settings import (
    AutoBackupOut,
    AutoBackupUpdate,
    MailSettingsOut,
    MailSettingsUpdate,
    MailTestIn,
    ShopSettingsOut,
    ShopSettingsUpdate,
    StageOut,
    StagesIn,
)
from app.schemas.treatment import TreatmentRecipeOut
from app.services.backup_service import BackupError, export_backup, inspect_backup, restore_backup
from app.services.order_service import load_order_with_relations
from app.services.seed_service import clear_mock_data, seed_mock_data, seed_mock_designs
from app.services.shop_settings_service import get_shop_settings

router = APIRouter(prefix="/api/admin/settings", tags=["settings"], dependencies=[Depends(require_admin)])


@router.get("/shop", response_model=ShopSettingsOut)
def get_shop(db: Session = Depends(get_db)):
    return get_shop_settings(db)


@router.patch("/shop", response_model=ShopSettingsOut)
def update_shop(payload: ShopSettingsUpdate, db: Session = Depends(get_db)):
    settings = get_shop_settings(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        # an emptied text field clears the value instead of storing ""
        setattr(settings, field, value if value != "" else None)
    db.commit()
    db.refresh(settings)
    return settings


@router.get("/mock-data")
def mock_data_status(db: Session = Depends(get_db)):
    enabled = db.query(Material).filter(Material.is_mock.is_(True)).first() is not None
    return {"enabled": enabled}


@router.post("/mock-data/seed")
def seed(db: Session = Depends(get_db)):
    created = seed_mock_data(db)
    created += seed_mock_designs(db)
    return {"seeded": created}


@router.post("/mock-data/clear")
def clear(db: Session = Depends(get_db)):
    removed = clear_mock_data(db)
    return {"removed": removed}


@router.get("/export")
def export_data(db: Session = Depends(get_db)):
    """Full JSON backup of everything in the database (including demo data,
    flagged via is_mock on each record) — a maker's own copy of their
    catalog, recipes, knife models, and order history, downloadable from
    the browser. Not an automatic scheduled backup; the maker triggers it
    from Settings whenever they want a snapshot."""
    materials = db.query(Material).options(joinedload(Material.saw_blade)).order_by(Material.name).all()
    saw_blades = db.query(SawBlade).order_by(SawBlade.name).all()
    recipes = db.query(TreatmentRecipe).order_by(TreatmentRecipe.name).all()
    knife_models = _knife_model_query(db).order_by(KnifeModel.name).all()
    orders = db.query(Order).order_by(Order.created_at).all()
    designs = db.query(Design).options(joinedload(Design.knife_model), joinedload(Design.material)).order_by(Design.name).all()
    shop = get_shop_settings(db)

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "shop_settings": ShopSettingsOut.model_validate(shop).model_dump(mode="json"),
        "materials": [MaterialOut.model_validate(m).model_dump(mode="json") for m in materials],
        "saw_blades": [SawBladeOut.model_validate(b).model_dump(mode="json") for b in saw_blades],
        "treatment_recipes": [TreatmentRecipeOut.model_validate(r).model_dump(mode="json") for r in recipes],
        "knife_models": [
            KnifeModelOut.model_validate(_knife_model_to_out(m)).model_dump(mode="json") for m in knife_models
        ],
        "orders": [
            OrderOut.model_validate(_order_to_out(load_order_with_relations(db, o.id))).model_dump(mode="json")
            for o in orders
        ],
        "designs": [DesignOut.model_validate(d).model_dump(mode="json") for d in designs],
    }


@router.get("/backup")
def download_backup(db: Session = Depends(get_db)):
    """Restorable backup: every table, raw rows, tagged with the schema version."""
    shop = get_shop_settings(db)
    shop.last_backup_at = datetime.now(timezone.utc)
    db.commit()
    return export_backup(db)


@router.post("/backup/inspect")
def inspect(payload: dict = Body(...)):
    """What a backup file holds (date, version, counts), before restoring it."""
    try:
        return inspect_backup(payload)
    except BackupError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/backup/status")
def backup_status(db: Session = Depends(get_db)):
    """When the data was last saved, and whether to remind the user (desktop build: the daily
    automatic backup counts; Docker: the nightly dump runs outside the application)."""
    shop = get_shop_settings(db)
    last_manual = shop.last_backup_at
    last_auto = None
    if get_settings().desktop:
        from app.services import auto_backup

        state = auto_backup.read_state()
        last_auto = state.get("last_at") if state.get("enabled") else None
    stamps = [t for t in (last_manual.isoformat() if last_manual else None, last_auto) if t]
    last = max(stamps) if stamps else None
    remind = False
    if get_settings().desktop:
        if last is None:
            remind = True
        else:
            when = datetime.fromisoformat(last)
            when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
            remind = (datetime.now(timezone.utc) - when).days >= 7
    return {"last_manual_at": last_manual, "last_auto_at": last_auto, "remind": remind}


@router.post("/restore")
def restore(payload: dict = Body(...), db: Session = Depends(get_db)):
    """Replace ALL data with the backup's content (one transaction: all or nothing)."""
    try:
        counts = restore_backup(db, payload)
    except BackupError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"restored": counts}


# ---- daily automatic backup (desktop build only; Docker has its nightly pg_dump service)
def _desktop_only() -> None:
    if not get_settings().desktop:
        raise HTTPException(status_code=404, detail="Only in the desktop version")


@router.get("/auto-backup", response_model=AutoBackupOut, dependencies=[Depends(_desktop_only)])
def auto_backup_state():
    from app.services import auto_backup

    return auto_backup.read_state()


@router.put("/auto-backup", response_model=AutoBackupOut, dependencies=[Depends(_desktop_only)])
def auto_backup_configure(payload: AutoBackupUpdate):
    from app.services import auto_backup

    try:
        return auto_backup.configure(payload.enabled, payload.directory, payload.keep_days)
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Backup folder not writable") from exc


@router.post("/auto-backup/run", response_model=AutoBackupOut, dependencies=[Depends(_desktop_only)])
def auto_backup_now():
    from app.services import auto_backup

    return auto_backup.run_backup()


def _mail_out() -> dict:
    from app.services import mail_service

    s = get_settings()
    return {
        "configured": mail_service.configured(s), "editable": s.desktop, "host": s.smtp_host, "port": s.smtp_port,
        "security": s.smtp_security, "user": s.smtp_user, "from_address": s.smtp_from, "from_name": s.smtp_from_name,
        "password_set": bool(s.smtp_password),
    }


@router.get("/mail", response_model=MailSettingsOut)
def mail_settings():
    """The outgoing mail account (never the password)."""
    return _mail_out()


@router.put("/mail", response_model=MailSettingsOut)
def mail_configure(payload: MailSettingsUpdate):
    """Desktop build: stored in config.json with the other secrets. Docker: set SMTP_* in .env."""
    from pathlib import Path

    from app.core import desktop

    s = get_settings()
    if not s.desktop:
        raise HTTPException(status_code=409, detail="E-mail is configured by the server environment")
    values = {
        "smtp_host": payload.host.strip(), "smtp_port": payload.port, "smtp_security": payload.security,
        "smtp_user": payload.user.strip(), "smtp_from": payload.from_address.strip(), "smtp_from_name": payload.from_name.strip(),
    }
    if payload.password is not None:
        values["smtp_password"] = payload.password
    desktop.update_config(Path(s.data_dir), **values)
    for key, value in values.items():  # the settings object is shared: effective at once
        setattr(s, key, value)
    return _mail_out()


@router.post("/mail/test", response_model=MailSettingsOut)
def mail_test(payload: MailTestIn):
    from app.services import mail_service

    try:
        mail_service.send(get_settings(), [str(payload.to)], "KnifeForge Pro : message d'essai",
                          "Ce message confirme que KnifeForge Pro peut envoyer vos devis, factures et relances.\n")
    except mail_service.MailError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _mail_out()


# ---- trade profile and workshop stages
def _stages_out(db: Session) -> list[dict]:
    from collections import Counter

    from app.models.order import Order, OrderStatus
    from app.services import stages_service

    used = Counter(s for (s,) in db.query(Order.stage).filter(Order.status.in_((OrderStatus.DRAFT, OrderStatus.CONFIRMED))).all())
    return [{**s, "used": used.get(s["key"], 0)} for s in stages_service.stages(get_shop_settings(db))]


@router.get("/stages", response_model=list[StageOut])
def get_stages(db: Session = Depends(get_db)):
    """The workshop's stages, in order, with how many active orders sit at each."""
    return _stages_out(db)


@router.put("/stages", response_model=list[StageOut])
def put_stages(payload: StagesIn, db: Session = Depends(get_db)):
    """Rename, add, remove or reorder stages. A stage still holding active orders stays."""
    from app.services import stages_service

    shop = get_shop_settings(db)
    builtin = {k for keys in stages_service.DEFAULT_STAGES.values() for k in keys}
    out: list[dict] = []
    for s in payload.stages:
        label = (s.label or "").strip() or None
        key = s.key or (stages_service.slug(label) if label else None)
        if not key:
            raise HTTPException(status_code=422, detail="A new stage needs a name")
        if key not in builtin and not label:
            raise HTTPException(status_code=422, detail="A new stage needs a name")
        base, n = key, 2
        while any(o["key"] == key for o in out):
            key, n = f"{base}_{n}", n + 1
        out.append({"key": key, "label": label})
    kept = {o["key"] for o in out}
    missing = [s for s in _stages_out(db) if s["used"] and s["key"] not in kept]
    if missing:
        raise HTTPException(status_code=409, detail="A removed stage still holds active orders")
    shop.workshop_stages = out
    db.commit()
    return _stages_out(db)


@router.delete("/stages", response_model=list[StageOut])
def reset_stages(db: Session = Depends(get_db)):
    """Back to the trade's stages (orders at a stage the trade does not have keep it)."""
    shop = get_shop_settings(db)
    shop.workshop_stages = None
    db.commit()
    return _stages_out(db)
