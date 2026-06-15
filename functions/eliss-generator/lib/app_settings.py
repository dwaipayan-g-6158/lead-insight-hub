"""Read the singleton app_settings row at job start.

Returns a plain dict of the super-admin's global generation settings, or {} on
any miss/error. Callers apply ``settings.get(key, <existing constant>)``, so an
empty dict means today's hardcoded defaults stand — the feature is inert until
the super-admin changes something in the /admin/settings panel.

The settings_json blob is written + validated by functions/api/routes/settings.js
against functions/api/lib/generation-settings.schema.json. The Python side never
needs the schema: it only reads stored values and falls back to its own
constants (which equal the schema defaults).
"""
import json
import logging

from .db import select_one

LOG = logging.getLogger("eliss-generator")

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
    """settings.get(key, default) coerced to int, tolerant of bad values."""
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
