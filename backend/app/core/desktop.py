"""Desktop build (Windows installer): one workshop, one machine, no Docker.

What Docker passes through environment variables lives here in `<data dir>/config.json`:
- `secret_key`: signs session tokens, generated on the first launch and never shown;
- `admin_email` / `admin_password_hash`: created on the first-run screen (`POST /api/auth/setup`);
- `port`: the local port the launcher last served on;
- `auto_backup`: the daily backup folder and how many days of backups to keep.

The database is SQLite in the same folder. Nothing in this folder ever leaves the machine.
`prepare_environment()` must run before anything imports `app.config`, since the settings are
read once and cached.
"""

import json
import os
import secrets
from pathlib import Path
from typing import Any

CONFIG_NAME = "config.json"
DB_NAME = "knifeforge.db"
DEFAULT_PORT = 8765


def default_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "KnifeForge Pro"


def load_config(data_dir: Path) -> dict[str, Any]:
    path = data_dir / CONFIG_NAME
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_config(data_dir: Path, values: dict[str, Any]) -> None:
    """Write atomically: a crash mid-write must not leave a half file that locks the workshop out."""
    data_dir.mkdir(parents=True, exist_ok=True)
    tmp = data_dir / (CONFIG_NAME + ".tmp")
    tmp.write_text(json.dumps(values, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, data_dir / CONFIG_NAME)


def update_config(data_dir: Path, **changes: Any) -> dict[str, Any]:
    values = load_config(data_dir)
    values.update(changes)
    save_config(data_dir, values)
    return values


def prepare_environment(data_dir: Path, frontend_dist: Path | None) -> dict[str, Any]:
    """Create the data folder and its config on first launch, then expose them as the
    environment the backend settings read."""
    data_dir.mkdir(parents=True, exist_ok=True)
    values = load_config(data_dir)
    if not values.get("secret_key"):
        values["secret_key"] = secrets.token_hex(32)
        save_config(data_dir, values)

    os.environ.update(
        {
            "DESKTOP": "true",
            "ENVIRONMENT": "desktop",
            "DATA_DIR": str(data_dir),
            "DATABASE_URL": f"sqlite:///{(data_dir / DB_NAME).as_posix()}",
            "SECRET_KEY": values["secret_key"],
            "ADMIN_EMAIL": values.get("admin_email", ""),
            "ADMIN_PASSWORD_HASH": values.get("admin_password_hash", ""),
            "REDIS_URL": "",  # no Redis on a workstation: the login rate limit counts in memory
            "FRONTEND_DIST": str(frontend_dist) if frontend_dist else "",
        }
    )
    return values
