"""Durable checkpoint store on Stratus — so already-spent Anthropic tokens
survive a Catalyst 15-min (900s) Job kill.

The expensive asset in the Heavy pipeline is the 4-subagent fan-out; in the
Light pipeline it is the single synthesis call. Both are persisted here the
instant they complete, BEFORE the cheap-but-kill-prone render/upload tail. A
resume Job (see main.py) loads the checkpoint and finishes from it without
re-spending a single research/synthesis token.

Stratus gotcha honored throughout: `put_object` is CREATE-ONLY when bucket
versioning is off — a duplicate key returns HTTP 409 `key_already_exists`. We
write each key exactly once and treat a 409 as "already checkpointed" (success),
never delete+put (which can silently wipe data and still fail the put). See
plan glowing-greeting-teapot.md and project memory
feedback_catalyst_stratus_no_overwrite.
"""
import json
import logging
import os

LOG = logging.getLogger("eliss-checkpoint")

STRATUS_BUCKET = os.environ.get("STRATUS_BUCKET", "dossiers")


def _bucket(app):
    return app.stratus().bucket(STRATUS_BUCKET)


# Write-once keys under a per-request prefix so cleanup is a small fixed set.
def fanout_key(request_id):
    return f"checkpoints/{request_id}/fanout.json"


def parent_key(request_id):
    return f"checkpoints/{request_id}/parent.json"


def dossier_key(request_id):
    return f"checkpoints/{request_id}/dossier.json"


def _write_once(app, key, payload):
    """Write a JSON payload to a Stratus key exactly once.

    Returns True on success OR when the key already exists (idempotent). Never
    raises — a checkpoint write must never be the thing that fails a job.
    """
    try:
        body = json.dumps(payload, default=str).encode("utf-8")
        _bucket(app).put_object(key, body, {"content_type": "application/json"})
        return True
    except Exception as e:  # noqa: BLE001 — checkpointing is best-effort
        msg = str(e).lower()
        if "already" in msg or "409" in msg:
            LOG.info("checkpoint key already exists (idempotent): %s", key)
            return True
        LOG.warning("checkpoint write failed for %s: %s", key, e)
        return False


def _read(app, key):
    """Read+parse a JSON checkpoint. Returns the dict, or None on miss/parse error."""
    try:
        res = _bucket(app).get_object(key)
    except Exception as e:  # noqa: BLE001 — a miss is expected (no checkpoint yet)
        LOG.info("checkpoint read miss for %s: %s", key, e)
        return None
    try:
        if hasattr(res, "read"):  # stream-like object from some SDK builds
            res = res.read()
        if isinstance(res, (bytes, bytearray)):
            res = res.decode("utf-8")
        obj = json.loads(res)
        return obj if isinstance(obj, dict) else None
    except Exception as e:  # noqa: BLE001
        LOG.warning("checkpoint parse failed for %s: %s", key, e)
        return None


def write_fanout(app, request_id, payload):
    return _write_once(app, fanout_key(request_id), payload)


def read_fanout(app, request_id):
    return _read(app, fanout_key(request_id))


def write_parent(app, request_id, payload):
    return _write_once(app, parent_key(request_id), payload)


def read_parent(app, request_id):
    return _read(app, parent_key(request_id))


def write_dossier(app, request_id, payload):
    return _write_once(app, dossier_key(request_id), payload)


def read_dossier(app, request_id):
    return _read(app, dossier_key(request_id))


def cleanup(app, request_id):
    """Best-effort delete of every checkpoint key for a request. Called only on
    terminal success — on failure we deliberately leave the checkpoint so a
    resume Job (or forensic inspection) can still use it.
    """
    for key in (fanout_key(request_id), parent_key(request_id), dossier_key(request_id)):
        try:
            _bucket(app).delete_object(key)
        except Exception:  # noqa: BLE001 — orphan cleanup is non-critical
            pass
