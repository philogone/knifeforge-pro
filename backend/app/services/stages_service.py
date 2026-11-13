"""Workshop stages and trade profile.

Each workshop has its own list of stages (key + label), shown on orders and the dashboard. By
default it is the list of its trade: a knifemaker forges, heat-treats, grinds and fits a handle;
a blacksmith surveys, forges, assembles, finishes and installs. A built-in stage has no label
(the interface translates its key); a stage the workshop adds carries its own label.
"""

from __future__ import annotations

import re
import unicodedata

from app.models.shop_settings import ShopSettings

TRADES = ("knifemaker", "blacksmith")
DEFAULT_STAGES = {
    "knifemaker": ["todo", "forging", "heat_treatment", "grinding", "handle", "finishing", "ready", "delivered"],
    "blacksmith": ["todo", "survey", "forging", "assembly", "finishing", "ready", "install", "delivered"],
}
MAX_STAGES = 16


def stages(settings: ShopSettings) -> list[dict]:
    """[{"key", "label"}] in workshop order; label None for a built-in key."""
    if settings.workshop_stages:
        return [{"key": s["key"], "label": s.get("label")} for s in settings.workshop_stages]
    return [{"key": k, "label": None} for k in DEFAULT_STAGES.get(settings.trade or "knifemaker", DEFAULT_STAGES["knifemaker"])]


def stage_keys(settings: ShopSettings) -> list[str]:
    return [s["key"] for s in stages(settings)]


def final_stage(settings: ShopSettings) -> str:
    """The last stage: the order has left the workshop."""
    return stage_keys(settings)[-1]


def slug(label: str) -> str:
    text = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")[:30] or "etape"
