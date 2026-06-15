"""Write a generated dossier to the leads + lead_signals tables and Stratus.

Sibling of the Node `parseAndStoreDossier` in functions/api/lib/storeDossier.js,
but specialized for the generate path: the dossier dict is already in hand
(produced by Anthropic synthesis), so the HTML parse step is skipped. Both
paths produce identical row shapes in the `leads` table.

The 12 Tab 1 contract fields (per feedback_eliss_tab1_card_contracts and
project_eliss_tab1_dict_unwrap) are unwrapped via _extract_value so structured
{value, confidence, tier} dicts flatten into the row's scalar columns.
"""
import json
import os
import re
import time

from .db import (
    catalyst_date_only,
    catalyst_datetime,
    esc,
    select_all,
    select_one,
)

STRATUS_BUCKET = os.environ.get("STRATUS_BUCKET", "dossiers")

# Match the Node sanitizer regex set in functions/api/lib/storeDossier.js so
# uploads and generations both write XSS-safe HTML to Stratus.
_SANITIZE_PATTERNS = [
    (re.compile(r"<script\b[^>]*>[\s\S]*?</script>", re.IGNORECASE), ""),
    (re.compile(r"<iframe\b[^>]*>[\s\S]*?</iframe>", re.IGNORECASE), ""),
    (re.compile(r"<object\b[^>]*>[\s\S]*?</object>", re.IGNORECASE), ""),
    (re.compile(r"<embed\b[^>]*/?>", re.IGNORECASE), ""),
    (re.compile(r"<form\b[^>]*>[\s\S]*?</form>", re.IGNORECASE), ""),
    (re.compile(r'\s+on[a-z]+\s*=\s*"[^"]*"', re.IGNORECASE), ""),
    (re.compile(r"\s+on[a-z]+\s*=\s*'[^']*'", re.IGNORECASE), ""),
    (re.compile(r"\s+on[a-z]+\s*=\s*[^\s>]+", re.IGNORECASE), ""),
    (re.compile(r'(href|src|action|formaction)\s*=\s*"javascript:[^"]*"', re.IGNORECASE), r'\1="#"'),
    (re.compile(r"(href|src|action|formaction)\s*=\s*'javascript:[^']*'", re.IGNORECASE), r"\1='#'"),
    (re.compile(r'src\s*=\s*"data:[^"]*"', re.IGNORECASE), 'src=""'),
    (re.compile(r"src\s*=\s*'data:[^']*'", re.IGNORECASE), "src=''"),
]

# Trusted runtime appended to every stored dossier AFTER the untrusted-script
# strip above. Keep byte-identical with the Node sibling at
# functions/api/lib/storeDossier.js (DOSSIER_RUNTIME_SCRIPT) — both paths
# write to the same Stratus bucket and the viewer expects one runtime.
DOSSIER_RUNTIME_MARKER = "<!-- dossier-runtime-v1 -->"
DOSSIER_RUNTIME_SCRIPT = DOSSIER_RUNTIME_MARKER + """
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
</script>"""

_RUNTIME_BLOCK_PATTERN = re.compile(
    r"<!-- dossier-runtime-v\d+ -->[\s\S]*?</script>",
    re.IGNORECASE,
)
_BODY_CLOSE_PATTERN = re.compile(r"</body>", re.IGNORECASE)


def append_dossier_runtime(html):
    """Insert DOSSIER_RUNTIME_SCRIPT before </body>; idempotent.

    Uses a lambda for the replacement so the script body (which contains
    JS escapes that re.sub would otherwise interpret as backreferences)
    is inserted verbatim.
    """
    without_old = _RUNTIME_BLOCK_PATTERN.sub("", html)
    insertion = DOSSIER_RUNTIME_SCRIPT + "\n</body>"
    if _BODY_CLOSE_PATTERN.search(without_old):
        return _BODY_CLOSE_PATTERN.sub(lambda _m: insertion, without_old, count=1)
    return without_old + "\n" + DOSSIER_RUNTIME_SCRIPT

# Catalyst varchar columns silently truncate — pre-clip everything. Mirrors
# COL_MAX in functions/api/lib/storeDossier.js exactly.
COL_MAX = {
    "user_id": 50,
    "storage_path": 255,
    "filename": 255,
    "lead_name": 255,
    "lead_title": 255,
    "company": 255,
    "email": 255,
    "eliss_version": 50,
    "generation_engine": 12,
    "tier": 10,
    "confidence": 20,
    "icp_rating": 20,
    "icp_reason": 255,
    "fit_conf": 20,
    "intent_conf": 20,
    "timing_conf": 20,
    "budget_conf": 20,
    "verdict_headline": 255,
    "verdict_next": 255,
    "verdict_insight": 10000,
    "executive_brief": 10000,
    "demo_playbook": 10000,
}


def sanitize_html(html):
    out = html
    for pattern, replacement in _SANITIZE_PATTERNS:
        out = pattern.sub(replacement, out)
    return append_dossier_runtime(out)


def _extract_value(node):
    """Unwrap {value, confidence, tier} structured-value dicts.

    Same shape contract as the eliss generate_report.py renderer — see
    project_eliss_tab1_dict_unwrap. Returns the raw scalar when not a dict.
    """
    if isinstance(node, dict):
        if "value" in node:
            return node["value"]
        return None
    return node


def _ensure_dict(v):
    """Coerce non-dict (str, list, None) to {} so downstream `.get()` is safe.

    Defends against synthesis output where a section like `lead` or `scoring`
    was emitted as a flat string instead of the expected dict. Without this,
    `dossier_dict.get("lead") or {}` returns the truthy string unchanged and
    `lead.get("name")` crashes with `'str' object has no attribute 'get'`.
    The malformed section degrades to empty-state in the leads card; the
    dossier HTML itself is unaffected (it already rendered before we get here).
    """
    return v if isinstance(v, dict) else {}


def _clip(s, max_len):
    if not isinstance(s, str):
        return s
    if len(s) > max_len:
        return s[: max_len - 1] + "…"
    return s


def _clip_row(row, col_max=None):
    out = dict(row)
    limits = col_max or COL_MAX
    for k, m in limits.items():
        if isinstance(out.get(k), str) and len(out[k]) > m:
            out[k] = out[k][: m - 1] + "…"
    return out


_CANONICAL_DIM_MAX = {"fit": 25, "intent": 25, "timing": 30, "budget": 20}


def _dim(scoring, name):
    """Pull score/max/conf for one dimension.

    Looks in scoring.dimensions[<name>] (preferred per the schema), then falls
    back to scoring.[<name>] flat — the LLM has been observed to flatten the
    nested shape away despite the system-prompt instruction. Also accepts the
    case where the value at .score is itself a dict {value, confidence, tier}.

    `max` falls back to the canonical rubric value (fit=25, intent=25,
    timing=30, budget=20 — same constants the renderer hardcodes at
    skill/scripts/generate_report.py:3810) when the LLM omits it. Without
    this fallback the React lead-detail Dimensions widget can't compute
    score/max ratios and renders empty even though the dossier itself is
    fine. The renderer doesn't depend on the column — only the outer chrome.
    """
    scoring = scoring or {}
    dims = scoring.get("dimensions") or {}
    block = dims.get(name) or scoring.get(name) or {}
    canonical_max = _CANONICAL_DIM_MAX.get(name)
    if not isinstance(block, dict):
        # If the LLM put a bare score at scoring.<name>, treat that as score-only.
        return {"score": _extract_value(block), "max": canonical_max, "conf": None}
    return {
        "score": _extract_value(block.get("score")),
        "max": _extract_value(block.get("max")) or canonical_max,
        "conf": _extract_value(block.get("confidence")) or _extract_value(block.get("conf")),
    }


def _scoring_scalar(scoring, *keys):
    """Find the first non-None scalar across `keys`, looking both at the top
    of `scoring` AND inside `scoring.composite` (the LLM keeps nesting it
    there despite the system-prompt instruction not to).
    """
    if not isinstance(scoring, dict):
        return None
    composite = scoring.get("composite")
    if not isinstance(composite, dict):
        composite = {}
    for k in keys:
        for source in (scoring, composite):
            v = _extract_value(source.get(k))
            if v is not None and v != "":
                return v
    return None


def _safe_filename(s):
    """Filesystem-safe slug used as the Stratus key suffix."""
    return re.sub(r"[^a-zA-Z0-9._-]", "_", s)


def _demo_playbook_teaser(dossier_dict):
    """Project demo_playbook into a leads-card teaser.

    Schema reminder (per scripts/generate_report.py build_demo_playbook_html):
        demo_playbook = {
            persona: str,        # top-level — who the demo is for
            opening_hook: str,   # top-level — 90-sec cold open
            ad360:  { value_moments[], discovery_questions[], top_objections[], cta },
            log360: { ...same... }
        }

    Persona + opening_hook live at the demo top level (shared across both
    product blocks). The teaser captures them plus boolean flags for which
    product blocks are populated, so the React preview can show "Includes:
    AD360 demo, Log360 demo" pills without parsing the HTML.

    Returns a JSON string, or None when the dossier omits demo_playbook
    (COOL/COLD tiers per v7.6.0 may legitimately skip it).
    """
    dp = dossier_dict.get("demo_playbook")
    if not isinstance(dp, dict) or not dp:
        return None

    persona = _extract_value(dp.get("persona"))
    opening_hook = _extract_value(dp.get("opening_hook"))

    def _product_populated(prod):
        if not isinstance(prod, dict):
            return False
        return bool(
            (prod.get("value_moments") or [])
            or (prod.get("discovery_questions") or [])
            or (prod.get("top_objections") or [])
            or _extract_value(prod.get("cta"))
        )

    has_ad360 = _product_populated(dp.get("ad360"))
    has_log360 = _product_populated(dp.get("log360"))
    has_playbook = bool(opening_hook or has_ad360 or has_log360)
    if not has_playbook:
        return None
    return json.dumps({
        "persona": persona,
        "opening_hook": opening_hook,
        "has_ad360": has_ad360,
        "has_log360": has_log360,
        "has_playbook": True,
    })


def _build_signals(dossier_dict):
    """Project dossier sections into lead_signals rows.

    The Node upload path extracts signals by parsing the rendered HTML
    (attribution legs, scenario cards, compliance vocab, competitor vocab).
    The generate path has the structured dict in hand so we lift signals
    directly from scoring.attribution[], scoring.scenarios[], compliance[],
    and technology.competitors_detected[].
    """
    signals = []
    seen = set()

    def push(signal_type, label, points, detail):
        if not label:
            return
        key = f"{signal_type}|{str(label).lower()}"
        if key in seen:
            return
        seen.add(key)
        signals.append(
            {
                "signal_type": signal_type,
                "label": str(label)[:200],
                "points": points,
                "detail": (str(detail) if detail is not None else None),
            }
        )

    scoring = _ensure_dict(dossier_dict.get("scoring"))
    for leg in scoring.get("attribution") or []:
        if isinstance(leg, dict):
            push(
                "attribution",
                _extract_value(leg.get("category") or leg.get("label")),
                _extract_value(leg.get("points")),
                _extract_value(leg.get("evidence") or leg.get("detail")),
            )

    for sc in scoring.get("scenarios") or []:
        if isinstance(sc, dict):
            push(
                "scenario",
                _extract_value(sc.get("label") or sc.get("name")),
                _extract_value(sc.get("delta") or sc.get("after_score")),
                _extract_value(sc.get("trigger") or sc.get("description")),
            )

    for c in dossier_dict.get("compliance") or []:
        if isinstance(c, dict):
            framework = _extract_value(c.get("framework"))
            push(
                "compliance",
                framework,
                None,
                _extract_value(c.get("pressure")) or _extract_value(c.get("urgency")),
            )

    tech = _ensure_dict(dossier_dict.get("technology"))
    for comp in tech.get("competitors_detected") or []:
        push("competitor", str(comp) if not isinstance(comp, dict) else _extract_value(comp.get("name")), None, None)

    return signals


def _name_from_email(email):
    """Derive a display name from an email local part — last-resort fallback
    for the mandatory leads.lead_name column.

    jason.brice@amba.info -> "Jason Brice". Returns None when there's no usable
    local part so the caller can fall through to a literal default.
    """
    if not isinstance(email, str) or "@" not in email:
        return None
    local = email.split("@", 1)[0]
    parts = [p for p in re.split(r"[._+-]+", local) if p]
    if not parts:
        return None
    return " ".join(p.capitalize() for p in parts)


def _flatten_lead_fields(dossier_dict, filename, storage_path, user_id, intake=None):
    """Project the dossier dict into the leads-table row shape.

    Source-of-truth contracts live in feedback_eliss_tab1_card_contracts.md;
    the Node parser at functions/api/lib/parser.js is the response-side mirror.
    """
    # Defensive: synthesis occasionally collapses sections to flat strings —
    # see _ensure_dict for the historical incident.
    lead = _ensure_dict(dossier_dict.get("lead"))
    company = _ensure_dict(dossier_dict.get("company"))
    scoring = _ensure_dict(dossier_dict.get("scoring"))
    meta = _ensure_dict(dossier_dict.get("meta"))

    # ICP — schema evolution: legacy was scoring.icp_rating{label,reason} or
    # scoring.icp{...}; v8 (heavy) uses scoring.icp_match + scoring.icp_match_reason
    # as flat scalars. Read both shapes so the leads-row sidebar populates
    # regardless of which the synthesizer emitted.
    icp_match = _extract_value(scoring.get("icp_match"))
    icp_match_reason = _extract_value(scoring.get("icp_match_reason"))
    icp_legacy = scoring.get("icp_rating") or scoring.get("icp") or {}
    if isinstance(icp_legacy, dict):
        icp_label = icp_match or _extract_value(icp_legacy.get("label"))
        icp_reason = icp_match_reason or _extract_value(icp_legacy.get("reason"))
    else:
        icp_label = icp_match or _extract_value(icp_legacy)
        icp_reason = icp_match_reason

    # Verdict — legacy was scoring.verdict{headline,insight,next_step}; v8 puts
    # the decision in scoring.recommended_action + recommendations.{next_steps,outreach.hook}.
    # Compose a verdict surface from whichever shape the synth emitted.
    verdict = _ensure_dict(scoring.get("verdict"))
    recommendations = _ensure_dict(dossier_dict.get("recommendations"))
    rec_action = _extract_value(scoring.get("recommended_action")) or _extract_value(recommendations.get("action"))
    rec_next_steps = recommendations.get("next_steps") if isinstance(recommendations.get("next_steps"), list) else None
    rec_first_step = rec_next_steps[0] if rec_next_steps else None
    rec_outreach = _ensure_dict(recommendations.get("outreach"))
    rec_hook = _extract_value(rec_outreach.get("hook"))

    fit = _dim(scoring, "fit")
    intent = _dim(scoring, "intent")
    timing = _dim(scoring, "timing")
    budget = _dim(scoring, "budget")

    row = {
        "user_id": user_id,
        "storage_path": storage_path,
        "filename": filename,
        # Mandatory Catalyst column — must never be empty. Synthesis output is
        # the preferred source, but under RR-degraded (rr_company_miss) runs the
        # LLM intermittently omits lead.name, which previously caused a 403
        # MANDATORY_MISSING on insert. Fall back to the known intake identity,
        # then an email-derived name, then a literal guard.
        "lead_name": (
            _extract_value(lead.get("name"))
            or (intake or {}).get("name")
            or _name_from_email((intake or {}).get("email"))
            or "Unknown Contact"
        ),
        "lead_title": _extract_value(lead.get("title")),
        "company": _extract_value(company.get("name")),
        "email": _extract_value(lead.get("email")),
        "report_date": catalyst_date_only(_extract_value(meta.get("generated"))),
        "eliss_version": _extract_value(meta.get("version") or meta.get("eliss_version")),
        # Self-identifying engine stamp: this is the Heavy generator (extended
        # 20-profile fan-out). Its Light sibling (eliss-generator) writes
        # "light". Surfaced as an admin-only Heavy/Light pill in the leads UI.
        "generation_engine": "heavy",
        "composite_score": _scoring_scalar(scoring, "final_score", "composite_score"),
        "tier": _scoring_scalar(scoring, "tier"),
        "confidence": _scoring_scalar(scoring, "overall_confidence", "confidence"),
        "icp_rating": icp_label,
        "icp_reason": icp_reason,
        "fit_score": fit["score"],
        "fit_max": fit["max"],
        "fit_conf": fit["conf"],
        "intent_score": intent["score"],
        "intent_max": intent["max"],
        "intent_conf": intent["conf"],
        "timing_score": timing["score"],
        "timing_max": timing["max"],
        "timing_conf": timing["conf"],
        "budget_score": budget["score"],
        "budget_max": budget["max"],
        "budget_conf": budget["conf"],
        # Verdict headline: prefer legacy verdict.headline; fall back to
        # recommended_action ("PURSUE NOW") which is what v8 emits.
        "verdict_headline": _extract_value(verdict.get("headline")) or rec_action,
        # Verdict insight: prefer legacy verdict.insight; fall back to first
        # next_step + outreach.hook composed.
        "verdict_insight": (_extract_value(verdict.get("insight"))
                            or (rec_hook if rec_hook else None)),
        # Verdict next step: prefer legacy; fall back to recommendations.next_steps[0].
        "verdict_next": (_extract_value(verdict.get("next_step") or verdict.get("next"))
                         or rec_first_step),
        "executive_brief": _extract_value(dossier_dict.get("executive_brief")),
        "demo_playbook": _demo_playbook_teaser(dossier_dict),
        "updated_at": catalyst_datetime(),
    }
    # Coerce tier to upper-case to match the existing /upload-path normalization.
    if isinstance(row["tier"], str):
        row["tier"] = row["tier"].upper()
    return row


def store_lead(app, user_id, filename, html, dossier_dict, intake=None,
               clip_overrides=None):
    """Write the dossier to Stratus + leads + lead_signals.

    Composite-key upsert matches the Node upload path:
    (user_id, lead_name, company, report_date).

    clip_overrides: optional {column: max_len} from the super-admin settings,
    clamped by the API to the real column width. Merged over COL_MAX.
    """
    if not user_id:
        raise ValueError("user_id required")
    if not filename:
        raise ValueError("filename required")
    if not html or len(html) < 50:
        raise ValueError("html body too small")

    safe_html = sanitize_html(html)
    safe_name = _safe_filename(filename)
    prefix = f"{user_id}/{int(time.time() * 1000)}_"
    remaining = max(50, 250 - len(prefix))
    storage_path = f"{prefix}{safe_name[:remaining]}"

    # Stratus put — options dict uses snake_case keys per
    # zcatalyst_sdk.stratus.bucket.put_object signature (content_type,
    # meta_data, overwrite, ttl, compress, extract_upload).
    bucket = app.stratus().bucket(STRATUS_BUCKET)
    bucket.put_object(
        storage_path,
        safe_html.encode("utf-8"),
        {"content_type": "text/html; charset=utf-8"},
    )

    # Compose row + composite-key lookup
    zcql = app.zcql()
    datastore = app.datastore()
    base_row_raw = _flatten_lead_fields(dossier_dict, filename, storage_path, user_id, intake)
    effective_col_max = {**COL_MAX, **clip_overrides} if clip_overrides else COL_MAX
    base_row = _clip_row(base_row_raw, effective_col_max)

    lead_name = base_row.get("lead_name")
    company = base_row.get("company")
    report_date = base_row.get("report_date")
    conds = [f"user_id = '{esc(user_id)}'"]
    if lead_name:
        conds.append(f"lead_name = '{esc(lead_name)}'")
    if company:
        conds.append(f"company = '{esc(company)}'")
    else:
        conds.append("company IS NULL")
    if report_date:
        conds.append(f"report_date = '{esc(report_date)}'")
    else:
        conds.append("report_date IS NULL")

    existing = select_one(
        zcql,
        "SELECT ROWID, storage_path FROM leads WHERE " + " AND ".join(conds),
        "leads",
    )

    if existing:
        # Best-effort delete of the old Stratus object so we don't accumulate
        # orphans across regenerations. Failure is logged but non-fatal.
        old_path = existing.get("storage_path")
        if old_path and old_path != storage_path:
            try:
                bucket.delete_object(old_path)
            except Exception as e:
                print(f"[store_lead] old stratus delete failed: {e}")
        update_row = dict(base_row)
        update_row["ROWID"] = existing["ROWID"]
        datastore.table("leads").update_row(update_row)
        lead_rowid = existing["ROWID"]
        updated = True

        old_signals = select_all(
            zcql,
            f"SELECT ROWID FROM lead_signals WHERE lead_id = {existing['ROWID']}",
            "lead_signals",
        )
        rowids = [str(s["ROWID"]) for s in old_signals if s.get("ROWID")]
        if rowids:
            datastore.table("lead_signals").delete_rows(rowids)
    else:
        datastore.table("leads").insert_row(base_row)
        # The SDK's insert_row return value has been observed to carry a
        # ROWID that's off-by-one from the row's actually-committed ROWID
        # (verified 2026-05-18, lead `Satya Nadella @ Microsoft`: SDK
        # returned 31210000000163004, actual row landed at ...163005).
        # Defensively re-SELECT by composite key to canonicalize.
        canonical = select_one(
            zcql,
            (
                f"SELECT ROWID FROM leads WHERE storage_path = '{esc(storage_path)}' "
                f"AND user_id = '{esc(user_id)}'"
            ),
            "leads",
        )
        if canonical is None or not canonical.get("ROWID"):
            raise RuntimeError(
                "leads insert completed but post-insert SELECT could not find the row"
            )
        lead_rowid = canonical["ROWID"]
        updated = False

    signals = _build_signals(dossier_dict)
    if signals:
        rows = [
            {
                "lead_id": lead_rowid,
                "signal_type": s["signal_type"],
                "label": s["label"],
                "points": s["points"],
                "detail": s["detail"],
            }
            for s in signals
        ]
        datastore.table("lead_signals").insert_rows(rows)

    return {
        "id": str(lead_rowid),
        "lead_name": base_row.get("lead_name"),
        "company": base_row.get("company"),
        "updated": updated,
        "storage_path": storage_path,
    }
