"""Daily automatic backup of the desktop build.

Once a day the full backup (the same file as Settings › Download a full backup, restorable from
Settings › Restore) is written to a folder the workshop chooses: a USB key, a second disk, a
synced folder. Files older than `keep_days` are removed, and only files this module wrote
(`knifeforge-*.json`) are ever touched. The settings live in the desktop config.json, not in
the database, so restoring a backup never changes where backups go.

Under Docker the nightly `pg_dump` service does this job; this module stays idle there.
"""

import json
import logging
import os
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.core import desktop
from app.database import SessionLocal
from app.services.backup_service import export_backup

logger = logging.getLogger("knifeforge")

DEFAULT_KEEP_DAYS = 30
INTERVAL = timedelta(hours=24)
CHECK_EVERY_S = 30 * 60
FILE_RE = re.compile(r"^knifeforge-\d{4}-\d{2}-\d{2}_\d{4}\.json$")

_lock = threading.Lock()


def _data_dir() -> Path:
    return Path(get_settings().data_dir)


def default_directory() -> Path:
    return _data_dir() / "Sauvegardes"


def read_state() -> dict[str, Any]:
    stored = desktop.load_config(_data_dir()).get("auto_backup", {})
    return {
        "enabled": stored.get("enabled", True),
        "directory": stored.get("directory") or str(default_directory()),
        "keep_days": int(stored.get("keep_days", DEFAULT_KEEP_DAYS)),
        "last_at": stored.get("last_at"),
        "last_file": stored.get("last_file"),
        "last_error": stored.get("last_error"),
    }


def _store(**changes: Any) -> dict[str, Any]:
    config = desktop.load_config(_data_dir())
    state = {**config.get("auto_backup", {}), **changes}
    desktop.update_config(_data_dir(), auto_backup=state)
    return read_state()


def configure(enabled: bool, directory: str, keep_days: int) -> dict[str, Any]:
    """Check the folder can be written now, rather than discovering it at 3 a.m."""
    folder = Path(directory).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    probe = folder / ".knifeforge-write-test"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink()
    return _store(enabled=enabled, directory=str(folder), keep_days=keep_days)


def prune(folder: Path, keep_days: int, now: datetime) -> list[str]:
    removed = []
    limit = now - timedelta(days=keep_days)
    for file in folder.iterdir():
        if FILE_RE.match(file.name) and datetime.fromtimestamp(file.stat().st_mtime) < limit:
            file.unlink()
            removed.append(file.name)
    return removed


def run_backup(now: datetime | None = None) -> dict[str, Any]:
    """Write one backup now, whatever the schedule says."""
    now = now or datetime.now()
    with _lock:
        state = read_state()
        folder = Path(state["directory"])
        try:
            folder.mkdir(parents=True, exist_ok=True)
            db = SessionLocal()
            try:
                content = export_backup(db)
            finally:
                db.close()
            target = folder / f"knifeforge-{now:%Y-%m-%d_%H%M}.json"
            tmp = target.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(content, ensure_ascii=False, default=str), encoding="utf-8")
            os.replace(tmp, target)
            prune(folder, state["keep_days"], now)
        except Exception as exc:  # noqa: BLE001 - a failed backup is reported in Settings, never fatal
            logger.exception("Automatic backup failed")
            return _store(last_error=f"{type(exc).__name__}: {exc}")
        logger.info("Automatic backup written: %s", target)
        return _store(last_at=now.isoformat(timespec="seconds"), last_file=target.name, last_error=None)


def run_if_due(now: datetime | None = None) -> bool:
    now = now or datetime.now()
    state = read_state()
    if not state["enabled"]:
        return False
    if state["last_at"] and now - datetime.fromisoformat(state["last_at"]) < INTERVAL:
        return False
    run_backup(now)
    return True


def start_scheduler(stop: threading.Event) -> threading.Thread:
    """Check at start-up, then every half hour: a computer that sleeps at night still gets its
    backup soon after it wakes."""

    def loop() -> None:
        while not stop.is_set():
            try:
                run_if_due()
            except Exception:  # noqa: BLE001
                logger.exception("Automatic backup check failed")
            stop.wait(CHECK_EVERY_S)

    thread = threading.Thread(target=loop, name="auto-backup", daemon=True)
    thread.start()
    return thread
