'use strict';

const catalyst = require('zcatalyst-sdk-node');

// ─────────────────────────────────────────────────────────────────────────────
//  dossier-sweeper — cron-driven GLOBAL self-heal sweep
// ─────────────────────────────────────────────────────────────────────────────
// This is the always-on, engine-agnostic twin of the user-scoped inline
// sweepStaleRunning() in functions/api/routes/dossiers.js. Same 15-min
// staleness rule, same checkpoint-resume-vs-fail decision, same heavy/light
// settings — but scoped to ALL users and triggered by a Catalyst Job-Scheduling
// cron instead of a client poll. A generation Job that hard-dies after
// checkpointing (e.g. an OOM in the render tail) leaves its row status=running;
// the inline sweep only re-fires when the OWNER re-opens the app, so a request
// created on mobile and then backgrounded could orphan indefinitely. This cron
// guarantees recovery within the cron interval regardless of who (if anyone) is
// using the app. Light especially needs this: unlike Heavy it has no proactive
// self-dispatch, so it relies entirely on a sweep to resume from a checkpoint.
//
// KEEP IN SYNC with dossiers.js sweepStaleRunning(): STALE_AFTER_MS, the
// resume/fail branch, and the heavy/light settings keys must match. The inline
// version stays user-scoped (instant per-user feedback, no cross-user
// concurrency); this version is global. See the dual-sweep memory note.

const STALE_AFTER_MS = 15 * 60 * 1000; // MUST match dossiers.js STALE_AFTER_MS
const PAGE = 300; // ZCQL hard-caps SELECT at 300 rows — always paginate

async function selectAll(zcql, base, table) {
  let off = 0;
  const out = [];
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const r = await zcql.executeZCQLQuery(`${base} LIMIT ${off}, ${PAGE}`);
    const rows = r.map((x) => x[table]);
    out.push(...rows);
    if (rows.length < PAGE) break;
    off += PAGE;
  }
  return out;
}

// Catalyst booleans / ints come back over ZCQL as native or stringified.
function truthy(v) {
  return v === true || v === 1 || v === '1' || v === 'true';
}

// Parse Catalyst's MODIFIEDTIME ("2026-06-16 00:24:56:386" — colon-separated
// millis, UTC). Returns epoch ms or null.
function parseCatalystTimestamp(s) {
  if (!s) return null;
  const normalized = String(s).replace(' ', 'T').replace(/:(\d{3})$/, '.$1');
  const ms = new Date(normalized + 'Z').getTime();
  return Number.isNaN(ms) ? null : ms;
}

// Catalyst DateTime columns accept "YYYY-MM-DD HH:MM:SS" (UTC) on input.
function catalystDateTime(d) {
  const pad = (n) => String(n).padStart(2, '0');
  return (
    `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}` +
    ` ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`
  );
}

// Resume toggles + caps from the app_settings singleton (best-effort; {} on
// miss → defaults). Mirrors readGenSettings() in dossiers.js.
async function readGenSettings(zcql) {
  try {
    const r = await zcql.executeZCQLQuery(
      'SELECT settings_json FROM app_settings ORDER BY ROWID ASC LIMIT 0, 1',
    );
    if (!r.length) return {};
    const row = r[0].app_settings;
    if (!row || !row.settings_json) return {};
    const obj = JSON.parse(row.settings_json);
    return obj && typeof obj === 'object' ? obj : {};
  } catch (e) {
    console.warn('dossier-sweeper: readGenSettings failed (using defaults):', e.message);
    return {};
  }
}

// Catalyst Node Job Functions are invoked as (jobRequest, context) — the app
// is NOT pre-injected (that's the Basic/Advanced-IO shape). Initialize the SDK
// here, matching the Python generator's handler(job_request, context) +
// zcatalyst_sdk.initialize() pattern. The SDK auto-detects the project headers
// off whichever arg carries them (.headers / .catalystHeaders).
module.exports = async (jobRequest, context) => {
  try {
    const initObj =
      context && (context.headers || context.catalystHeaders)
        ? context
        : jobRequest && (jobRequest.headers || jobRequest.catalystHeaders)
          ? jobRequest
          : context;
    const app = catalyst.initialize(initObj);
    const zcql = app.zcql();
    const datastore = app.datastore();

    // ORDER BY MODIFIEDTIME ASC — oldest first; break on the first fresh row.
    const rows = await selectAll(
      zcql,
      'SELECT ROWID, MODIFIEDTIME, checkpoint_ready, resume_attempts, resume_target ' +
        "FROM dossier_requests WHERE status IN ('pending', 'running') " +
        'ORDER BY MODIFIEDTIME ASC',
      'dossier_requests',
    );

    if (!rows.length) {
      console.log('dossier-sweeper: no pending/running rows');
      context.closeWithSuccess();
      return;
    }

    const settings = await readGenSettings(zcql);
    const heavyResume = settings.heavy_auto_resume_enabled !== false; // default on
    const lightResume = settings.light_auto_resume_enabled !== false; // default on
    const heavyMax = Number(settings.heavy_resume_max_attempts ?? 4);
    const lightMax = Number(settings.light_resume_max_attempts ?? 4);
    const jobpoolId = process.env.ELISS_GEN_JOBPOOL_ID;

    const now = Date.now();
    let resumed = 0;
    let failed = 0;

    for (const r of rows) {
      const mtMs = parseCatalystTimestamp(r.MODIFIEDTIME);
      if (mtMs == null) continue;
      if (now - mtMs <= STALE_AFTER_MS) break; // sorted ASC — rest are fresher

      const target = r.resume_target || null;
      const attempts = Number(r.resume_attempts || 0);
      const isHeavy = target === 'eliss-heavy-generator';
      const resumeEnabled = isHeavy ? heavyResume : lightResume;
      const maxAttempts = isHeavy ? heavyMax : lightMax;

      // Self-heal: resume from the durable checkpoint rather than failing.
      if (jobpoolId && truthy(r.checkpoint_ready) && target && resumeEnabled && attempts < maxAttempts) {
        try {
          const shortName = `cr_${String(r.ROWID).slice(-12)}`.slice(0, 20);
          await app.jobScheduling().job().submitJob({
            jobpool_id: jobpoolId,
            job_name: shortName,
            target_type: 'Function',
            target_name: target,
            // request_id stays a STRING — bigint ROWID precision.
            params: { request_id: String(r.ROWID), resume: '1', resume_reason: 'cron-sweep' },
          });
          await datastore.table('dossier_requests').updateRow({
            ROWID: r.ROWID,
            stage: 'resuming',
            resume_attempts: attempts + 1,
          });
          resumed++;
          console.warn(
            `dossier-sweeper: resumed stale request ${r.ROWID} ` +
              `(attempt ${attempts + 1}/${maxAttempts}, target ${target})`,
          );
          continue; // resumed, not failed — leave status=running
        } catch (e) {
          console.warn(
            'dossier-sweeper: resume dispatch failed, falling back to fail:',
            r.ROWID,
            e.message,
          );
          // fall through to fail
        }
      }

      // Default: mark failed (no checkpoint, attempts exhausted, or disabled).
      try {
        await datastore.table('dossier_requests').updateRow({
          ROWID: r.ROWID,
          status: 'failed',
          stage: 'error',
          error_message: `Job stalled — no progress in ${Math.round(STALE_AFTER_MS / 60000)} min`,
          completed_at: catalystDateTime(new Date()),
        });
        failed++;
      } catch (e) {
        console.warn('dossier-sweeper: failed to patch row', r.ROWID, e.message);
      }
    }

    console.log(
      `dossier-sweeper done: scanned=${rows.length} resumed=${resumed} failed=${failed}`,
    );
    context.closeWithSuccess();
  } catch (error) {
    console.error('dossier-sweeper error:', error);
    context.closeWithFailure();
  }
};
