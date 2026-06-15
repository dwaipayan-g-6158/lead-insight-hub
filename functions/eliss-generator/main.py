"""eliss-generator — Catalyst Python 3.9 Job Function entry point.

Receives a job param `request_id` (the ROWID of a dossier_requests row).
Runs the 6-stage ELISS pipeline server-side:

    queued → preflight → rocketreach → synthesis → rendering → lint → upload

Each stage transition patches the dossier_requests row so the frontend
poller can show progress. Terminal states write status=succeeded |
status=partial | status=failed and completed_at.

Signature confirmed against zoho-catalyst skill reference.txt §
"Python Job Function Boilerplate" — args are (job_request, context),
order matters.
"""
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import zcatalyst_sdk

# Vendored eliss-light scripts live under skill/scripts/. They were written
# as standalone CLI tools; we import them as modules where possible (preflight,
# rocketreach_client) and subprocess them where their argparse + sys.exit make
# in-process invocation awkward (generate_report).
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "skill" / "scripts"))

import preflight  # noqa: E402  (skill-vendored)
from rocketreach_client import (  # noqa: E402
    RocketReachAuthError,
    RocketReachClient,
    RocketReachError,
    RocketReachRateLimited,
)

from lib import checkpoint  # noqa: E402
from lib.app_settings import get_bool, get_int, load_settings  # noqa: E402
from lib.db import catalyst_datetime, select_one  # noqa: E402
from lib.depth_lint import depth_lint  # noqa: E402
from lib.store_lead import store_lead  # noqa: E402
from lib.synth import synthesize  # noqa: E402

RESUME_TARGET = "eliss-generator"


LOG = logging.getLogger("eliss-generator")
if not LOG.handlers:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="[%(asctime)s] %(levelname)s %(message)s")


class _BlockingError(Exception):
    """Raised after the dossier_requests row has been patched to 'failed'.

    Top-level handler catches this and calls context.close_with_failure
    without re-patching. Avoids double-writes when an inner stage already
    surfaced the failure reason to the user.
    """


def handler(job_request, context):
    """Catalyst Job Function entry — (job_request, context) per docs."""
    request_id = job_request.get_job_param("request_id")
    if not request_id:
        LOG.error("missing request_id in job params; closing as failure")
        context.close_with_failure()
        return

    try:
        app = zcatalyst_sdk.initialize()
    except Exception as e:
        LOG.exception("zcatalyst_sdk.initialize failed: %s", e)
        context.close_with_failure()
        return

    # A resume Job re-enters this same function with resume="1" — it skips
    # preflight/rocketreach/synthesis and re-renders from the Stratus dossier
    # checkpoint, so the (expensive) synthesis call is never re-spent.
    # get_job_param RAISES on an absent key (normal jobs have no `resume`
    # param), so read it defensively — an uncaught throw here would crash the
    # handler before _run_pipeline can patch the row.
    def _opt_param(key):
        try:
            return job_request.get_job_param(key)
        except Exception:
            return None
    resume = str(_opt_param("resume") or "") == "1"
    mode = "resume" if resume else "full"
    LOG.info("starting pipeline (%s) for request_id=%s", mode, request_id)
    try:
        if resume:
            _run_resume(app, str(request_id))
        else:
            _run_pipeline(app, str(request_id))
        context.close_with_success()
    except _BlockingError as e:
        LOG.error("pipeline blocked for request_id=%s: %s", request_id, e)
        context.close_with_failure()
    except Exception as e:
        LOG.exception("unexpected error in pipeline for request_id=%s", request_id)
        try:
            _patch_request(app, request_id,
                           status="failed", stage="error",
                           error_message=str(e)[:9999])
        except Exception:
            pass
        context.close_with_failure()


# ────────────────────────────────────────────────────────────────────────────
#  Request row helpers
# ────────────────────────────────────────────────────────────────────────────

def _patch_request(app, request_id, **fields):
    """Update one or more columns on a dossier_requests row.

    Terminal-state writes (succeeded/failed/partial/cancelled) auto-stamp
    completed_at if the caller didn't provide it.
    """
    if not fields:
        return
    row = dict(fields)
    if row.get("status") in ("succeeded", "failed", "partial", "cancelled"):
        row.setdefault("completed_at", catalyst_datetime())
    row["ROWID"] = int(request_id)
    app.datastore().table("dossier_requests").update_row(row)


def _load_request(app, request_id):
    zcql = app.zcql()
    row = select_one(
        zcql,
        (
            "SELECT ROWID, user_id, intake_name, intake_email, "
            "intake_linkedin_url, intake_company_url, intake_notes "
            f"FROM dossier_requests WHERE ROWID = {int(request_id)}"
        ),
        "dossier_requests",
    )
    if not row:
        # Patch is pointless if the row doesn't exist — surface upstream.
        raise _BlockingError(f"dossier_requests row {request_id} not found")
    return {
        "user_id": row.get("user_id"),
        "intake": {
            "name": row.get("intake_name"),
            "email": row.get("intake_email"),
            "linkedin_url": row.get("intake_linkedin_url"),
            "company_url": row.get("intake_company_url"),
            "notes": row.get("intake_notes"),
        },
    }


# ────────────────────────────────────────────────────────────────────────────
#  Intake helpers
# ────────────────────────────────────────────────────────────────────────────

def _derive_domain(intake):
    """Email > company_url > linkedin (no path). Mirrors skill STEP 1."""
    email = intake.get("email")
    if email and "@" in email:
        return email.split("@", 1)[1].lower().strip()
    company_url = intake.get("company_url")
    if company_url:
        url = company_url.lower().strip()
        url = re.sub(r"^https?://", "", url)
        return url.split("/", 1)[0].lstrip("www.")
    raise _BlockingError(
        "cannot derive domain — provide email or company_url; linkedin_url alone is insufficient"
    )


def _company_name_guess(domain, intake):
    """Cheap fallback when the LLM hasn't yet enriched."""
    if not domain:
        return None
    label = domain.split(".")[0]
    if not label:
        return None
    return label.replace("-", " ").replace("_", " ").title()


# ────────────────────────────────────────────────────────────────────────────
#  Render — subprocess generate_report.py
# ────────────────────────────────────────────────────────────────────────────

def _slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", str(s)).strip("_") or "Unknown"


_OSINT_BANNER_REASONS = {
    "rr_full_miss": "RocketReach has no record of this organization.",
    "rr_company_miss": "RocketReach returned partial data — firmographics missing.",
}


def _inject_osint_banner(html, reason):
    """Prepend an OSINT-only banner div to the rendered HTML.

    Direct HTML injection rather than a markdown callout because the
    callout pipeline runs inside generate_report.py (subprocess); by
    the time we have `html` here, markdown is already rendered. The
    banner div uses inline styles to survive whatever stylesheet the
    renderer emitted.
    """
    detail = _OSINT_BANNER_REASONS.get(reason, "RocketReach data unavailable for this lead.")
    banner = (
        '<div class="eliss-osint-banner" role="status" '
        'style="background:#fef3c7;border:1px solid #f59e0b;'
        'border-left-width:4px;padding:12px 16px;margin:16px;'
        'border-radius:6px;font-family:system-ui,-apple-system,sans-serif;'
        'font-size:13px;color:#78350f;line-height:1.5;">'
        '<strong style="display:block;margin-bottom:4px;">'
        'OSINT-only dossier (no RocketReach baseline)</strong>'
        f'{detail} All values sourced from web search and preflight only. '
        'Confidence is lower than a standard RR-backed dossier — '
        'review carefully before sending outreach.'
        '</div>'
    )
    m = re.search(r"(<body[^>]*>)", html, re.IGNORECASE)
    if m:
        return html[: m.end()] + banner + html[m.end():]
    return banner + html


def _render(dossier_dict, request_id, render_timeout=120):
    """Write dossier JSON to temp dir, subprocess generate_report.py.

    Subprocess (not in-process import) because the script's main() ends in
    sys.exit() and reads sys.argv via argparse — both are awkward to
    monkey-patch reliably from a long-running Job Function.

    Returns (html_path, json_path) for cleanup.
    """
    tmp = Path(tempfile.gettempdir())
    ts = int(time.time() * 1000)
    json_path = tmp / f"eliss_dossier_{request_id}_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dossier_dict, f, indent=2, default=str)

    script = _HERE / "skill" / "scripts" / "generate_report.py"
    if not script.exists():
        raise _BlockingError(f"generate_report.py missing at {script}")

    # Snapshot HTML files in tmp before the render so we can identify the new one.
    pre = set(tmp.glob("ELISS_*.html"))

    result = subprocess.run(
        [
            sys.executable, str(script), str(json_path),
            "--output-dir", str(tmp),
            "--format", "html",
            "--cleanup-input-json",
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=render_timeout,
    )
    if result.returncode != 0:
        stderr_tail = (result.stderr or "")[-500:]
        raise _BlockingError(
            f"generate_report.py exit {result.returncode}: {stderr_tail}"
        )

    new = sorted(tmp.glob("ELISS_*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
    new = [p for p in new if p not in pre] or new
    if not new:
        raise _BlockingError("generate_report.py produced no HTML output")
    return str(new[0]), str(json_path)


# ────────────────────────────────────────────────────────────────────────────
#  Pipeline
# ────────────────────────────────────────────────────────────────────────────

def _get_resume_attempts(app, request_id):
    """Current resume_attempts for a row (0 when null/missing). Best-effort."""
    try:
        zcql = app.zcql()
        row = select_one(
            zcql,
            f"SELECT resume_attempts FROM dossier_requests WHERE ROWID = {int(request_id)}",
            "dossier_requests",
        )
        v = (row or {}).get("resume_attempts")
        return int(v) if v not in (None, "") else 0
    except Exception:
        return 0


def _dispatch_resume(app, request_id, settings, reason):
    """Self-dispatch a fresh Job to finish this request from its checkpoint.

    Parity with the Heavy generator. Light's one expensive asset (the synthesis
    call) is already on Stratus (checkpoint_ready) by the time this is called, so
    a resume re-renders from the checkpoint without re-spending a Claude call.
    Returns True if a resume Job was submitted. On the attempts cap the row is
    failed. If the jobpool env var is missing or the SDK submit fails, the row is
    LEFT running so the Node stale-sweep (cron / api) recovers it (belt+suspenders).
    """
    resume_max = get_int(settings, "light_resume_max_attempts", 4)
    attempts = _get_resume_attempts(app, request_id)
    if attempts >= resume_max:
        _patch_request(app, request_id, status="failed", stage="error",
                       error_message=f"resume attempts exhausted ({attempts}/{resume_max}) after {reason}")
        LOG.error("resume cap hit for request_id=%s (%d/%d)", request_id, attempts, resume_max)
        return False

    jobpool = os.environ.get("ELISS_GEN_JOBPOOL_ID")
    if not jobpool:
        LOG.error("ELISS_GEN_JOBPOOL_ID not set — leaving row running for Node sweep recovery")
        return False

    try:
        # Python SDK: `job` is a @property (NOT a method like Node's .job()) —
        # call submit_job on it directly. jobpool_id goes in the payload.
        short_name = f"er_{str(request_id)[-12:]}"[:20]
        app.job_scheduling().job.submit_job({
            "jobpool_id": jobpool,
            "job_name": short_name,
            "target_type": "Function",
            "target_name": RESUME_TARGET,
            # request_id stays a STRING — bigint ROWID precision (see memory).
            "params": {
                "request_id": str(request_id),
                "resume": "1",
                "resume_reason": str(reason),
            },
        })
    except Exception as e:
        # A Job Function's app may lack scope to submit a job — that's fine; the
        # Node stale-sweep (admin-scoped api / cron) recovers it. Surface the
        # reason on the row for observability without failing it.
        LOG.exception("resume self-dispatch failed (Node sweep will recover): %s", e)
        try:
            _patch_request(app, request_id,
                           error_message=f"self-dispatch failed ({reason}), awaiting sweep: {str(e)[:300]}")
        except Exception:
            pass
        return False

    _patch_request(app, request_id, resume_attempts=attempts + 1, stage="resuming")
    LOG.info("dispatched resume job for request_id=%s (attempt %d/%d, reason=%s)",
             request_id, attempts + 1, resume_max, reason)
    return True


def _run_pipeline(app, request_id):
    # Global super-admin generation settings (empty dict => hardcoded defaults
    # stand; each lookup below falls back to the original constant).
    settings = load_settings(app)
    render_timeout = get_int(settings, "light_render_timeout_s", 120)
    preflight_timeout = get_int(settings, "preflight_timeout_s", 10)
    rr_timeout = get_int(settings, "rocketreach_timeout_s", 20)
    rr_profiles = get_int(settings, "rr_max_bulk_profiles_light", 10)
    lint_retry_max = get_int(settings, "light_lint_retry_max", 1)
    # Self-dispatch deadline (parity with Heavy): if synthesis eats most of the
    # 900s Job budget, defer the kill-prone render tail to a fresh resume Job.
    # Conservative default (720s) so normal fast runs NEVER defer — only
    # genuinely slow synthesis trips it. job_start anchors the elapsed check.
    render_deadline_s = get_int(settings, "light_render_deadline_s", 720)
    job_start = time.monotonic()
    if settings:
        LOG.info("loaded global generation settings: %s keys", len(settings))

    # ---- preflight ----------------------------------------------------------
    _patch_request(app, request_id,
                   status="running", stage="preflight",
                   started_at=catalyst_datetime())
    req = _load_request(app, request_id)
    intake = req["intake"]
    user_id = req["user_id"]
    if not user_id:
        _patch_request(app, request_id,
                       status="failed",
                       error_message="request row missing user_id")
        raise _BlockingError("request row missing user_id")

    try:
        domain = _derive_domain(intake)
    except _BlockingError as e:
        _patch_request(app, request_id, status="failed", error_message=str(e))
        raise

    company_guess = _company_name_guess(domain, intake)
    LOG.info("preflight: domain=%s company=%s", domain, company_guess)
    try:
        preflight_data = preflight.run_preflight(
            domain, company=company_guess, timeout=preflight_timeout, log=sys.stderr,
            lead_email=intake.get("email"),
        )
    except Exception as e:
        _patch_request(app, request_id, status="failed",
                       error_message=f"preflight failed: {str(e)[:500]}")
        raise _BlockingError(f"preflight failed: {e}")

    # ---- rocketreach baseline (auto-degrade on coverage gap) ---------------
    # RR_API_KEY missing and RocketReachAuthError/RateLimited/other-RocketReachError
    # are GENUINE FAILURES — hard-fail so the operator sees them. An empty
    # `company` slot in the returned baseline is a COVERAGE GAP (RR doesn't
    # have firmographics for this org — common for .gov/.edu/non-profits)
    # and is NOT a failure: the pipeline auto-degrades to OSINT-only synthesis.
    _patch_request(app, request_id, stage="rocketreach")
    if not os.environ.get("RR_API_KEY"):
        _patch_request(app, request_id,
                       status="failed",
                       error_message="RR_API_KEY not set — required for server-side generation")
        raise _BlockingError("RR_API_KEY missing")

    rr_call_count = 0
    rr_baseline = None
    rr_degraded = False
    rr_degradation_reason = None
    try:
        client = RocketReachClient(timeout=rr_timeout)
        rr_baseline = client.run_baseline_enrichment(
            domain=domain,
            company_name=company_guess,
            contact_name=intake.get("name"),
            contact_linkedin=intake.get("linkedin_url"),
            contact_email=intake.get("email"),
            max_bulk_profiles=rr_profiles,
        )
        rr_call_count = client.budget_summary().get("total_calls", 0) or 0
    except RocketReachAuthError as e:
        _patch_request(app, request_id, status="failed",
                       error_message=f"RocketReach auth error: {str(e)[:500]}")
        raise _BlockingError(f"RR auth: {e}")
    except RocketReachRateLimited as e:
        _patch_request(app, request_id, status="failed",
                       error_message=f"RocketReach rate-limited: {str(e)[:500]}")
        raise _BlockingError(f"RR rate-limited: {e}")
    except RocketReachError as e:
        _patch_request(app, request_id, status="failed",
                       error_message=f"RocketReach baseline failed: {str(e)[:500]}")
        raise _BlockingError(f"RR baseline failed: {e}")

    # Coverage-gap detection — when RR has no firmographics, the client
    # swallows /company/lookup/ 404s into rr_baseline['errors'] and returns
    # the dict with company=None. That's the degradation signal, NOT a failure.
    has_company = bool(rr_baseline and rr_baseline.get("company"))
    has_named_contact = bool(rr_baseline and rr_baseline.get("named_contact"))
    has_exec_dmu = bool(rr_baseline and rr_baseline.get("exec_dmu_enriched"))

    if not has_company:
        rr_degraded = True
        if not has_named_contact and not has_exec_dmu:
            rr_degradation_reason = "rr_full_miss"
            rr_baseline_for_synth = None
        else:
            rr_degradation_reason = "rr_company_miss"
            rr_baseline_for_synth = rr_baseline
        LOG.info("rr coverage gap (%s) — degrading to OSINT-augmented synthesis",
                 rr_degradation_reason)
        _patch_request(app, request_id,
                       rr_degraded=True,
                       rr_degradation_reason=rr_degradation_reason)
    else:
        rr_baseline_for_synth = rr_baseline

    # ---- synthesis ----------------------------------------------------------
    # Patch rr_calls upfront so a synthesis failure still leaves the observability
    # field populated (previously this only landed after synthesis succeeded).
    _patch_request(app, request_id, stage="synthesis", rr_calls=rr_call_count)
    LOG.info("synthesis: calling Anthropic with web_search (rr_degraded=%s)", rr_degraded)
    # Settings-derived synthesis knobs. None => synthesize() falls back to its
    # own constant / ANTHROPIC_MODEL env var.
    synth_kwargs = dict(
        rr_degraded=rr_degraded,
        rr_degradation_reason=rr_degradation_reason,
        model=settings.get("light_model"),
        max_tokens=settings.get("light_max_tokens"),
        web_search_max_uses=settings.get("light_web_search_max_uses"),
        thinking_enabled=get_bool(settings, "light_thinking_enabled", False),
        thinking_budget=get_int(settings, "light_thinking_budget", 0),
    )
    try:
        dossier_dict, usage = synthesize(
            intake, preflight_data, rr_baseline_for_synth, **synth_kwargs,
        )
    except Exception as e:
        _patch_request(app, request_id, status="failed",
                       error_message=f"synthesis failed: {str(e)[:500]}")
        raise _BlockingError(f"synthesis failed: {e}")

    tokens_in = int(usage.get("input", 0) or 0)
    tokens_out = int(usage.get("output", 0) or 0)

    # ── CHECKPOINT ───────────────────────────────────────────────────────────
    # Light's one big token cost is this synthesis call. Persist the completed
    # dossier to Stratus BEFORE the kill-prone render/upload tail so a failure
    # there (or a 900s kill) is recovered by re-rendering — never a 2nd Claude
    # call. Record spend immediately too (closes the tokens-only-at-render gap).
    # Gated on the master toggle: when off, behavior is byte-identical to before.
    auto_resume = get_bool(settings, "light_auto_resume_enabled", True)
    if auto_resume:
        checkpoint.write_dossier(app, request_id, {
            "schema": 1,
            "request_id": str(request_id),
            "dossier": dossier_dict,
            "usage": usage,
            "intake": intake,
            "user_id": user_id,
            "rr_degraded": rr_degraded,
            "rr_degradation_reason": rr_degradation_reason,
            "rr_call_count": rr_call_count,
        })
        _patch_request(app, request_id,
                       tokens_input=tokens_in, tokens_output=tokens_out,
                       rr_calls=rr_call_count,
                       checkpoint_ready=True, resume_target=RESUME_TARGET)
        LOG.info("dossier checkpoint written; tokens=%s/%s", tokens_in, tokens_out)

        # ── TIME-BUDGET GUARD ────────────────────────────────────────────────
        # Checkpoint is durable. If synthesis ate most of the Job budget, hand
        # the render tail to a fresh resume Job (loads the checkpoint, re-renders,
        # zero re-spent tokens) rather than risk a 900s kill mid-render. Only
        # reachable when auto_resume is on (we're inside that block) AND past the
        # deadline, so fast runs are byte-identical to before. A failed dispatch
        # falls through to in-job render, with the cron/api sweep as backstop.
        elapsed = time.monotonic() - job_start
        if elapsed > render_deadline_s:
            LOG.warning("synthesis took %.0fs (> deadline %ds) — deferring render to a resume job",
                        elapsed, render_deadline_s)
            if _dispatch_resume(app, request_id, settings, reason="render_deadline"):
                return
            LOG.error("deferral dispatch failed for request_id=%s; rendering in-job", request_id)

    # Lint retry re-runs the full synthesis (Light has no cheaper path); only
    # the in-job pipeline does this — a resume never re-synthesizes.
    def _regenerate():
        return synthesize(intake, preflight_data, rr_baseline_for_synth, **synth_kwargs)

    _finalize_light(
        app, request_id,
        settings=settings,
        dossier_dict=dossier_dict,
        intake=intake, user_id=user_id,
        rr_degraded=rr_degraded, rr_degradation_reason=rr_degradation_reason,
        rr_call_count=rr_call_count,
        tokens_in=tokens_in, tokens_out=tokens_out,
        render_timeout=render_timeout,
        regenerate=_regenerate, lint_retry_max=lint_retry_max,
    )


def _soft_hits_exceed_tolerance(lint_result, settings, tier, setting_key):
    """Tier-aware soft-hit gate for the 'partial' (saved-with-warnings) status.
    HOT/WARM stay strict — a single empty cell on a high-value lead warrants a
    rep review. COLD/COOL are expected to be sparse, so tolerate up to
    ``<setting_key>`` isolated empty cells before downgrading. Hard hits + RR
    degradation are evaluated by the caller and still flag partial at every tier.
    """
    t = (tier or "").upper().strip()
    tol = 0 if t in ("HOT", "WARM") else get_int(settings, setting_key, 4)
    return int(lint_result.get("soft_total", 0) or 0) > tol


def _finalize_light(app, request_id, *, settings, dossier_dict, intake, user_id,
                    rr_degraded, rr_degradation_reason, rr_call_count,
                    tokens_in, tokens_out, render_timeout,
                    regenerate=None, lint_retry_max=0):
    """Shared tail: render → lint(+retry) → upload → terminal → checkpoint
    cleanup. The in-job path passes a `regenerate` closure (full re-synthesis)
    and lint_retry_max; the resume path passes regenerate=None so it NEVER
    re-spends a synthesis call — it just re-renders the checkpointed dossier.
    """
    def _stamp_meta(d):
        # Renderer reads meta.rr_degraded to force the illustrative scatter +
        # footnote when an exact timeline can't be derived.
        m = d.get("meta")
        d["meta"] = ({**m, "rr_degraded": rr_degraded}
                     if isinstance(m, dict) else {"rr_degraded": rr_degraded})

    _stamp_meta(dossier_dict)

    # ---- rendering ----------------------------------------------------------
    _patch_request(app, request_id, stage="rendering",
                   tokens_input=tokens_in, tokens_output=tokens_out,
                   rr_calls=rr_call_count)
    html_path, _json_path = _render(dossier_dict, request_id, render_timeout)
    html = Path(html_path).read_text(encoding="utf-8")
    if rr_degraded:
        html = _inject_osint_banner(html, rr_degradation_reason)

    # ---- lint gate (retry on blocking, up to lint_retry_max) ----------------
    _patch_request(app, request_id, stage="lint")
    lint_result = depth_lint(
        html, (dossier_dict.get("scoring") or {}).get("tier"), rr_degraded=rr_degraded,
    )
    LOG.info("depth_lint: %s", lint_result)
    retries_done = 0
    while regenerate and lint_result["blocking"] and retries_done < lint_retry_max:
        retries_done += 1
        LOG.warning("blocking lint hits — regenerating (%d/%d): %s",
                    retries_done, lint_retry_max, lint_result["hits"])
        _patch_request(app, request_id, stage="synthesis_retry")
        try:
            dossier_dict, usage2 = regenerate()
        except Exception as e:
            _patch_request(app, request_id, status="failed",
                           error_message=f"synthesis retry failed: {str(e)[:500]}")
            raise _BlockingError(f"synthesis retry failed: {e}")
        tokens_in += int(usage2.get("input", 0) or 0)
        tokens_out += int(usage2.get("output", 0) or 0)
        _stamp_meta(dossier_dict)
        _patch_request(app, request_id, stage="rendering",
                       tokens_input=tokens_in, tokens_output=tokens_out)
        try:
            Path(html_path).unlink(missing_ok=True)
        except Exception:
            pass
        html_path, _json_path = _render(dossier_dict, request_id, render_timeout)
        html = Path(html_path).read_text(encoding="utf-8")
        if rr_degraded:
            html = _inject_osint_banner(html, rr_degradation_reason)
        _patch_request(app, request_id, stage="lint")
        lint_result = depth_lint(
            html, (dossier_dict.get("scoring") or {}).get("tier"), rr_degraded=rr_degraded,
        )

    # ---- upload -------------------------------------------------------------
    _patch_request(app, request_id, stage="upload")
    company_name = ((dossier_dict.get("company") or {}).get("name") or "Unknown")
    last_name = ((intake.get("name") or "").strip().split(" ") or ["Lead"])[-1]
    date_str = time.strftime("%Y-%m-%d")
    filename = f"ELISS_{_slug(company_name)}_{_slug(last_name)}_{date_str}.html"

    clip_overrides = {}
    for col in ("verdict_insight", "executive_brief", "demo_playbook"):
        v = settings.get(f"clip_{col}")
        if v is not None:
            clip_overrides[col] = int(v)
    try:
        result = store_lead(app, user_id, filename, html, dossier_dict, intake,
                            clip_overrides=clip_overrides or None)
    except Exception as e:
        _patch_request(app, request_id, status="failed",
                       error_message=f"store_lead failed: {str(e)[:500]}")
        raise _BlockingError(f"store_lead failed: {e}")

    # ---- terminal -----------------------------------------------------------
    # Partial ("saved with warnings") on: any HARD lint hit (missing section /
    # zero sources) at any tier, RR degradation, or SOFT cell-level hits beyond
    # the tier-aware tolerance (HOT/WARM strict; COLD/COOL tolerate sparse data).
    tier = (dossier_dict.get("scoring") or {}).get("tier")
    is_partial = bool(
        lint_result["hard_total"] > 0
        or rr_degraded
        or _soft_hits_exceed_tolerance(
            lint_result, settings, tier, "light_lint_soft_tolerance")
    )
    terminal_status = "partial" if is_partial else "succeeded"
    # lead_id is a Catalyst ROWID (17-digit bigint > 2^53). Pass as STRING so
    # JSON-number precision loss doesn't drop the last digit server-side.
    _patch_request(app, request_id,
                   status=terminal_status, stage="done",
                   lead_id=str(result["id"]))
    # Success → drop the checkpoint (best-effort; left on failure for resume).
    checkpoint.cleanup(app, request_id)

    LOG.info("pipeline complete: request_id=%s lead_id=%s status=%s tokens=%s/%s rr_calls=%s",
             request_id, result["id"], terminal_status, tokens_in, tokens_out, rr_call_count)

    for p in (html_path,):
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:
            pass


def _run_resume(app, request_id):
    """Finish a Light request from its Stratus dossier checkpoint — re-render +
    upload only, no synthesis call (zero re-spent tokens).
    """
    settings = load_settings(app)
    render_timeout = get_int(settings, "light_render_timeout_s", 120)

    _patch_request(app, request_id, status="running", stage="resuming")

    cp = checkpoint.read_dossier(app, request_id)
    if not cp or not isinstance(cp.get("dossier"), dict):
        _patch_request(app, request_id, status="failed", stage="error",
                       error_message="resume requested but no dossier checkpoint found")
        raise _BlockingError("no dossier checkpoint to resume from")

    user_id = cp.get("user_id")
    if not user_id:
        _patch_request(app, request_id, status="failed", stage="error",
                       error_message="checkpoint missing user_id")
        raise _BlockingError("checkpoint missing user_id")

    usage = cp.get("usage") or {}
    _finalize_light(
        app, request_id,
        settings=settings,
        dossier_dict=cp["dossier"],
        intake=cp.get("intake") or {},
        user_id=user_id,
        rr_degraded=bool(cp.get("rr_degraded")),
        rr_degradation_reason=cp.get("rr_degradation_reason"),
        rr_call_count=int(cp.get("rr_call_count") or 0),
        tokens_in=int(usage.get("input", 0) or 0),
        tokens_out=int(usage.get("output", 0) or 0),
        render_timeout=render_timeout,
        regenerate=None, lint_retry_max=0,  # never re-synthesize on resume
    )
