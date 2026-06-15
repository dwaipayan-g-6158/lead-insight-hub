const { parseDossier } = require("./parser");
const { esc, selectAll, selectOne, catalystDateTime, catalystDateOnly } = require("./db");
const { putHtml, deleteObject } = require("./stratus");

// Catalyst varchar columns silently truncate-or-reject; pre-clip everything.
const COL_MAX = {
  user_id: 50,
  storage_path: 255,
  filename: 255,
  lead_name: 255,
  lead_title: 255,
  company: 255,
  email: 255,
  eliss_version: 50,
  generation_engine: 12,
  tier: 10,
  confidence: 20,
  icp_rating: 20,
  icp_reason: 255,
  fit_conf: 20,
  intent_conf: 20,
  timing_conf: 20,
  budget_conf: 20,
  verdict_headline: 255,
  verdict_next: 255,
  // text columns (10k):
  verdict_insight: 10000,
  executive_brief: 10000,
  demo_playbook: 10000,
};

function clipRow(row) {
  const out = { ...row };
  for (const [k, max] of Object.entries(COL_MAX)) {
    if (typeof out[k] === "string" && out[k].length > max) {
      out[k] = out[k].slice(0, max - 1) + "…";
    }
  }
  return out;
}

// Trusted runtime appended to every stored dossier AFTER the
// untrusted-script strip below. Wires:
//   1. Tab switching   (.tab-btn / .tab-panel with data-tab="…")
//   2. Copy-to-clipboard buttons (.copy-btn with data-copy-payload="…")
//   3. External-link retargeting via postMessage — handled by the
//      LeadDetailPage parent listener (see LeadDetailPage.tsx onMessage).
// Identical to the Python sibling in
// functions/eliss-generator/lib/store_lead.py (DOSSIER_RUNTIME_SCRIPT) —
// keep both copies in sync when editing.
const DOSSIER_RUNTIME_MARKER = "<!-- dossier-runtime-v1 -->";
const DOSSIER_RUNTIME_SCRIPT = `${DOSSIER_RUNTIME_MARKER}
<script>
(function(){
  function legacyCopy(text, cb){
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'absolute';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); cb(); } catch(_) {}
    document.body.removeChild(ta);
  }
  function wire(){
    var btns = document.querySelectorAll('.tab-btn');
    var panels = document.querySelectorAll('.tab-panel');
    btns.forEach(function(btn){
      btn.addEventListener('click', function(){
        var target = btn.getAttribute('data-tab');
        btns.forEach(function(b){
          var active = b.getAttribute('data-tab') === target;
          b.classList.toggle('active', active);
          b.setAttribute('aria-selected', active ? 'true' : 'false');
        });
        panels.forEach(function(p){
          p.classList.toggle('active', p.id === 'tab-' + target);
        });
        try { window.scrollTo({top: 0, behavior: 'smooth'}); } catch(_) { window.scrollTo(0, 0); }
      });
    });
    document.querySelectorAll('.copy-btn').forEach(function(btn){
      btn.addEventListener('click', function(){
        var raw = btn.getAttribute('data-copy-payload') || '""';
        var text = '';
        try { text = JSON.parse(raw); } catch(_) { text = raw; }
        var done = function(){
          var orig = btn.textContent;
          btn.classList.add('copied');
          btn.textContent = 'Copied';
          setTimeout(function(){
            btn.classList.remove('copied');
            btn.textContent = orig;
          }, 1400);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done, function(){ legacyCopy(text, done); });
        } else {
          legacyCopy(text, done);
        }
      });
    });
  }
  document.addEventListener('click', function(e){
    var a = e.target && e.target.closest && e.target.closest('a[href]');
    if (!a) return;
    var h = a.getAttribute('href') || '';
    if (h.charAt(0) === '#' || h.indexOf('mailto:') === 0 || h.indexOf('tel:') === 0) return;
    if (h.indexOf('http://') !== 0 && h.indexOf('https://') !== 0) return;
    e.preventDefault();
    try {
      window.parent.postMessage({ source: 'eliss-dossier', type: 'open-link', url: h }, '*');
    } catch(_) {}
  }, true);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wire);
  } else {
    wire();
  }
})();
</script>`;

// Strip <script>/<iframe>/<object>/<embed>/<form> tags and event-handler
// attributes from uploaded dossier HTML. Defense-in-depth: the iframe
// also runs with `sandbox="allow-scripts"` minus `allow-same-origin`,
// so even if a script slipped through it can't reach the parent origin.
// Whitelist approach would break rich dossier rendering — blacklist of
// dangerous constructs is the pragmatic middle ground here.
//
// After stripping untrusted scripts, append the trusted DOSSIER_RUNTIME
// block so tabs, copy buttons, and link retargeting work in the iframe.
function sanitizeDossierHtml(html) {
  if (typeof html !== "string") return html;
  const stripped = html
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, "")
    .replace(/<iframe\b[^>]*>[\s\S]*?<\/iframe>/gi, "")
    .replace(/<object\b[^>]*>[\s\S]*?<\/object>/gi, "")
    .replace(/<embed\b[^>]*\/?>/gi, "")
    .replace(/<form\b[^>]*>[\s\S]*?<\/form>/gi, "")
    .replace(/\s+on[a-z]+\s*=\s*"[^"]*"/gi, "")
    .replace(/\s+on[a-z]+\s*=\s*'[^']*'/gi, "")
    .replace(/\s+on[a-z]+\s*=\s*[^\s>]+/gi, "")
    .replace(/(href|src|action|formaction)\s*=\s*"javascript:[^"]*"/gi, "$1=\"#\"")
    .replace(/(href|src|action|formaction)\s*=\s*'javascript:[^']*'/gi, "$1='#'")
    .replace(/src\s*=\s*"data:[^"]*"/gi, "src=\"\"")
    .replace(/src\s*=\s*'data:[^']*'/gi, "src=''");
  return appendDossierRuntime(stripped);
}

// Inserts DOSSIER_RUNTIME_SCRIPT immediately before </body>, or
// appends to end if </body> is missing. Removes any pre-existing
// runtime block first so the re-stamp is idempotent.
function appendDossierRuntime(html) {
  const withoutOld = html.replace(
    /<!-- dossier-runtime-v\d+ -->[\s\S]*?<\/script>/gi,
    "",
  );
  if (/<\/body>/i.test(withoutOld)) {
    return withoutOld.replace(/<\/body>/i, `${DOSSIER_RUNTIME_SCRIPT}\n</body>`);
  }
  return `${withoutOld}\n${DOSSIER_RUNTIME_SCRIPT}`;
}

// Parse + sanitize + composite-key upsert (with old-signal replacement) +
// Stratus put. The single source of truth for "user-supplied HTML →
// persisted lead row." Both POST /leads/upload (this Node function) and
// any future Node caller go through here. The Python eliss-generator
// uses a sibling helper that writes from a dossier dict directly,
// skipping the parse half — the two paths share the row SHAPE but not
// the source of the data.
async function parseAndStoreDossier(app, { userId, filename, html }) {
  if (!userId) throw new Error("userId required");
  if (!filename || typeof filename !== "string") throw new Error("filename required");
  if (!html || typeof html !== "string" || html.length < 50) throw new Error("html body too small");
  if (html.length > 5_000_000) throw new Error("html body too large");

  const parsed = parseDossier(html, filename);
  // Parse against the original HTML so dossiers that wrap their dim-rows
  // inside <script type="text/template">…</script> still resolve scores —
  // but PERSIST the sanitized form so Stratus only ever stores XSS-safe
  // HTML. Rendering then injects the cleaned HTML into the iframe.
  const safeHtml = sanitizeDossierHtml(html);
  const safeNameFull = filename.replace(/[^a-zA-Z0-9._-]/g, "_");
  const prefix = `${userId}/${Date.now()}_`;
  const remainingChars = Math.max(50, 250 - prefix.length);
  const safeName = safeNameFull.slice(0, remainingChars);
  const storagePath = `${prefix}${safeName}`;

  await putHtml(app, storagePath, safeHtml);

  const zcql = app.zcql();
  const datastore = app.datastore();

  // Composite-key lookup: (lead_name, company, report_date), scoped to user
  const conds = [
    `user_id = '${esc(userId)}'`,
    `lead_name = '${esc(parsed.lead_name)}'`,
    parsed.company ? `company = '${esc(parsed.company)}'` : `company IS NULL`,
    parsed.report_date ? `report_date = '${esc(parsed.report_date)}'` : `report_date IS NULL`,
  ];
  const existing = await selectOne(
    zcql,
    `SELECT ROWID, storage_path FROM leads WHERE ${conds.join(" AND ")}`,
    "leads",
  );

  const nowIso = catalystDateTime(new Date());
  const baseRowRaw = {
    user_id: userId,
    storage_path: storagePath,
    filename,
    lead_name: parsed.lead_name,
    lead_title: parsed.lead_title,
    company: parsed.company,
    email: parsed.email,
    report_date: catalystDateOnly(parsed.report_date),
    eliss_version: parsed.eliss_version,
    // CSV/HTML uploads aren't produced by either generator — tag them as
    // imported so the admin pill reads "Imported" rather than Heavy/Light.
    generation_engine: "import",
    composite_score: parsed.composite_score,
    tier: parsed.tier,
    confidence: parsed.confidence,
    icp_rating: parsed.icp_rating,
    icp_reason: parsed.icp_reason,
    fit_score: parsed.fit_score,
    fit_max: parsed.fit_max,
    fit_conf: parsed.fit_conf,
    intent_score: parsed.intent_score,
    intent_max: parsed.intent_max,
    intent_conf: parsed.intent_conf,
    timing_score: parsed.timing_score,
    timing_max: parsed.timing_max,
    timing_conf: parsed.timing_conf,
    budget_score: parsed.budget_score,
    budget_max: parsed.budget_max,
    budget_conf: parsed.budget_conf,
    verdict_headline: parsed.verdict_headline,
    verdict_insight: parsed.verdict_insight,
    verdict_next: parsed.verdict_next,
    executive_brief: parsed.executive_brief,
    demo_playbook: parsed.demo_playbook ? JSON.stringify(parsed.demo_playbook) : null,
    updated_at: nowIso,
  };
  const baseRow = clipRow(baseRowRaw);

  let leadRowid;
  let updated = false;
  if (existing) {
    if (existing.storage_path && existing.storage_path !== storagePath) {
      await deleteObject(app, existing.storage_path);
    }
    const updateRow = { ROWID: existing.ROWID, ...baseRow };
    await datastore.table("leads").updateRow(updateRow);
    leadRowid = existing.ROWID;
    updated = true;

    // Replace signals
    const oldSignals = await selectAll(
      zcql,
      `SELECT ROWID FROM lead_signals WHERE lead_id = ${existing.ROWID}`,
      "lead_signals",
    );
    const rowids = oldSignals.map((s) => s.ROWID).filter(Boolean);
    if (rowids.length) {
      await datastore.table("lead_signals").deleteRows(rowids);
    }
  } else {
    const inserted = await datastore.table("leads").insertRow(baseRow);
    leadRowid = inserted.ROWID;
  }

  if (parsed.signals.length) {
    const rows = parsed.signals.map((s) => ({
      lead_id: leadRowid,
      signal_type: s.signal_type,
      label: s.label,
      points: s.points,
      detail: s.detail,
    }));
    await datastore.table("lead_signals").insertRows(rows);
  }

  return {
    id: String(leadRowid),
    lead_name: parsed.lead_name,
    company: parsed.company,
    updated,
    storage_path: storagePath,
  };
}

module.exports = {
  parseAndStoreDossier,
  sanitizeDossierHtml,
  appendDossierRuntime,
  DOSSIER_RUNTIME_MARKER,
  DOSSIER_RUNTIME_SCRIPT,
  clipRow,
  COL_MAX,
};
