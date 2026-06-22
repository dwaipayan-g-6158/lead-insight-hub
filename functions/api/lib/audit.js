/**
 * Append-only audit-event emitter for the org-wide Audit Report.
 *
 * Writes one row to the `audit_events` Data Store table per noteworthy user
 * action (login, dossier creation, search, lead view, admin mutation).
 * Visibility is org-wide by product decision — every authenticated user can
 * read every event via routes/audit.js — so this module only WRITES; there is
 * no client-facing mutate/delete path (the only delete path is the 120-day
 * retention sweep in functions/dossier-sweeper/index.js).
 *
 * Design rules:
 *   - FIRE-AND-FORGET + NON-THROWING. An audit-write failure must never break
 *     the user action it describes. The exported helpers swallow every error
 *     and are called WITHOUT await by routes (matching the existing
 *     fire-and-forget DB writes in auth.js last_seen_at and leads.js
 *     opened_by_creator_at). Catalyst Advanced I/O runs a persistent server,
 *     so the insert completes after res.json() returns.
 *   - occurred_at is written in UTC via catalystDateTime() (same helper used
 *     for updated_at / completed_at elsewhere). The SYSTEM columns
 *     CREATEDTIME/MODIFIEDTIME are project-local IST (+05:30) — the retention
 *     sweep keys off occurred_at (UTC), not those, to avoid offset drift.
 *   - bigint ROWID target_id values are stored as STRINGS (precision gotcha).
 */

const { catalystDateTime } = require("./db");

// Whitelist guards against typo'd event_type values silently polluting the
// feed. Keep in sync with the AuditEventType union in app/src/types/audit.ts
// and the filter chips in AuditPage.tsx.
const EVENT_TYPES = new Set([
  "login",
  "dossier_create",
  "search",
  "lead_view",
  "admin_action",
]);

// Column length caps — mirror the audit_events schema. Strings are clipped
// rather than rejected so an over-long label never drops the whole event.
const ACTION_MAX = 250;
const LABEL_MAX = 250;
const METADATA_MAX = 9999;

// A typing burst on the leads search (z → zo → zoh → … → zohocorp) fires one
// debounced GET /leads per keystroke. We collapse the whole burst into a SINGLE
// audit row by UPDATING the row in place while the query keeps evolving (the
// new query is a prefix-extension of, or a backspace from, the previous one)
// within this window. A genuinely different query, or one typed after a pause
// longer than the window, starts a fresh row.
const SEARCH_SESSION_MS = 12_000;
const _searchSession = new Map(); // userId -> { rowId, query, ts }

// Opening the same dossier repeatedly (re-render, navigate back-and-forth)
// shouldn't spam the feed — collapse repeat views of the same lead by the same
// user inside this window.
const VIEW_DEDUP_MS = 60_000;
const _viewDedup = new Map(); // `${userId}:${leadId}` -> ts

function _displayName(user) {
  const full = [user?.first_name, user?.last_name].filter(Boolean).join(" ").trim();
  return full || user?.email_id || null;
}

// Common actor columns, derived from the authenticated session.
function _actorFields(req) {
  return {
    user_id: String(req.userId),
    actor_email: req.user?.email_id ?? null,
    actor_name: _displayName(req.user),
  };
}

function _table(req) {
  const app = req.catalystAdminApp || req.catalystApp;
  return app ? app.datastore().table("audit_events") : null;
}

// Opportunistic GC so the dedup maps can't grow unbounded across many users.
function _gc(map, ttl) {
  if (map.size <= 500) return;
  const now = Date.now();
  for (const [k, v] of map) {
    const ts = typeof v === "number" ? v : v?.ts ?? 0;
    if (now - ts > ttl) map.delete(k);
  }
}

/**
 * Insert one audit row. Never throws; never rejects. Call without await.
 * Returns the inserted ROWID (string) or null. Used for login / dossier_create
 * / lead_view / admin_action. Search goes through logSearch() instead.
 *
 * @param {object} req  Express request — must have run requireUser + attachCatalyst.
 * @param {object} ev   { eventType, action?, targetType?, targetId?, targetLabel?, metadata? }
 */
async function logEvent(req, ev) {
  try {
    const {
      eventType,
      action = null,
      targetType = null,
      targetId = null,
      targetLabel = null,
      metadata = null,
    } = ev || {};

    if (!EVENT_TYPES.has(eventType)) {
      console.warn("audit.logEvent: unknown eventType", eventType);
      return null;
    }
    const table = _table(req);
    if (!table || !req.userId) return null;

    const row = {
      ..._actorFields(req),
      event_type: eventType,
      event_action: action != null ? String(action).slice(0, ACTION_MAX) : null,
      target_type: targetType != null ? String(targetType).slice(0, 50) : null,
      target_id: targetId != null ? String(targetId) : null,
      target_label: targetLabel != null ? String(targetLabel).slice(0, LABEL_MAX) : null,
      metadata: metadata != null ? JSON.stringify(metadata).slice(0, METADATA_MAX) : null,
      occurred_at: catalystDateTime(new Date()),
    };
    const inserted = await table.insertRow(row);
    return inserted?.ROWID != null ? String(inserted.ROWID) : null;
  } catch (e) {
    console.warn("audit.logEvent failed (non-fatal):", e?.message);
    return null;
  }
}

/**
 * Log a leads search, collapsing an in-progress typing burst into one row.
 * While the query keeps evolving (prefix-extension or backspace) within
 * SEARCH_SESSION_MS, the existing row is UPDATED to the latest query/result
 * count instead of inserting a new one — so typing "zohocorp" yields a single
 * "searched zohocorp" entry, not one per keystroke. Fire-and-forget.
 */
async function logSearch(req, { query, filters = {}, results = null } = {}) {
  try {
    const table = _table(req);
    if (!table || !req.userId || !query) return;
    const uid = String(req.userId);
    const q = String(query).slice(0, LABEL_MAX);
    const qLower = q.toLowerCase();
    const now = Date.now();
    const metadata = JSON.stringify({ filters, results }).slice(0, METADATA_MAX);
    const occurred_at = catalystDateTime(new Date());

    const prev = _searchSession.get(uid);
    const evolving =
      prev &&
      prev.rowId &&
      now - prev.ts < SEARCH_SESSION_MS &&
      (qLower.startsWith(prev.query) || prev.query.startsWith(qLower));

    if (evolving) {
      // Same evolving search — update in place so the feed shows one row.
      await table.updateRow({ ROWID: prev.rowId, target_label: q, metadata, occurred_at });
      _searchSession.set(uid, { rowId: prev.rowId, query: qLower, ts: now });
      return;
    }

    const inserted = await table.insertRow({
      ..._actorFields(req),
      event_type: "search",
      event_action: "leads",
      target_type: null,
      target_id: null,
      target_label: q,
      metadata,
      occurred_at,
    });
    _searchSession.set(uid, {
      rowId: inserted?.ROWID != null ? String(inserted.ROWID) : null,
      query: qLower,
      ts: now,
    });
    _gc(_searchSession, SEARCH_SESSION_MS);
  } catch (e) {
    console.warn("audit.logSearch failed (non-fatal):", e?.message);
  }
}

/**
 * Returns true if this lead view should be logged (not a repeat of the same
 * user viewing the same lead within VIEW_DEDUP_MS). Updates the dedup map.
 */
function shouldLogView(userId, leadId) {
  if (!userId || !leadId) return false;
  const key = `${userId}:${leadId}`;
  const now = Date.now();
  const prev = _viewDedup.get(key);
  if (prev && now - prev < VIEW_DEDUP_MS) return false;
  _viewDedup.set(key, now);
  _gc(_viewDedup, VIEW_DEDUP_MS);
  return true;
}

module.exports = { logEvent, logSearch, shouldLogView, EVENT_TYPES };
