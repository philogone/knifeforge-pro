from sqlalchemy.orm import Session

from app.models.shop_settings import ShopSettings


def get_shop_settings(db: Session) -> ShopSettings:
    """The singleton row is created lazily on first access rather than in
    a migration data-seed step, so it always exists exactly once without
    the migration needing to guess at defaults a maker hasn't set yet."""
    settings = db.query(ShopSettings).filter(ShopSettings.id == 1).first()
    if settings is None:
        settings = ShopSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings
