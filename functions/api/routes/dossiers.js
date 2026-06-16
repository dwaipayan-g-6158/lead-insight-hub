const express = require("express");
const { esc, selectAll, selectOne, catalystDateTime } = require("../lib/db");
const { isHeavyAllowed } = require("../lib/featureFlags");

const router = express.Router();

const VALID_STATUSES = new Set([
  "pending", "running", "succeeded", "failed", "partial", "cancelled",
]);

// Stale-row backstop, expressed as time since the row's last MODIFIEDTIME
// update. The eliss-generator function patches the row at every stage
// boundary (preflight → rocketreach → synthesis → rendering → lint →
// upload), so MODIFIEDTIME is effectively a free heartbeat without
// needing a dedicated column. The longest legitimate gap between patches
// is a single synthesis call (~10–12 min with web_search × 4); 15 min
// gives ~3 min of grace. Anything stuck longer than that is genuinely
// crashed — the function would have patched the next stage by then.
const STALE_AFTER_MS = 15 * 60 * 1000;

// Catalyst capped intake_linkedin_url and intake_company_url at varchar(255)
// even though we requested 500 — clip on the way in to match.
const URL_MAX = 255;
const NAME_MAX = 255;
const NOTES_MAX = 2000;

function clip(s, max) {
  if (typeof s !== "string") return null;
  const t = s.trim();
  if (!t) return null;
  return t.length > max ? t.slice(0, max - 1) + "…" : t;
}

// Intake invariant — mirrors the /eliss-light STEP 1 INTAKE contract:
// at least one of (name+email), linkedin_url, or company_url must be
// present, otherwise the skill has nothing to anchor enrichment against.
function isValidIntake({ name, email, linkedin_url, company_url }) {
  return Boolean((name && email) || linkedin_url || company_url);
}

// Coerce ZCQL stringified ints back to numbers so the frontend doesn't
// accidentally string-concat them. `lead_id` is INTENTIONALLY excluded
// from this list — it's a Catalyst bigint ROWID (17 digits > 2^53) and
// Number() rounds it to the nearest IEEE-754 double, producing an
// off-by-one ID that 404s on /leads/:id. Keep it as a string. See
// feedback_catalyst_bigint_json_precision in memory for the back-story.
const NUM_FIELDS = ["tokens_input", "tokens_output", "rr_calls"];
function reshapeRequest(row) {
  if (!row) return null;
  const out = { ...row };
  for (const k of NUM_FIELDS) {
    if (k in out && out[k] !== null && out[k] !== undefined && out[k] !== "") {
      out[k] = Number(out[k]);
    }
  }
  if (out.lead_id !== null && out.lead_id !== undefined && out.lead_id !== "") {
    out.lead_id = String(out.lead_id);
  } else {
    out.lead_id = null;
  }
  out.id = row.ROWID != null ? String(row.ROWID) : null;
  return out;
}

// Parse Catalyst's MODIFIEDTIME format ("2026-05-19 00:48:01:386" — note
// the colon-separated millis instead of a dot). Returns epoch ms or null
// if unparseable.
function parseCatalystTimestamp(s) {
  if (!s) return null;
  // Normalize "YYYY-MM-DD HH:MM:SS:mmm" → "YYYY-MM-DDTHH:MM:SS.mmm"
  const normalized = String(s)
    .replace(" ", "T")
    .replace(/:(\d{3})$/, ".$1");
  const ms = new Date(normalized + "Z").getTime();
  return Number.isNaN(ms) ? null : ms;
}

// Read the singleton generation settings (best-effort; {} on miss). Used by
// the self-healing sweep to decide resume-vs-fail without a full merge — only
// the resume toggles + caps are needed here.
async function readGenSettings(app) {
  try {
    const zcql = app.zcql();
    const row = await selectOne(
      zcql,
      `SELECT settings_json FROM app_settings ORDER BY ROWID ASC`,
      "app_settings",
    );
    if (!row || !row.settings_json) return {};
    const obj = JSON.parse(row.settings_json);
    return obj && typeof obj === "object" ? obj : {};
  } catch (e) {
    console.warn("readGenSettings failed (using defaults):", e.message);
    return {};
  }
}

// Catalyst booleans / ints come back over ZCQL as native or stringified —
// normalize both checkpoint_ready shapes to a real boolean.
function truthy(v) {
  return v === true || v === 1 || v === "1" || v === "true";
}

// Sweep rows that haven't been touched (MODIFIEDTIME) in STALE_AFTER_MS.
// SELF-HEALING: a stale row that has a durable checkpoint (checkpoint_ready,
// set only by the generators once the expensive work is on Stratus) and resume
// attempts left is RESUMED — a fresh job finishes it from the checkpoint —
// instead of being failed. So even a hard 900s kill that died before the
// generator could self-dispatch never wastes the tokens already spent. Rows
// with no checkpoint, attempts exhausted, or the feature disabled fall back to
// the original fail behavior. Idempotent.
async function sweepStaleRunning(app, userId) {
  const zcql = app.zcql();
  const datastore = app.datastore();
  // ORDER BY MODIFIEDTIME ASC — oldest-modified first. As soon as we hit
  // a row that's fresh enough, everything after it is fresher → break.
  const rows = await selectAll(
    zcql,
    `SELECT ROWID, CREATEDTIME, MODIFIEDTIME, checkpoint_ready, resume_attempts, resume_target ` +
      `FROM dossier_requests ` +
      `WHERE user_id = '${esc(userId)}' AND status IN ('pending', 'running') ` +
      `ORDER BY MODIFIEDTIME ASC`,
    "dossier_requests",
  );
  if (!rows.length) return 0;

  const settings = await readGenSettings(app);
  const heavyResume = settings.heavy_auto_resume_enabled !== false; // default on
  const lightResume = settings.light_auto_resume_enabled !== false; // default on
  const heavyMax = Number(settings.heavy_resume_max_attempts ?? 4);
  const lightMax = Number(settings.light_resume_max_attempts ?? 4);
  // Age guard — see dossier-sweeper/index.js: a stale row created longer ago
  // than this is abandoned, so clean it up rather than silently regenerating
  // it. Default 3h; tunable via app_settings.sweep_resume_max_age_min. KEEP
  // IN SYNC with the cron sweeper.
  const maxAgeMin = Number(settings.sweep_resume_max_age_min ?? 180);
  const RESUME_MAX_AGE_MS = maxAgeMin * 60 * 1000;
  const jobpoolId = process.env.ELISS_GEN_JOBPOOL_ID;

  const now = Date.now();
  let swept = 0;
  for (const r of rows) {
    const mtMs = parseCatalystTimestamp(r.MODIFIEDTIME);
    if (mtMs == null) continue;
    if (now - mtMs <= STALE_AFTER_MS) break; // sorted ASC — rest are fresher

    const target = r.resume_target || null;
    const attempts = Number(r.resume_attempts || 0);
    const isHeavy = target === "eliss-heavy-generator";
    const resumeEnabled = isHeavy ? heavyResume : lightResume;
    const maxAttempts = isHeavy ? heavyMax : lightMax;
    const createdMs = parseCatalystTimestamp(r.CREATEDTIME);
    // Too old to resume (or unparseable creation time → fail closed): clean up
    // an abandoned request instead of regenerating it.
    const tooOldToResume = createdMs == null || now - createdMs > RESUME_MAX_AGE_MS;

    // Self-heal: resume from checkpoint rather than failing.
    if (jobpoolId && !tooOldToResume && truthy(r.checkpoint_ready) && target && resumeEnabled && attempts < maxAttempts) {
      try {
        const shortName = `er_${String(r.ROWID).slice(-12)}`.slice(0, 20);
        await app.jobScheduling().job().submitJob({
          jobpool_id: jobpoolId,
          job_name: shortName,
          target_type: "Function",
          target_name: target,
          // request_id stays a STRING — bigint ROWID precision (see memory).
          params: { request_id: String(r.ROWID), resume: "1", resume_reason: "sweep" },
        });
        await datastore.table("dossier_requests").updateRow({
          ROWID: r.ROWID,
          stage: "resuming",
          resume_attempts: attempts + 1,
        });
        console.warn(
          `sweep: resumed stale request ${r.ROWID} (attempt ${attempts + 1}/${maxAttempts}, target ${target})`,
        );
        continue; // resumed, not failed — leave status=running
      } catch (e) {
        console.warn("sweep: resume dispatch failed, falling back to fail:", r.ROWID, e.message);
        // fall through to fail
      }
    }

    // Default: mark failed (too old to resume, no checkpoint, attempts
    // exhausted, or resume disabled).
    try {
      const failMsg = tooOldToResume
        ? `Job abandoned — not resumed (no progress and created over ${Math.round(RESUME_MAX_AGE_MS / 60000)} min ago)`
        : `Job stalled — no progress in ${Math.round(STALE_AFTER_MS / 60000)} min`;
      await datastore.table("dossier_requests").updateRow({
        ROWID: r.ROWID,
        status: "failed",
        stage: "error",
        error_message: failMsg,
        completed_at: catalystDateTime(new Date()),
      });
      swept++;
    } catch (e) {
      console.warn("sweepStaleRunning: failed to patch row", r.ROWID, e.message);
    }
  }
  return swept;
}

// Dedup: returns an existing pending/running request for the same intake,
// scoped to this user, so a double-click or browser refresh during submit
// doesn't burn a second ~$0.40 Anthropic run. Matches on linkedin_url,
// email, or company_url in that priority order — those are the strongest
// identity anchors and what the skill itself keys off.
async function findExistingInFlight(app, userId, intake) {
  const zcql = app.zcql();
  const orParts = [];
  if (intake.linkedin_url) orParts.push(`intake_linkedin_url = '${esc(intake.linkedin_url)}'`);
  if (intake.email) orParts.push(`intake_email = '${esc(intake.email)}'`);
  if (intake.company_url) orParts.push(`intake_company_url = '${esc(intake.company_url)}'`);
  if (!orParts.length) return null;
  const row = await selectOne(
    zcql,
    `SELECT * FROM dossier_requests WHERE user_id = '${esc(userId)}' ` +
      `AND status IN ('pending', 'running') AND (${orParts.join(" OR ")}) ` +
      `ORDER BY CREATEDTIME DESC`,
    "dossier_requests",
  );
  return row;
}

// POST /dossiers/generate — accept intake, insert row, dispatch Job.
// Returns 200 with request_id even when the Job pool env var isn't
// configured yet (Phase 3 not deployed) — the row is created so the UI
// can show it as pending, but a warning is logged server-side.
router.post("/generate", async (req, res) => {
  try {
    const body = req.body || {};
    const intake = {
      name: clip(body.name, NAME_MAX),
      email: clip(body.email, NAME_MAX),
      linkedin_url: clip(body.linkedin_url, URL_MAX),
      company_url: clip(body.company_url, URL_MAX),
      notes: clip(body.notes, NOTES_MAX),
    };

    if (!isValidIntake(intake)) {
      return res.status(400).json({
        error: "intake_invariant_failed",
        message: "Provide at least one of: (name AND email), linkedin_url, or company_url",
      });
    }

    const app = req.catalystAdminApp || req.catalystApp;
    const datastore = app.datastore();

    // Dedup guard — don't burn a second Anthropic run on the same person.
    // Sweep stale rows first so a long-dead "running" doesn't false-positive.
    try {
      await sweepStaleRunning(app, req.userId);
    } catch (e) {
      console.warn("sweepStaleRunning failed (continuing):", e.message);
    }
    const existing = await findExistingInFlight(app, req.userId, intake);
    if (existing) {
      return res.status(409).json({
        error: "duplicate_in_flight",
        message: "A dossier for this person is already in progress.",
        request_id: String(existing.ROWID),
        status: existing.status,
        stage: existing.stage || null,
      });
    }

    const row = {
      user_id: req.userId,
      status: "pending",
      stage: "queued",
      intake_name: intake.name,
      intake_email: intake.email,
      intake_linkedin_url: intake.linkedin_url,
      intake_company_url: intake.company_url,
      intake_notes: intake.notes,
    };

    const inserted = await datastore.table("dossier_requests").insertRow(row);
    const requestId = String(inserted.ROWID);

    // Dispatch target selection — `_x:"h"` requests the heavy variant. The
    // gate fails closed: a non-allowlisted user sending the field gets the
    // light path silently, with identical response shape, identical polling
    // cadence, and the same target column in the row. The only difference
    // observable to the requester is the dossier itself (depth + cost) —
    // which they cannot tell apart without comparing two runs.
    const wantsHeavy = (body._x === "h");
    const heavyAllowed = wantsHeavy && (await isHeavyAllowed(req.userId, app));
    const targetName = heavyAllowed ? "eliss-heavy-generator" : "eliss-generator";

    // Observability for the covert downgrade: a non-allowlisted caller that
    // sends `_x:"h"` (e.g. via a tampered client) is silently routed to the
    // light generator. The response shape is intentionally identical, so this
    // warning is the only server-side signal that the gate fired. Without it
    // the gate is impossible to audit from logs.
    if (wantsHeavy && !heavyAllowed) {
      console.warn(
        `heavy_downgrade user_id=${req.userId} request_id=${requestId} requested heavy, routed to light (not allowlisted)`,
      );
    }

    const jobpoolId = process.env.ELISS_GEN_JOBPOOL_ID;
    let catalystJobId = null;
    if (jobpoolId) {
      try {
        // job_name is capped at 20 chars by Catalyst — use a short prefix
        // plus the trailing digits of the request_id for uniqueness.
        const shortName = `eg_${String(requestId).slice(-12)}`.slice(0, 20);
        const job = await app.jobScheduling().job().submitJob({
          jobpool_id: jobpoolId,
          job_name: shortName,
          target_type: "Function",
          target_name: targetName,
          params: { request_id: requestId },
        });
        catalystJobId = job?.job_id || job?.id || job?.details?.job_id || null;
        if (catalystJobId) {
          await datastore.table("dossier_requests").updateRow({
            ROWID: inserted.ROWID,
            catalyst_job_id: String(catalystJobId).slice(0, 50),
          });
        }
      } catch (jobErr) {
        console.error("submitJob failed:", jobErr);
        // Mark the row as failed so the UI surfaces the error immediately
        // instead of polling forever on a stuck "pending".
        await datastore.table("dossier_requests").updateRow({
          ROWID: inserted.ROWID,
          status: "failed",
          error_message: String(jobErr.message || "job dispatch failed").slice(0, 9999),
          completed_at: catalystDateTime(new Date()),
        });
        return res.status(500).json({
          error: "job_dispatch_failed",
          message: jobErr.message || "job dispatch failed",
          request_id: requestId,
        });
      }
    } else {
      console.warn(
        "ELISS_GEN_JOBPOOL_ID not set — request",
        requestId,
        "created but no Job dispatched (Phase 3 not yet deployed)",
      );
    }

    return res.json({
      request_id: requestId,
      status: "pending",
      catalyst_job_id: catalystJobId,
    });
  } catch (err) {
    console.error("dossiers.generate error:", err);
    res.status(500).json({ error: err.message || "generate failed" });
  }
});

// GET /dossiers/generate/:id — status poll for one request.
router.get("/generate/:id", async (req, res) => {
  try {
    const id = String(req.params.id || "");
    if (!/^\d+$/.test(id)) return res.status(400).json({ error: "invalid id" });

    const app = req.catalystAdminApp || req.catalystApp;
    const zcql = app.zcql();

    const row = await selectOne(
      zcql,
      `SELECT * FROM dossier_requests WHERE ROWID = ${id}`,
      "dossier_requests",
    );

    if (!row) return res.status(404).json({ error: "request not found" });

    // Scope to creator unless admin — same pattern as the rest of the API
    // for non-leads data (leads are intentionally org-wide; requests are
    // operational records and stay per-user).
    if (!req.isAdmin && row.user_id !== req.userId) {
      return res.status(404).json({ error: "request not found" });
    }

    res.json({ request: reshapeRequest(row) });
  } catch (err) {
    console.error("dossiers.get error:", err);
    res.status(500).json({ error: err.message || "get failed" });
  }
});

// GET /dossiers/generate — recent + in-flight requests for the current user.
// Optional ?status=pending,running filter drives the "Active requests" pill.
router.get("/generate", async (req, res) => {
  try {
    const q = req.query || {};
    const app = req.catalystAdminApp || req.catalystApp;
    const zcql = app.zcql();

    // Self-heal: any rows still "running" past STALE_AFTER_MS get flipped
    // to failed before we read them out. Keeps the pill from showing a
    // misleading "N in progress" forever when the function crashed.
    try {
      await sweepStaleRunning(app, req.userId);
    } catch (e) {
      console.warn("sweepStaleRunning failed (continuing):", e.message);
    }

    const conds = [`user_id = '${esc(req.userId)}'`];

    if (q.status) {
      const wanted = String(q.status)
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const safe = wanted.filter((s) => VALID_STATUSES.has(s));
      if (safe.length) {
        const list = safe.map((s) => `'${esc(s)}'`).join(", ");
        conds.push(`status IN (${list})`);
      }
    }

    const rows = await selectAll(
      zcql,
      `SELECT * FROM dossier_requests WHERE ${conds.join(" AND ")} ORDER BY CREATEDTIME DESC`,
      "dossier_requests",
    );

    // Cap at 50 client-side after the paginated selectAll pulls them. The
    // active-requests pill only needs a small recent window — we'd add a
    // proper LIMIT-aware variant if this list grows.
    const requests = rows.slice(0, 50).map(reshapeRequest);
    res.json({ requests });
  } catch (err) {
    console.error("dossiers.list error:", err);
    res.status(500).json({ error: err.message || "list failed" });
  }
});

// Terminal-status set, declared once so the bulk-clear and single-clear
// branches stay in sync. "Live" rows (pending/running) are intentionally
// excluded — hard-deleting one would orphan an in-flight Python Job.
const TERMINAL_STATUSES = new Set(["succeeded", "failed", "partial", "cancelled"]);

// DELETE /dossiers/generate?clear_terminal=1
// Hard-deletes every terminal row belonging to the current user. Used by
// the "Clear all" link in the ActiveRequestsPill dropdown.
// Mounted BEFORE the parameterized /generate/:id below so Express routes
// the no-id form to this handler instead of treating "" as :id.
router.delete("/generate", async (req, res) => {
  try {
    if (req.query.clear_terminal !== "1") {
      return res.status(400).json({ error: "missing clear_terminal=1" });
    }
    const app = req.catalystAdminApp || req.catalystApp;
    const zcql = app.zcql();
    const datastore = app.datastore();

    // Bulk-collect ROWIDs to delete. selectAll paginates around the silent
    // ZCQL 300-row cap (see project memory) — fine because a single user's
    // dossier_requests history is unlikely to exceed that, but the helper
    // costs nothing extra.
    const rows = await selectAll(
      zcql,
      `SELECT ROWID, status FROM dossier_requests WHERE user_id = '${esc(req.userId)}'`,
      "dossier_requests",
    );
    const ids = rows
      .filter((r) => TERMINAL_STATUSES.has(r.status))
      .map((r) => r.ROWID);
    if (ids.length === 0) {
      return res.json({ ok: true, deleted: 0 });
    }
    await datastore.table("dossier_requests").deleteRows(ids);
    res.json({ ok: true, deleted: ids.length });
  } catch (err) {
    console.error("dossiers.clearAll error:", err);
    res.status(500).json({ error: err.message || "clear failed" });
  }
});

// DELETE /dossiers/generate/:id
//   default (no ?force)   — cancel a pending request only.
//   with ?force=1         — hard-delete a TERMINAL row (succeeded / partial /
//                           failed / cancelled). Used by the per-row × button
//                           in the ActiveRequestsPill dropdown.
// Cancel-while-running is deferred to v2: the Job is already in flight in
// a Python subprocess by then and graceful interrupt requires Anthropic
// stream abort + SIGTERM coordination we don't need on day one.
router.delete("/generate/:id", async (req, res) => {
  try {
    const id = String(req.params.id || "");
    if (!/^\d+$/.test(id)) return res.status(400).json({ error: "invalid id" });
    const force = req.query.force === "1";

    const app = req.catalystAdminApp || req.catalystApp;
    const zcql = app.zcql();
    const datastore = app.datastore();

    const row = await selectOne(
      zcql,
      `SELECT ROWID, user_id, status FROM dossier_requests WHERE ROWID = ${id}`,
      "dossier_requests",
    );
    if (!row) return res.status(404).json({ error: "request not found" });
    if (!req.isAdmin && row.user_id !== req.userId) {
      return res.status(404).json({ error: "request not found" });
    }

    if (force) {
      // Per-row hard-delete from the inbox. Refuse on live rows so we
      // never orphan an in-flight Job — user should let it finish (or
      // cancel via the default DELETE) before clearing.
      if (!TERMINAL_STATUSES.has(row.status)) {
        return res.status(409).json({
          error: "cannot_clear_live",
          message: `request is ${row.status}; only terminal requests can be cleared`,
        });
      }
      await datastore.table("dossier_requests").deleteRow(row.ROWID);
      return res.json({ ok: true, deleted: 1 });
    }

    if (row.status !== "pending") {
      return res.status(409).json({
        error: "cannot_cancel",
        message: `request is ${row.status}; only pending requests can be cancelled`,
      });
    }

    await datastore.table("dossier_requests").updateRow({
      ROWID: row.ROWID,
      status: "cancelled",
      completed_at: catalystDateTime(new Date()),
    });

    res.json({ ok: true, status: "cancelled" });
  } catch (err) {
    console.error("dossiers.cancel error:", err);
    res.status(500).json({ error: err.message || "cancel failed" });
  }
});

module.exports = router;
