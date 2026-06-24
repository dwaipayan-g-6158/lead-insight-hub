const express = require("express");
const { esc, selectAll, catalystDateTime } = require("../lib/db");
const { EVENT_TYPES } = require("../lib/audit");

const router = express.Router();

// Org-wide audit feed. Every authenticated user can read every event — this is
// the transparent-by-design product decision (see lib/audit.js). Mounted under
// requireUser only; no admin gate.

const FEED_DEFAULT_LIMIT = 100;
const FEED_MAX_LIMIT = 300;
// When a free-text q is present we can't filter in ZCQL (its LIKE is broken for
// substrings — see leads.js), so we pull a bounded recent window and narrow in
// JS. Caps the scan so a huge table can't blow the function's memory/time.
const FREE_TEXT_SCAN_CAP = 600;

const AUDIT_COLS = [
  "ROWID", "user_id", "actor_email", "actor_name",
  "event_type", "event_action", "target_type", "target_id",
  "target_label", "metadata", "occurred_at",
];

// occurred_at is written in UTC as "YYYY-MM-DD HH:MM:SS" (see lib/audit.js).
// Hand the client an ISO-Z string so its Date()/safeDate math is unambiguous.
function occurredToIso(s) {
  if (!s) return null;
  const str = String(s).trim();
  // Catalyst may echo "YYYY-MM-DD HH:MM:SS:mmm" (colon millis) on read.
  const m = str.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})(?::(\d{1,3}))?$/);
  if (m) {
    const ms = m[7] ? `.${m[7].padEnd(3, "0").slice(0, 3)}` : "";
    return `${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}${ms}Z`;
  }
  return str;
}

function parseMeta(raw) {
  if (raw == null || raw === "") return null;
  if (typeof raw === "object") return raw;
  try {
    return JSON.parse(String(raw));
  } catch {
    return null;
  }
}

function reshapeEvent(row) {
  if (!row) return null;
  return {
    id: row.ROWID != null ? String(row.ROWID) : null,
    user_id: row.user_id != null ? String(row.user_id) : null,
    actor_email: row.actor_email ?? null,
    actor_name: row.actor_name ?? null,
    event_type: row.event_type ?? null,
    event_action: row.event_action ?? null,
    target_type: row.target_type ?? null,
    // Keep as string — dossier_request / user ROWIDs overflow JS Number.
    target_id: row.target_id != null ? String(row.target_id) : null,
    target_label: row.target_label ?? null,
    metadata: parseMeta(row.metadata),
    occurred_at: occurredToIso(row.occurred_at),
  };
}

// Parse a ?from / ?to query value (accepts "YYYY-MM-DD" or a full datetime)
// into a Catalyst-comparable "YYYY-MM-DD HH:MM:SS" literal, or null.
function toBound(v, endOfDay) {
  if (!v) return null;
  const s = String(v).trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return `${s} ${endOfDay ? "23:59:59" : "00:00:00"}`;
  if (/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}$/.test(s)) return s.replace("T", " ");
  return null;
}

// Live-enrich dossier_create events with the dossier_requests row's current
// status/stage. We deliberately do NOT log every status transition (that would
// need Python-generator changes); instead the feed reflects live state here.
async function enrichDossierStatus(zcql, events) {
  const ids = Array.from(
    new Set(
      events
        .filter((e) => e.event_type === "dossier_create" && e.target_id && /^\d+$/.test(e.target_id))
        .map((e) => e.target_id),
    ),
  );
  if (!ids.length) return;
  const statusById = new Map();
  // Chunk the IN-list to stay clear of any ZCQL clause limits.
  for (let i = 0; i < ids.length; i += 100) {
    const chunk = ids.slice(i, i + 100).join(", ");
    const rows = await selectAll(
      zcql,
      `SELECT ROWID, status, stage, lead_id FROM dossier_requests WHERE ROWID IN (${chunk})`,
      "dossier_requests",
    );
    for (const r of rows) {
      statusById.set(String(r.ROWID), {
        status: r.status ?? null,
        stage: r.stage ?? null,
        lead_id: r.lead_id != null && r.lead_id !== "" ? String(r.lead_id) : null,
      });
    }
  }
  for (const e of events) {
    if (e.event_type === "dossier_create" && e.target_id) {
      e.dossier = statusById.get(e.target_id) || { status: "unknown", stage: null, lead_id: null };
    }
  }
}

// GET /audit — paginated org-wide feed, newest first.
//   ?event_type=login,search   filter by type(s)
//   ?q=acme                     free-text over actor + label + action (JS-side)
//   ?from=YYYY-MM-DD&to=...      occurred_at date range
//   ?limit=100&offset=0         pagination
router.get("/", async (req, res) => {
  try {
    const app = req.catalystAdminApp || req.catalystApp;
    const zcql = app.zcql();
    const q = req.query || {};

    const limit = Math.min(
      Math.max(parseInt(q.limit, 10) || FEED_DEFAULT_LIMIT, 1),
      FEED_MAX_LIMIT,
    );
    const offset = Math.max(parseInt(q.offset, 10) || 0, 0);

    const conds = [];
    if (q.event_type) {
      const wanted = String(q.event_type)
        .split(",")
        .map((s) => s.trim())
        .filter((s) => EVENT_TYPES.has(s));
      if (wanted.length) {
        conds.push(`event_type IN (${wanted.map((s) => `'${esc(s)}'`).join(", ")})`);
      }
    }
    if (q.user) conds.push(`user_id = '${esc(q.user)}'`);
    const from = toBound(q.from, false);
    const to = toBound(q.to, true);
    if (from) conds.push(`occurred_at >= '${esc(from)}'`);
    if (to) conds.push(`occurred_at <= '${esc(to)}'`);

    // ZCQL needs at least one predicate after WHERE.
    const where = `WHERE ${conds.length ? conds.join(" AND ") : "ROWID IS NOT NULL"}`;
    const base = `SELECT ${AUDIT_COLS.join(", ")} FROM audit_events ${where} ORDER BY occurred_at DESC`;

    const freeText = q.q && String(q.q).trim() ? String(q.q).trim().toLowerCase() : null;

    let pageRows;
    let hasMore;
    if (freeText) {
      // Pull a bounded recent window, narrow in JS, then page.
      const r = await zcql.executeZCQLQuery(`${base} LIMIT 0, ${FREE_TEXT_SCAN_CAP}`);
      const all = r.map((x) => x.audit_events);
      const matched = all.filter((row) => {
        const hay = [row.actor_email, row.actor_name, row.target_label, row.event_action]
          .filter(Boolean)
          .join("  ")
          .toLowerCase();
        return hay.includes(freeText);
      });
      pageRows = matched.slice(offset, offset + limit);
      hasMore = matched.length > offset + limit;
    } else {
      // Fetch one extra row to compute hasMore without a COUNT.
      const r = await zcql.executeZCQLQuery(`${base} LIMIT ${offset}, ${limit + 1}`);
      const rows = r.map((x) => x.audit_events);
      hasMore = rows.length > limit;
      pageRows = rows.slice(0, limit);
    }

    const events = pageRows.map(reshapeEvent);
    await enrichDossierStatus(zcql, events);

    res.json({ events, limit, offset, hasMore });
  } catch (err) {
    console.error("audit.list error:", err);
    res.status(500).json({ error: err.message || "audit list failed" });
  }
});

// GET /audit/summary — header KPIs + a 7-day series for the Audit Report.
router.get("/summary", async (req, res) => {
  try {
    const app = req.catalystAdminApp || req.catalystApp;
    const zcql = app.zcql();

    const now = Date.now();
    const cutoff7d = catalystDateTime(new Date(now - 7 * 24 * 60 * 60 * 1000));
    const cutoff24h = now - 24 * 60 * 60 * 1000;

    const rows = await selectAll(
      zcql,
      `SELECT ROWID, user_id, actor_email, actor_name, event_type, target_label, occurred_at ` +
        `FROM audit_events WHERE occurred_at >= '${esc(cutoff7d)}' ORDER BY occurred_at DESC`,
      "audit_events",
    );

    const byType = { login: 0, dossier_create: 0, search: 0, lead_view: 0, admin_action: 0 };
    const activeUsers24h = new Set();
    const searchers = new Map(); // user -> { name, count }
    let eventsToday = 0;
    let dossiersToday = 0;
    let searchesToday = 0;
    let loginsToday = 0;

    // 7 UTC-day buckets (oldest → newest) for a small stacked series.
    const dayKeys = [];
    for (let i = 6; i >= 0; i--) {
      dayKeys.push(new Date(now - i * 24 * 60 * 60 * 1000).toISOString().slice(0, 10));
    }
    const series = new Map(dayKeys.map((d) => [d, { date: d, login: 0, dossier_create: 0, search: 0, lead_view: 0, admin_action: 0 }]));

    for (const r of rows) {
      const type = r.event_type;
      if (type in byType) byType[type] += 1;

      const iso = occurredToIso(r.occurred_at);
      const t = iso ? Date.parse(iso) : NaN;
      const dayKey = Number.isFinite(t) ? new Date(t).toISOString().slice(0, 10) : null;
      if (dayKey && series.has(dayKey) && type in byType) series.get(dayKey)[type] += 1;

      const isToday = Number.isFinite(t) && t >= cutoff24h;
      if (isToday) {
        eventsToday += 1;
        if (r.user_id) activeUsers24h.add(String(r.user_id));
        if (type === "dossier_create") dossiersToday += 1;
        if (type === "search") searchesToday += 1;
        if (type === "login") loginsToday += 1;
      }

      if (type === "search") {
        const key = String(r.user_id || r.actor_email || "?");
        const cur = searchers.get(key) || { name: r.actor_name || r.actor_email || "Unknown", count: 0 };
        cur.count += 1;
        searchers.set(key, cur);
      }
    }

    const topSearchers = Array.from(searchers.values())
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);

    res.json({
      window_days: 7,
      total_7d: rows.length,
      events_today: eventsToday,
      active_users_today: activeUsers24h.size,
      dossiers_today: dossiersToday,
      searches_today: searchesToday,
      logins_today: loginsToday,
      by_type_7d: byType,
      top_searchers_7d: topSearchers,
      series_7d: dayKeys.map((d) => series.get(d)),
    });
  } catch (err) {
    console.error("audit.summary error:", err);
    res.status(500).json({ error: err.message || "audit summary failed" });
  }
});

// GET /audit/drilldown?card=events|active_users|dossiers|searches
// Returns the exact rows behind a KPI card. Parity with /summary is guaranteed
// by reproducing its rolling-24h JS test verbatim (occurred_at >= cutoff24h),
// rather than trusting a date-only DB bound.
const DRILL_CARDS = new Set(["events", "active_users", "dossiers", "searches"]);
const CARD_TYPE = { dossiers: "dossier_create", searches: "search" };

router.get("/drilldown", async (req, res) => {
  try {
    const card = String((req.query && req.query.card) || "").trim();
    if (!DRILL_CARDS.has(card)) {
      return res.status(400).json({ error: "invalid card" });
    }

    const app = req.catalystAdminApp || req.catalystApp;
    const zcql = app.zcql();

    const now = Date.now();
    const cutoff24h = now - 24 * 60 * 60 * 1000;
    // 2s slack on the DB bound so rounding never drops a boundary row before
    // the authoritative JS gate below runs.
    const cutoffStr = catalystDateTime(new Date(cutoff24h - 2000));

    const typeName = CARD_TYPE[card]; // undefined for events / active_users
    const where =
      `WHERE occurred_at >= '${esc(cutoffStr)}'` +
      (typeName ? ` AND event_type = '${esc(typeName)}'` : "");
    const base = `SELECT ${AUDIT_COLS.join(", ")} FROM audit_events ${where} ORDER BY occurred_at DESC`;
    const rows = await selectAll(zcql, base, "audit_events");

    // Authoritative parity gate — identical to /summary's isToday test.
    const todayRows = rows.filter((r) => {
      const t = Date.parse(occurredToIso(r.occurred_at));
      return Number.isFinite(t) && t >= cutoff24h;
    });

    if (card === "active_users") {
      const byUser = new Map(); // user_id -> aggregate
      for (const r of todayRows) {
        if (!r.user_id) continue; // same guard as summary's activeUsers24h
        const key = String(r.user_id);
        let u = byUser.get(key);
        if (!u) {
          u = {
            user_id: key,
            actor_name: r.actor_name ?? null,
            actor_email: r.actor_email ?? null,
            count: 0,
            last_at: null,
            by_type: {},
          };
          byUser.set(key, u);
        }
        u.count += 1;
        if (r.event_type) u.by_type[r.event_type] = (u.by_type[r.event_type] || 0) + 1;
        const iso = occurredToIso(r.occurred_at);
        if (iso && (!u.last_at || iso > u.last_at)) u.last_at = iso;
        if (!u.actor_name && r.actor_name) u.actor_name = r.actor_name;
        if (!u.actor_email && r.actor_email) u.actor_email = r.actor_email;
      }
      const users = Array.from(byUser.values()).sort((a, b) =>
        (b.last_at || "").localeCompare(a.last_at || ""),
      );
      return res.json({ card, window_hours: 24, count: users.length, users });
    }

    const events = todayRows.map(reshapeEvent);
    await enrichDossierStatus(zcql, events);
    res.json({ card, window_hours: 24, count: events.length, events });
  } catch (err) {
    console.error("audit.drilldown error:", err);
    res.status(500).json({ error: err.message || "audit drilldown failed" });
  }
});

module.exports = router;
