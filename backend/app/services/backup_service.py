"""Full backup and restore, table by table.

The JSON export in Settings is a readable snapshot; this is the restorable one. Every table
of the schema is dumped as raw rows (so tables added later are covered without code here),
tagged with the Alembic revision it came from. Restore replaces the whole database content in
one transaction: delete in reverse dependency order, insert in dependency order, then reset
PostgreSQL sequences so new rows do not collide with restored ids.
"""

from __future__ import annotations

import base64
import enum
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, Enum, LargeBinary, Numeric, Time, text
from sqlalchemy.orm import Session

from app.database import Base

FORMAT = "knifeforge-backup"
FORMAT_VERSION = 1


def _schema_revision(db: Session) -> str | None:
    try:
        return db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:  # noqa: BLE001 - a database created without Alembic has no version table
        db.rollback()
        return None


def _dump_value(value: Any) -> Any:
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return base64.b64encode(value).decode("ascii")
    return value


def _load_value(column, value: Any) -> Any:
    if value is None:
        return None
    col_type = column.type
    if isinstance(col_type, Enum) and col_type.enum_class is not None:
        return col_type.enum_class(value)
    if isinstance(col_type, DateTime):
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo or not col_type.timezone else parsed.replace(tzinfo=timezone.utc)
    if isinstance(col_type, Date):
        return date.fromisoformat(value)
    if isinstance(col_type, Time):
        return time.fromisoformat(value)
    if isinstance(col_type, Numeric) and isinstance(value, str):
        return Decimal(value)
    if isinstance(col_type, LargeBinary):
        return base64.b64decode(value)
    return value


def export_backup(db: Session) -> dict[str, Any]:
    tables: dict[str, list[dict[str, Any]]] = {}
    for table in Base.metadata.sorted_tables:
        pk = list(table.primary_key.columns)
        rows = db.execute(table.select().order_by(*pk)).mappings().all()
        tables[table.name] = [{key: _dump_value(val) for key, val in row.items()} for row in rows]
    return {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "schema_revision": _schema_revision(db),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tables": tables,
    }


class BackupError(ValueError):
    pass


def restore_backup(db: Session, data: dict[str, Any]) -> dict[str, int]:
    """Replace everything with the backup's content. All or nothing."""
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise BackupError("Not a KnifeForge backup file")
    if data.get("format_version") != FORMAT_VERSION:
        raise BackupError("Unsupported backup format version")
    current = _schema_revision(db)
    if data.get("schema_revision") and current and data["schema_revision"] != current:
        raise BackupError(
            f"Backup made with database version {data['schema_revision']}, this installation is at {current}"
        )
    tables_in = data.get("tables")
    if not isinstance(tables_in, dict):
        raise BackupError("Backup has no tables")
    known = {t.name for t in Base.metadata.sorted_tables}
    unknown = set(tables_in) - known
    if unknown:
        raise BackupError(f"Backup contains unknown tables: {', '.join(sorted(unknown))}")

    counts: dict[str, int] = {}
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        for table in Base.metadata.sorted_tables:
            rows = tables_in.get(table.name) or []
            columns = {c.name: c for c in table.columns}
            prepared = [
                {name: _load_value(columns[name], value) for name, value in row.items() if name in columns}
                for row in rows
            ]
            if prepared:
                db.execute(table.insert(), prepared)
            counts[table.name] = len(prepared)
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            for table in Base.metadata.sorted_tables:
                pk = list(table.primary_key.columns)
                if len(pk) == 1 and pk[0].autoincrement and str(pk[0].type) in ("INTEGER", "BIGINT"):
                    db.execute(
                        text(
                            f"SELECT setval(pg_get_serial_sequence('{table.name}', '{pk[0].name}'), "
                            f"COALESCE((SELECT MAX({pk[0].name}) FROM {table.name}), 0) + 1, false)"
                        )
                    )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return counts
