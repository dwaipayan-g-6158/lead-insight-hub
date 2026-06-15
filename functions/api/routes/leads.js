const express = require("express");
const multer = require("multer");
const { requireAdmin } = require("../lib/auth");
const { esc, selectAll, selectOne, catalystDateTime } = require("../lib/db");
const { getSignedUrl, deleteObject } = require("../lib/stratus");
const { parseAndStoreDossier } = require("../lib/storeDossier");

const router = express.Router();
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 5 * 1024 * 1024 } });

const LEAD_COLS_FULL = [
  "ROWID", "user_id", "storage_path", "filename",
  "lead_name", "lead_title", "company", "email", "report_date", "eliss_version",
  "generation_engine",
  "composite_score", "tier", "confidence", "icp_rating", "icp_reason",
  "fit_score", "fit_max", "fit_conf",
  "intent_score", "intent_max", "intent_conf",
  "timing_score", "timing_max", "timing_conf",
  "budget_score", "budget_max", "budget_conf",
  "verdict_headline", "verdict_insight", "verdict_next", "executive_brief",
  "demo_playbook",
  "CREATEDTIME", "updated_at", "opened_by_creator_at",
];

const LEAD_COLS_LIST = [
  "ROWID", "lead_name", "lead_title", "company", "email",
  "composite_score", "tier", "report_date", "CREATEDTIME",
  // icp_rating is needed so reshapeLead() can derive the virtual
  // icp_stars field that the post-fetch icp_min filter (and the
  // /leads page UI badge) both rely on. Adding this column keeps us
  // at 10 selected columns — well under the ZCQL 20-col SELECT cap.
  "icp_rating",
  // demo_playbook (v7.6.0) carries the JSON-stringified teaser. The list
  // page no longer renders a "Demo ready" badge, but the column is cheap
  // to keep selected and the detail-page preview still reads it.
  "demo_playbook",
  // user_id + opened_by_creator_at drive the creator-scoped "New" pill:
  // a dossier you created that you haven't opened yet. user_id is stripped
  // from the response after the flag is computed (see the list loop). Still
  // 12 cols — under the ZCQL 20-col SELECT cap.
  "user_id", "opened_by_creator_at",
  // confidence drives the "Low confidence" caution pill on the list page.
  "confidence",
  // generation_engine ("light"|"heavy"|"import") drives the admin-only
  // Heavy/Light engine pill. 13 cols total — still under the ZCQL 20-col cap.
  "generation_engine",
];

// ZCQL returns int/decimal columns as JSON strings — coerce here so the
// frontend doesn't accidentally string-concat scores in aggregations.
const LEAD_NUM_FIELDS = [
  "composite_score", "fit_score", "intent_score", "timing_score", "budget_score",
  "fit_max", "intent_max", "timing_max", "budget_max",
];
const SIGNAL_NUM_FIELDS = ["points"];
const toNum = (v) => (v === null || v === undefined || v === "" ? null : Number(v));
function coerceLeadNumerics(row) {
  if (!row) return row;
  for (const k of LEAD_NUM_FIELDS) if (k in row) row[k] = toNum(row[k]);
  return row;
}
function coerceSignalNumerics(row) {
  if (!row) return row;
  for (const k of SIGNAL_NUM_FIELDS) if (k in row) row[k] = toNum(row[k]);
  return row;
}

// Map ICP rating string → integer 1..5 (server-side mirror of the
// client's icpStar utility). The dashboard widget and /leads filter
// both use exact-bucket semantics: icp_min=N means "exactly N stars"
// (i.e. ICP >= N AND ICP < N+1), not cumulative ≥ N.
function icpRatingToStars(rating) {
  if (rating == null) return null;
  const s = String(rating).toLowerCase().trim();
  if (!s) return null;
  const m = s.match(/(\d+)/);
  if (m) {
    const n = parseInt(m[1], 10);
    if (n >= 1 && n <= 5) return n;
  }
  if (/(excellent|perfect|ideal|bullseye)/.test(s)) return 5;
  if (/(strong|great|high)/.test(s)) return 4;
  if (/(moderate|medium|good|fair)/.test(s)) return 3;
  if (/(weak|low|marginal)/.test(s)) return 2;
  if (/(poor|none|very weak|reject)/.test(s)) return 1;
  return null;
}

// Catalyst stores CREATEDTIME in the project DC's local timezone (e.g.
// IST for the IN datacenter) and emits it as `YYYY-MM-DD HH:mm:ss:SSS`
// — not ISO. The application's updated_at is already UTC ISO. Normalize
// CREATEDTIME to UTC ISO on the way out so client-side date math is
// consistent across both fields.
const DC_OFFSET_MS = 5.5 * 60 * 60 * 1000; // IN datacenter is IST = UTC+5:30
function normalizeCatalystDateTime(raw) {
  if (raw == null) return null;
  const s = String(raw).trim();
  if (!s) return null;
  // Already ISO (Z or ±HH:MM offset)?
  if (/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.*(Z|[+-]\d{2}:?\d{2})$/.test(s)) {
    return new Date(s).toISOString();
  }
  // Catalyst format: "2026-05-15 00:11:45:798" — colon between seconds and ms.
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})(?::(\d{1,3}))?$/);
  if (m) {
    const ms = m[7] ? `.${m[7].padEnd(3, "0").slice(0, 3)}` : "";
    const localIso = `${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}${ms}`;
    const t = Date.parse(localIso + "Z") - DC_OFFSET_MS;
    if (!Number.isNaN(t)) return new Date(t).toISOString();
  }
  return s;
}

// Normalize a string for substring search so accents, smart quotes, and
// stray whitespace don't cause silent misses. Used on BOTH the user's
// query and the haystack so they meet at the same canonical form:
//   - NFKD decomposes accented chars into base + combining marks; we
//     then strip the combining marks. "François" → "francois".
//   - Curly quotes (U+2018/19/1A/1B and U+201C/D/E/F) fold to their
//     ASCII equivalents so a typed straight apostrophe matches data
//     stored with a curly one (the dossier generator emits curly by
//     default).
//   - All whitespace, including non-breaking spaces (U+00A0), collapses
//     to a single ASCII space, then we trim.
//   - Lowercase last so the case-folding handles the diacritic-folded
//     output.
function normalizeForSearch(s) {
  return String(s ?? "")
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[‘’‚‛]/g, "'")
    .replace(/[“”„‟]/g, '"')
    // Fold separator punctuation to space so trailing/leading commas
    // and slashes don't break tokenization. ", ; : ! ? | / \" act like
    // whitespace; hyphens, periods, ampersands, and apostrophes are
    // preserved (they carry meaning in names: Esquibel-Almaraz, AT&T,
    // St. John, O'Brien).
    .replace(/[,;:!?|/\\]+/g, " ")
    .replace(/[\s ]+/g, " ")
    .trim()
    .toLowerCase();
}

// demo_playbook lands as a JSON string (Catalyst text column). Parse it
// here so consumers see a structured object; tolerate malformed JSON by
// returning null rather than throwing — the badge / preview should
// silently degrade rather than crash the leads page.
function parseDemoPlaybook(raw) {
  if (raw == null || raw === "") return null;
  if (typeof raw === "object") return raw;
  try {
    return JSON.parse(String(raw));
  } catch {
    return null;
  }
}

function reshapeLead(row) {
  if (!row) return null;
  const createdUtc = normalizeCatalystDateTime(row.CREATEDTIME ?? row.created_at);
  return coerceLeadNumerics({
    ...row,
    id: row.ROWID != null ? String(row.ROWID) : null,
    created_at: createdUtc,
    CREATEDTIME: createdUtc,
    updated_at: normalizeCatalystDateTime(row.updated_at) ?? row.updated_at ?? null,
    // Computed virtual field — derived from icp_rating, not persisted.
    icp_stars: icpRatingToStars(row.icp_rating),
    demo_playbook: parseDemoPlaybook(row.demo_playbook),
  });
}

function quoteOrNull(v) {
  if (v === null || v === undefined || v === "") return "NULL";
  return `'${esc(v)}'`;
}

router.post("/upload", requireAdmin, upload.single("file"), async (req, res) => {
  try {
    let html;
    let filename;
    if (req.file) {
      html = req.file.buffer.toString("utf8");
      filename = req.file.originalname || req.body?.filename || "dossier.html";
    } else if (req.body?.html && req.body?.filename) {
      html = req.body.html;
      filename = req.body.filename;
    } else {
      return res.status(400).json({ error: "missing file or html body" });
    }

    const app = req.catalystAdminApp || req.catalystApp;
    const result = await parseAndStoreDossier(app, {
      userId: req.userId,
      filename,
      html,
    });

    res.json({
      id: result.id,
      lead_name: result.lead_name,
      company: result.company,
      updated: result.updated,
    });
  } catch (err) {
    console.error("upload error:", err);
    const msg = err.message || "upload failed";
    // parseAndStoreDossier throws these for bad input — surface as 400.
    if (
      msg === "filename required" ||
      msg === "userId required" ||
      msg === "html body too small" ||
      msg === "html body too large"
    ) {
      return res.status(400).json({ error: msg });
    }
    res.status(500).json({ error: msg });
  }
});

router.get("/", async (req, res) => {
  try {
    const zcql = req.catalystApp.zcql();
    const q = req.query || {};

    let signalLeadIds = null;
    if (q.signal_label) {
      const sigConds = [`label = '${esc(q.signal_label)}'`];
      if (q.signal_type) sigConds.push(`signal_type = '${esc(q.signal_type)}'`);
      const sigRows = await selectAll(
        zcql,
        `SELECT lead_id FROM lead_signals WHERE ${sigConds.join(" AND ")}`,
        "lead_signals",
      );
      signalLeadIds = Array.from(new Set(sigRows.map((r) => r.lead_id).filter(Boolean)));
      if (signalLeadIds.length === 0) return res.json({ leads: [] });
      if (signalLeadIds.length > 2000) signalLeadIds = signalLeadIds.slice(0, 2000);
    }

    // Default visibility is org-wide: both 'user' and 'admin' roles see every
    // dossier. Ownership stays attributed via leads.user_id. The optional
    // ?mine=1 (or ?mine=true) query param narrows the list to dossiers the
    // calling user created — same userId pattern as dossiers.js:309.
    const conds = [];
    if (q.mine === "1" || q.mine === "true") {
      conds.push(`user_id = '${esc(req.userId)}'`);
    }
    if (q.tier) conds.push(`tier = '${esc(q.tier)}'`);
    if (q.company) conds.push(`company = '${esc(q.company)}'`);
    if (q.min_score != null && q.min_score !== "")
      conds.push(`composite_score >= ${parseInt(q.min_score, 10)}`);
    if (q.max_score != null && q.max_score !== "")
      conds.push(`composite_score <= ${parseInt(q.max_score, 10)}`);

    // CATALYST ZCQL QUIRK: `LIKE '%X%'` with wildcards returns 0 rows
    // even when X is a clear substring of the stored value. Verified via
    // raw ZCQL on 2026-05-15:
    //   SELECT confidence FROM leads WHERE confidence LIKE '%HIGH%'  → []
    //   SELECT confidence FROM leads WHERE confidence = 'HIGH'        → 4 rows
    // Bare `LIKE 'X'` (no wildcards) and `=` BOTH behave as case-
    // insensitive equality. So all the dashboard click-through filters
    // (confidence, icp_min, search) were silently broken before this
    // patch. The strategy below: use SQL equality for confidence and
    // tier-style filters; do post-fetch JS filtering for substring
    // search and for icp_min (the IN-list of rating strings would
    // overflow the ZCQL 10-condition WHERE-clause limit for icp_min=1).
    if (q.confidence) {
      if (q.confidence === "unknown") {
        conds.push(`(confidence IS NULL OR confidence = '')`);
      } else {
        // ZCQL `=` is case-insensitive, so 'HIGH'/'High'/'high' all match.
        conds.push(`confidence = '${esc(q.confidence)}'`);
      }
    }

    // icp_min and search are deferred to post-fetch JS filtering — see
    // below. We don't push anything into `conds` for them so the SQL
    // returns the broader (tier/company/score-range/signal-filtered)
    // result set, and we narrow in memory.
    const icpMinN =
      q.icp_min != null && q.icp_min !== "" ? parseInt(q.icp_min, 10) : null;
    // Token-AND search: every whitespace-separated token in the query
    // must appear in the normalized haystack. Lets "lisboa marco" match
    // "Marco Lisboa @ AIG" regardless of order. Both sides flow through
    // normalizeForSearch() above so accents, smart quotes, and stray
    // whitespace don't cause silent misses.
    const searchTokens = q.search && String(q.search).trim()
      ? normalizeForSearch(q.search).split(" ").filter(Boolean)
      : null;

    // Apply signalLeadIds in chunks of 300
    let collected = [];
    const baseCols = LEAD_COLS_LIST.join(", ");
    // ZCQL requires at least one predicate after WHERE; emit a true-tautology when no filters apply.
    const whereClause = (extra = []) => {
      const all = [...conds, ...extra];
      return all.length ? `WHERE ${all.join(" AND ")}` : "WHERE ROWID IS NOT NULL";
    };
    if (signalLeadIds) {
      for (let i = 0; i < signalLeadIds.length; i += 300) {
        const chunk = signalLeadIds.slice(i, i + 300);
        const ids = chunk.join(", ");
        const rows = await selectAll(
          zcql,
          `SELECT ${baseCols} FROM leads ${whereClause([`ROWID IN (${ids})`])} ORDER BY composite_score DESC`,
          "leads",
        );
        collected = collected.concat(rows);
        if (collected.length >= 500) break;
      }
    } else {
      collected = await selectAll(
        zcql,
        `SELECT ${baseCols} FROM leads ${whereClause()} ORDER BY composite_score DESC`,
        "leads",
      );
    }

    const seen = new Set();
    const leads = [];
    for (const row of collected) {
      const id = String(row.ROWID);
      if (seen.has(id)) continue;
      seen.add(id);
      const reshaped = reshapeLead(row);
      // Creator-scoped "New" pill: true only on dossiers the caller created
      // and has never opened. Cleared when the creator opens the dossier
      // (see GET /:id below). Strip the raw ownership fields afterwards so
      // we don't leak user_id / the timestamp to the client.
      reshaped.creator_unopened =
        String(row.user_id) === String(req.userId) && !row.opened_by_creator_at;
      delete reshaped.user_id;
      delete reshaped.opened_by_creator_at;
      leads.push(reshaped);
      if (leads.length >= 500) break;
    }

    // ── Post-fetch JS filters (icp_min, search) ──
    // ZCQL doesn't support working substring LIKE; we narrow in memory.
    // Both filters operate on the reshapeLead() output, which already
    // exposes `icp_stars` derived from icp_rating via icpRatingToStars().
    // icp_min uses EXACT-bucket semantics: icp_min=3 returns only leads
    // with icp_stars === 3 (i.e. ICP ≥ 3 AND ICP < 4). The dashboard
    // ICP ladder and the /leads "ICP =" filter buttons both rely on this.
    let filtered = leads;
    if (icpMinN != null && !Number.isNaN(icpMinN)) {
      filtered = filtered.filter((l) => {
        const s = l.icp_stars;
        return typeof s === "number" && s === icpMinN;
      });
    }
    if (searchTokens && searchTokens.length) {
      filtered = filtered.filter((l) => {
        const hay = normalizeForSearch(
          [l.lead_name, l.company, l.lead_title, l.email]
            .filter(Boolean)
            .join("  "),
        );
        return searchTokens.every((t) => hay.includes(t));
      });
    }

    res.json({ leads: filtered });
  } catch (err) {
    console.error("list error:", err);
    res.status(500).json({ error: err.message || "list failed" });
  }
});

router.get("/:id", async (req, res) => {
  try {
    // ROWIDs are 17-digit ints that overflow JS Number precision past 2^53.
    // Keep as raw digit string and embed in ZCQL literally.
    const id = String(req.params.id || "");
    if (!/^\d+$/.test(id)) return res.status(400).json({ error: "invalid id" });

    const app = req.catalystAdminApp || req.catalystApp;
    const zcql = app.zcql();

    // ZCQL caps 20 columns per SELECT — split into two queries, merge.
    const colsA = LEAD_COLS_FULL.slice(0, 18).join(", ");
    const colsB = ["ROWID", ...LEAD_COLS_FULL.slice(18)].join(", ");

    // Org-wide visibility — any authenticated user can view any dossier.
    const partA = await selectOne(
      zcql,
      `SELECT ${colsA} FROM leads WHERE ROWID = ${id}`,
      "leads",
    );
    if (!partA) return res.status(404).json({ error: "lead not found" });
    const partB = await selectOne(
      zcql,
      `SELECT ${colsB} FROM leads WHERE ROWID = ${id}`,
      "leads",
    );

    const lead = reshapeLead({ ...partA, ...(partB || {}) });

    // Clear the creator-scoped "New" pill: the first time the dossier's
    // creator opens it, stamp opened_by_creator_at. Fire-and-forget so we
    // don't block the response on a Data Store roundtrip — the detail page
    // doesn't read this flag, and the next /leads fetch reflects the
    // cleared pill. Only the creator triggers it (a different viewer, even
    // an admin, never stamps it), and only once (guarded on null). Same
    // datetime + admin-datastore + .catch() pattern as auth.js:67-95.
    if (String(lead.user_id) === String(req.userId) && !lead.opened_by_creator_at) {
      (req.catalystAdminApp || req.catalystApp)
        .datastore()
        .table("leads")
        .updateRow({ ROWID: id, opened_by_creator_at: catalystDateTime(new Date()) })
        .catch((e) => console.warn("opened_by_creator_at stamp failed:", e?.message));
    }

    const signalRows = await selectAll(
      zcql,
      `SELECT ROWID, signal_type, label, points, detail, CREATEDTIME FROM lead_signals WHERE lead_id = ${id}`,
      "lead_signals",
    );
    const signals = signalRows.map((s) => ({
      id: String(s.ROWID),
      signal_type: s.signal_type,
      label: s.label,
      points: toNum(s.points),
      detail: s.detail,
    }));

    let html = null;
    let htmlUrl = null;
    // storage_status:
    //   null         → lead row had no storage_path (legacy / never uploaded)
    //   "available"  → inline html was retrieved AND has content
    //   "missing"    → storage_path existed but the object is unreachable
    //                  (deleted from Stratus, or signed URL HEAD 404s).
    //                  The iframe would otherwise be blank, so the UI swaps
    //                  in an empty-state card.
    //
    // We fetch BOTH paths in parallel:
    //   - htmlUrl  → used by the Download button to stream straight from
    //                Stratus (cheap, no proxying through this function).
    //   - html     → inline-serialized into the iframe `srcdoc`. Stratus
    //                serves `X-Frame-Options: SAMEORIGIN`, so its signed
    //                URLs cannot be cross-origin iframe-embedded — the
    //                iframe always uses srcdoc, while the download uses
    //                the signed URL.
    //
    // `getSignedUrl()` returns a URL even when the underlying object is
    // missing (signing is cryptographic — no existence check). So we
    // rely on a non-empty `html` body to decide `storage_status`. When
    // html is empty, we also clear htmlUrl so the Download button can't
    // hand the user a URL that 404s.
    let storage_status = null;
    if (lead.storage_path) {
      storage_status = "missing";
      const { getHtml } = require("../lib/stratus");
      const [signedRes, htmlRes] = await Promise.allSettled([
        getSignedUrl(app, lead.storage_path),
        getHtml(app, lead.storage_path),
      ]);
      if (signedRes.status === "fulfilled" && signedRes.value) {
        htmlUrl = signedRes.value;
      } else if (signedRes.status === "rejected") {
        console.warn("signed url failed:", signedRes.reason?.message);
      }
      if (htmlRes.status === "fulfilled" && typeof htmlRes.value === "string") {
        html = htmlRes.value;
      } else if (htmlRes.status === "rejected") {
        console.warn("html fetch failed:", htmlRes.reason?.message);
      }
      if (typeof html === "string" && html.length > 0) {
        storage_status = "available";
      } else {
        // Object missing — don't expose a download URL that 404s.
        htmlUrl = null;
      }
    }

    res.json({ lead, signals, html, htmlUrl, storage_status });
  } catch (err) {
    console.error("get lead error:", err);
    res.status(500).json({ error: err.message || "get failed" });
  }
});

router.delete("/:id", async (req, res) => {
  // Admin-only — non-admins are rejected before we touch the data store.
  if (!req.isAdmin) return res.status(403).json({ error: "admin role required" });

  // Per-step diagnostics: returned to the client on failure so we can see
  // exactly which SDK call rejected (lookup / signal-delete / stratus /
  // leads-delete) instead of a bare JSON-string error.
  let step = "init";
  try {
    const id = String(req.params.id || "");
    if (!/^\d+$/.test(id)) return res.status(400).json({ error: "invalid id" });

    const app = req.catalystAdminApp || req.catalystApp;
    const zcql = app.zcql();
    const datastore = app.datastore();

    step = "select-lead";
    const lead = await selectOne(
      zcql,
      `SELECT ROWID, storage_path FROM leads WHERE ROWID = ${id}`,
      "leads",
    );
    if (!lead) return res.status(404).json({ error: "lead not found" });

    step = "select-signals";
    const sigs = await selectAll(
      zcql,
      `SELECT ROWID FROM lead_signals WHERE lead_id = ${id}`,
      "lead_signals",
    );
    const sigIds = sigs.map((s) => s.ROWID).filter(Boolean).map((x) => String(x));
    if (sigIds.length) {
      step = `delete-signals(${sigIds.length})`;
      await datastore.table("lead_signals").deleteRows(sigIds);
    }

    if (lead.storage_path) {
      step = "stratus-delete";
      await deleteObject(app, lead.storage_path);
    }

    step = "delete-lead-row";
    await datastore.table("leads").deleteRows([String(id)]);

    res.json({ ok: true });
  } catch (err) {
    console.error(`delete error at step=${step}:`, err);
    res.status(500).json({
      error: err.message || "delete failed",
      step,
      catalyst: err?.code || err?.error_code || null,
    });
  }
});

module.exports = router;
