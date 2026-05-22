"""ZCQL helpers — Python mirror of functions/api/lib/db.js.

ZCQL has a silent 300-row LIMIT (verified 2026-02-11 per zoho-catalyst skill);
all SELECT helpers paginate. The Catalyst Python SDK exposes ZCQL via
catalyst_app.zcql() with execute_query(query) returning a list of
{table_name: {col: val}} dicts — same shape as the Node SDK.
"""
from datetime import datetime, timezone

PAGE = 300


def esc(v):
    """Quote a value for inline ZCQL string interpolation.

    Returns 'NULL' when value is None — callers concat directly:
        f"WHERE foo = {esc(maybe_none)}"  # always parses
    Otherwise doubles any single quote.
    """
    if v is None:
        return "NULL"
    return str(v).replace("'", "''")


def catalyst_datetime(v=None):
    """Format for Catalyst DateTime columns: 'YYYY-MM-DD HH:MM:SS' in UTC.

    Default v=None means now(). Datetime responses come back as
    'YYYY-MM-DD HH:MM:SS:sss' (Catalyst's DC-local IST format on input/output
    differs — see normalizeCatalystDateTime in routes/leads.js for the
    response-side handling).
    """
    if v is None:
        v = datetime.now(timezone.utc)
    elif isinstance(v, str):
        try:
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(v, datetime):
        return None
    if v.tzinfo is not None:
        v = v.astimezone(timezone.utc).replace(tzinfo=None)
    return v.strftime("%Y-%m-%d %H:%M:%S")


def catalyst_date_only(v):
    """Promote a 'YYYY-MM-DD' string to full datetime; passthrough datetimes."""
    if not v:
        return None
    if isinstance(v, str) and len(v) == 10 and v[4] == "-" and v[7] == "-":
        return f"{v} 00:00:00"
    return catalyst_datetime(v)


def select_all(zcql, base, table):
    """Paginate SELECT in 300-row chunks. Returns flat list of row dicts."""
    off = 0
    out = []
    while True:
        rows = zcql.execute_query(f"{base} LIMIT {off}, {PAGE}")
        unwrapped = [r[table] for r in rows]
        out.extend(unwrapped)
        if len(unwrapped) < PAGE:
            break
        off += PAGE
    return out


def select_one(zcql, base, table):
    """Single-row SELECT. Returns the row dict or None."""
    rows = zcql.execute_query(f"{base} LIMIT 0, 1")
    if not rows:
        return None
    return rows[0][table]
