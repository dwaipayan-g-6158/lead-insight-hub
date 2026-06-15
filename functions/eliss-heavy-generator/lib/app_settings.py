"""Read the singleton app_settings row at job start.

Mirror of functions/eliss-generator/lib/app_settings.py — see that file for the
full rationale. Returns {} on any miss/error so callers fall back to their own
constants; the feature is inert until the super-admin changes something.
"""
import json
import logging

from .db import select_one

LOG = logging.getLogger("eliss-heavy-generator")

_TABLE = "app_settings"


def load_settings(app):
    """Best-effort read of the global generation settings. Never raises."""
    try:
        zcql = app.zcql()
        row = select_one(
            zcql,
            f"SELECT settings_json FROM {_TABLE} ORDER BY ROWID ASC",
            _TABLE,
        )
        if not row:
            return {}
        raw = row.get("settings_json")
        if not raw:
            return {}
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception as e:  # noqa: BLE001 — settings must never block generation
        LOG.warning("load_settings failed (using defaults): %s", e)
        return {}


def get_int(settings, key, default):
    try:
        v = settings.get(key)
        return int(v) if v is not None else int(default)
    except (TypeError, ValueError):
        return int(default)


def get_bool(settings, key, default=False):
    v = settings.get(key)
    return bool(v) if v is not None else bool(default)


def get_str(settings, key, default=None):
    v = settings.get(key)
    if v is None:
        return default
    s = str(v).strip()
    return s or default
