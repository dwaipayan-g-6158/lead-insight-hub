"""eliss-heavy-generator — Catalyst Python 3.9 Job Function entry point.

Heavyweight sibling of eliss-generator. Same intake → leads + Stratus → polling
contract; the difference is the synthesis stage, which fans out FOUR parallel
Anthropic API calls (Tech / Compliance / Org / Behavioral) and consolidates the
fragments in a final parent-synthesis call. ~3x token cost vs. light, ~10x
RocketReach baseline (uses max_bulk_profiles=20 instead of 10).

Trigger contract is identical to eliss-generator — `request_id` job param,
patches the same `dossier_requests` row through the same stage column. The
front-end ActiveRequestsPill / poller does NOT need to know it's the heavy
function; users see "synthesis" as the longest stage, same as light.

Stage progression:
    queued → preflight → rocketreach → fanout → synthesis → rendering → lint → upload

Job-cap math (must fit Catalyst's 15-min Job Function ceiling):
    preflight       ~10s   (free OSINT endpoints, parallel HTTP)
    rocketreach     ~30s   (~25 RR API calls, mostly serial)
    fanout          ~600s  (4 × asyncio.wait_for, each subagent capped at 600s
                            with max_uses=10 on web_search; in practice 4-8 min)
    synthesis       ~120s  (parent merges fragments — no tools, just text gen)
    rendering+lint  ~10s
    upload          ~5s
    ─────────────────
    total           ~13 min worst-case; ~8-10 min typical.

If reliability falls short (partial > 20% of runs), promote to the 2-Job
pipeline described in the plan file. For now: capped fan-out, partial-tolerant.
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

# Vendored eliss skill scripts (mirror eliss-generator layout).
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "skill" / "scripts"))

import preflight  # noqa: E402
from rocketreach_client import (  # noqa: E402
    RocketReachAuthError,
    RocketReachClient,
    RocketReachError,
    RocketReachRateLimited,
)

from lib import checkpoint  # noqa: E402
from lib.app_settings import get_bool, get_int, get_str, load_settings  # noqa: E402
from lib.db import catalyst_datetime, select_one  # noqa: E402
from lib.depth_lint import depth_lint  # noqa: E402
from lib.fanout import (  # noqa: E402
    ParentSynthesisTimeout,
    merge_usage,
    run_fanout_only,
    run_parent_only,
)
from lib.store_lead import store_lead  # noqa: E402
from lib.synthesis_shards import run_sharded_synthesis  # noqa: E402

RESUME_TARGET = "eliss-heavy-generator"


LOG = logging.getLogger("eliss-heavy-generator")
if not LOG.handlers:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="[%(asctime)s] %(levelname)s %(message)s")


class _BlockingError(Exception):
    """Mirror of eliss-generator's sentinel — see that file for rationale."""


def handler(job_request, context):
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
    # preflight/rocketreach/fanout entirely and finishes from the Stratus
    # checkpoint, so no research tokens are ever re-spent.
    # get_job_param RAISES on an absent key (normal jobs have no `resume`
    # param), so read it defensively — an uncaught throw here would crash the
    # handler before _run_pipeline can patch the row.
    def _opt_param(key):
        try:
            return job_request.get_job_param(key)
        except Exception:
            return None
    resume = str(_opt_param("resume") or "") == "1"
    resume_reason = _opt_param("resume_reason") or "unknown"
    mode = "resume" if resume else "full"
    LOG.info("starting heavy pipeline (%s) for request_id=%s reason=%s",
             mode, request_id, resume_reason if resume else "-")
    try:
        if resume:
            _run_resume(app, str(request_id), resume_reason)
        else:
            _run_pipeline(app, str(request_id))
        context.close_with_success()
    except _BlockingError as e:
        LOG.error("heavy pipeline blocked for request_id=%s: %s", request_id, e)
        context.close_with_failure()
    except Exception as e:
        LOG.exception("unexpected error in heavy pipeline for request_id=%s", request_id)
        try:
            _patch_request(app, request_id,
                           status="failed", stage="error",
                           error_message=str(e)[:9999])
        except Exception:
            pass
        context.close_with_failure()


def _patch_request(app, request_id, **fields):
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

    Returns True if a resume Job was submitted. On the attempts cap the row is
    failed. If the jobpool env var is missing or the SDK submit fails, the row
    is LEFT running so the Node stale-sweep can recover it (belt + suspenders).
    """
    resume_max = get_int(settings, "heavy_resume_max_attempts", 4)
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
        # A Job Function's app may lack admin scope to submit a job — that's
        # expected; the Node stale-sweep (admin-scoped api function) recovers it.
        # Surface the reason on the row for observability without failing it.
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


def _derive_domain(intake):
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
    if not domain:
        return None
    label = domain.split(".")[0]
    if not label:
        return None
    return label.replace("-", " ").replace("_", " ").title()


def _slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", str(s)).strip("_") or "Unknown"


def _render(dossier_dict, request_id, render_timeout=180):
    tmp = Path(tempfile.gettempdir())
    ts = int(time.time() * 1000)
    json_path = tmp / f"eliss_heavy_dossier_{request_id}_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dossier_dict, f, indent=2, default=str)

    script = _HERE / "skill" / "scripts" / "generate_report.py"
    if not script.exists():
        raise _BlockingError(f"generate_report.py missing at {script}")

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


# Auto-gate tuning — "auto" mode needs no settings. Single-stream parent
# throughput measured at ~46 tok/s on the dev account (2026-06-11). The gate
# assumes a rich HOT-sized monolithic dossier and shards only when that (plus a
# possible lint retry) wouldn't safely fit the remaining 900s budget. Both are
# optional super-admin overrides via settings, but the constants are the default.
_HEAVY_SINGLE_STREAM_TPS = 46
_HEAVY_MONOLITHIC_EST_TOKENS = 30000


def _should_shard(settings, *, elapsed_s, render_reserve_s, lint_retry_max):
    """Decide monolithic vs sharded synthesis for this run.

    Mode `heavy_synthesis_mode` (default "auto"):
      - "monolithic": never shard (original single-call behavior).
      - "sharded":    always shard.
      - "auto":       budget-predictive — shard only when a serial monolithic
                      parent (plus a possible lint retry) wouldn't fit the
                      remaining 900s budget at the account's throughput. So a
                      fast account / small dossier stays monolithic (cheaper),
                      a slow account / rich dossier shards automatically.
    """
    mode = (get_str(settings, "heavy_synthesis_mode", "auto") or "auto").lower()
    if mode == "monolithic":
        return False
    if mode == "sharded":
        return True
    tps = max(get_int(settings, "heavy_throughput_tokens_per_s", _HEAVY_SINGLE_STREAM_TPS), 1)
    est_tokens = get_int(settings, "heavy_monolithic_est_output_tokens", _HEAVY_MONOLITHIC_EST_TOKENS)
    est_monolithic_s = est_tokens / tps
    retry_mult = 2 if (lint_retry_max or 0) > 0 else 1
    remaining = 900 - elapsed_s - render_reserve_s - 30
    need = est_monolithic_s * retry_mult
    decision = need > remaining
    LOG.info("synthesis auto-gate: est_monolithic=%.0fs x%d=%.0fs vs remaining=%.0fs -> %s",
             est_monolithic_s, retry_mult, need, remaining, "SHARDED" if decision else "monolithic")
    return decision


def _synthesize(fragments, intake, preflight_data, rr_baseline, *,
                settings, parent_kwargs, use_sharded, degraded=False):
    """Run parent synthesis and return (dossier, usage).

    `use_sharded` is decided by the caller via _should_shard. Sharded and
    monolithic both return the same (dossier, usage) tuple, so the caller's
    checkpoint/finalize tail is unchanged. ParentSynthesisTimeout propagates so
    the caller can defer to a resume job. Any other sharded error falls back to
    the monolithic parent when heavy_sharded_fallback_on_error is on — so a
    sharding bug degrades gracefully instead of failing the dossier.
    """
    if use_sharded:
        try:
            return run_sharded_synthesis(
                fragments, intake, preflight_data, rr_baseline,
                settings=settings, degraded=degraded, **parent_kwargs,
            )
        except ParentSynthesisTimeout:
            raise
        except Exception as e:
            if get_bool(settings, "heavy_sharded_fallback_on_error", True):
                LOG.warning("sharded synthesis failed (%s) — falling back to monolithic parent",
                            str(e)[:300])
                return run_parent_only(
                    fragments, intake, preflight_data, rr_baseline,
                    degraded=degraded, **parent_kwargs,
                )
            raise
    return run_parent_only(
        fragments, intake, preflight_data, rr_baseline,
        degraded=degraded, **parent_kwargs,
    )


def _run_pipeline(app, request_id):
    # Wall-clock start — the time-budget guard below compares elapsed against
    # heavy_synthesis_deadline_s to decide whether to finish in-process or hand
    # the parent synthesis to a fresh resume Job (so a 900s kill never wastes
    # the fan-out tokens).
    job_start = time.monotonic()

    # Global super-admin generation settings (empty dict => hardcoded defaults
    # stand; each lookup below falls back to the original constant).
    settings = load_settings(app)
    render_timeout = get_int(settings, "heavy_render_timeout_s", 180)
    preflight_timeout = get_int(settings, "preflight_timeout_s", 10)
    rr_timeout = get_int(settings, "rocketreach_timeout_s", 20)
    rr_profiles = get_int(settings, "rr_max_bulk_profiles_heavy", 20)
    lint_retry_max = get_int(settings, "heavy_lint_retry_max", 0)
    auto_resume = get_bool(settings, "heavy_auto_resume_enabled", True)
    deadline_s = get_int(settings, "heavy_synthesis_deadline_s", 660)
    parent_timeout_s = get_int(settings, "heavy_parent_timeout_s", 240)
    if settings:
        LOG.info("loaded global generation settings: %s keys", len(settings))

    # ---- preflight ---------------------------------------------------------
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

    # ---- rocketreach baseline (deeper than light: 20 profiles vs 10) ------
    _patch_request(app, request_id, stage="rocketreach")
    if not os.environ.get("RR_API_KEY"):
        _patch_request(app, request_id,
                       status="failed",
                       error_message="RR_API_KEY not set — required for heavy generation")
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

    # ---- fanout (4 parallel subagents) -------------------------------------
    _patch_request(app, request_id, stage="fanout", rr_calls=rr_call_count)
    LOG.info("fanout: dispatching 4 parallel Anthropic subagents")
    # Settings-derived knobs; None => the fanout/parent helpers fall back to
    # their constants / the ANTHROPIC_*_MODEL env vars. Split into fanout vs
    # parent so we can checkpoint between them and defer the parent if late.
    fanout_kwargs = dict(
        rr_degraded=rr_degraded,
        rr_degradation_reason=rr_degradation_reason,
        subagent_model=settings.get("heavy_subagent_model"),
        subagent_max_tokens=settings.get("heavy_subagent_max_tokens"),
        subagent_web_search_max_uses=settings.get("heavy_subagent_web_search_max_uses"),
        subagent_timeout_s=settings.get("heavy_subagent_timeout_s"),
        subagent_payload_max_chars=settings.get("heavy_subagent_rr_trim_max_chars"),
        log=LOG,
        # Heartbeat-only stage flips so the poller doesn't think we stalled.
        on_stage=lambda s: _patch_request(app, request_id, stage=s),
    )
    parent_kwargs = dict(
        rr_degraded=rr_degraded,
        rr_degradation_reason=rr_degradation_reason,
        parent_model=settings.get("heavy_parent_model"),
        parent_max_tokens=settings.get("heavy_parent_max_tokens"),
        parent_payload_max_chars=settings.get("heavy_parent_payload_max_chars"),
        parent_thinking_enabled=get_bool(settings, "heavy_parent_thinking_enabled", False),
        parent_thinking_budget=get_int(settings, "heavy_parent_thinking_budget", 0),
        parent_timeout_s=parent_timeout_s,
        log=LOG,
        on_stage=lambda s: _patch_request(app, request_id, stage=s),
    )
    try:
        fragments, per_subagent, fanout_usage, subagents_ok = run_fanout_only(
            intake, preflight_data, rr_baseline_for_synth, **fanout_kwargs,
        )
    except Exception as e:
        _patch_request(app, request_id, status="failed",
                       error_message=f"heavy fanout failed: {str(e)[:500]}")
        raise _BlockingError(f"heavy fanout failed: {e}")

    subagents_total = 4
    fanout_tokens_in = int(fanout_usage.get("input", 0) or 0)
    fanout_tokens_out = int(fanout_usage.get("output", 0) or 0)

    # ── CHECKPOINT ──────────────────────────────────────────────────────────
    # The fan-out is the expensive asset. Persist it the instant the barrier
    # completes — BEFORE the kill-prone parent/render tail — so a 900s Job kill
    # can never waste these tokens. Record spend immediately too (previously
    # tokens only landed at the rendering stage and were lost on an early kill).
    checkpoint.write_fanout(app, request_id, {
        "schema": 1,
        "request_id": str(request_id),
        "intake": intake,
        "user_id": user_id,
        "preflight_data": preflight_data,
        "rr_baseline_for_synth": rr_baseline_for_synth,
        "rr_degraded": rr_degraded,
        "rr_degradation_reason": rr_degradation_reason,
        "rr_call_count": rr_call_count,
        "fragments": fragments,
        "fanout_usage": fanout_usage,
        "per_subagent": per_subagent,
        "subagents_ok": subagents_ok,
        "subagents_total": subagents_total,
    })
    _patch_request(app, request_id,
                   tokens_input=fanout_tokens_in, tokens_output=fanout_tokens_out,
                   rr_calls=rr_call_count,
                   checkpoint_ready=True, resume_target=RESUME_TARGET)
    LOG.info("checkpoint written; fanout %d/%d ok; fanout tokens=%s/%s",
             subagents_ok, subagents_total, fanout_tokens_in, fanout_tokens_out)

    # ── TIME-BUDGET GUARD ─────────────────────────────────────────────────────
    # If the fan-out ran long, don't risk the parent + render getting killed at
    # 900s. Hand parent synthesis to a fresh resume Job (which loads the
    # checkpoint — zero re-spent tokens) and return cleanly.
    elapsed = time.monotonic() - job_start
    if auto_resume and elapsed > deadline_s:
        LOG.warning("fanout took %.0fs (> deadline %ds) — deferring parent to a resume job",
                    elapsed, deadline_s)
        _patch_request(app, request_id, stage="awaiting_synthesis")
        if not _dispatch_resume(app, request_id, settings, reason="deadline"):
            LOG.error("deferral dispatch failed for request_id=%s; relying on Node sweep", request_id)
        return

    # ── AUTO-GATE: monolithic vs sharded (no settings needed) ──────────────────
    use_sharded = _should_shard(
        settings, elapsed_s=time.monotonic() - job_start,
        render_reserve_s=render_timeout, lint_retry_max=lint_retry_max,
    )

    # ── SHARDED budget guard (waste-free deferral) ─────────────────────────────
    # Sharded synthesis (spine + parallel shards + narrative) needs more wall-clock
    # than it can be allowed to consume in-process near the end of a job. If the
    # remaining job budget can't safely hold it, defer to a fresh resume job NOW —
    # BEFORE spending any synthesis tokens — rather than starting and being killed
    # mid-shard (which would waste the spine/shard tokens). The resume job runs the
    # shards in a fresh 900s budget. With a fast fan-out there's ample budget and
    # this guard does not fire (single-job completion).
    if use_sharded and auto_resume:
        remaining = 900 - (time.monotonic() - job_start) - render_timeout - 30
        shard_timeout = get_int(settings, "heavy_shard_timeout_s", 300)
        sharded_need = shard_timeout + 240  # parallel shards + serial spine+narrative
        if remaining < sharded_need:
            LOG.warning("sharded synthesis needs ~%ds but only ~%ds remain — deferring to "
                        "resume (waste-free, no synthesis tokens spent)", sharded_need, int(remaining))
            _patch_request(app, request_id, stage="awaiting_synthesis")
            if not _dispatch_resume(app, request_id, settings, reason="sharded_budget"):
                LOG.error("sharded-budget dispatch failed for request_id=%s; relying on Node sweep", request_id)
            return

    # ── parent synthesis (in-process) ─────────────────────────────────────────
    try:
        dossier_dict, parent_usage = _synthesize(
            fragments, intake, preflight_data, rr_baseline_for_synth,
            settings=settings, parent_kwargs=parent_kwargs, use_sharded=use_sharded,
        )
    except ParentSynthesisTimeout:
        # Checkpoint already durable → defer to a resume job (degraded parent).
        LOG.warning("parent synthesis timed out — deferring to resume job")
        _patch_request(app, request_id, stage="awaiting_synthesis")
        if not _dispatch_resume(app, request_id, settings, reason="parent_timeout"):
            LOG.error("parent-timeout dispatch failed for request_id=%s; relying on Node sweep", request_id)
        return
    except Exception as e:
        _patch_request(app, request_id, status="failed",
                       error_message=f"heavy parent synthesis failed: {str(e)[:500]}")
        raise _BlockingError(f"heavy parent synthesis failed: {e}")

    # Persist the parent dossier BEFORE render so a render/upload failure (or a
    # late kill) never re-spends the parent tokens — a resume reads this and
    # skips synthesis entirely.
    total_usage = merge_usage(fanout_usage, parent_usage)
    checkpoint.write_parent(app, request_id, {
        "schema": 1,
        "dossier": dossier_dict,
        "parent_usage": parent_usage,
        "total_usage": total_usage,
    })

    # Lint retry regenerates ONLY the parent (or the full shard set when sharding
    # is on) from the cached fragments — never re-runs the (expensive) fan-out.
    def _regenerate_parent():
        return _synthesize(
            fragments, intake, preflight_data, rr_baseline_for_synth,
            settings=settings, parent_kwargs=parent_kwargs, use_sharded=use_sharded,
        )

    _finalize(
        app, request_id,
        settings=settings,
        dossier_dict=dossier_dict,
        regenerate_parent=_regenerate_parent,
        intake=intake, user_id=user_id,
        rr_degraded=rr_degraded, rr_degradation_reason=rr_degradation_reason,
        rr_call_count=rr_call_count,
        subagents_ok=subagents_ok, subagents_total=subagents_total,
        tokens_in=int(total_usage.get("input", 0) or 0),
        tokens_out=int(total_usage.get("output", 0) or 0),
        render_timeout=render_timeout, lint_retry_max=lint_retry_max,
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


def _finalize(app, request_id, *, settings, dossier_dict, regenerate_parent,
              intake, user_id, rr_degraded, rr_degradation_reason,
              rr_call_count, subagents_ok, subagents_total,
              tokens_in, tokens_out, render_timeout, lint_retry_max):
    """Shared tail: render → lint(+retry) → upload → terminal → checkpoint
    cleanup. Used by both the in-job path and the resume path. The lint retry
    regenerates ONLY the parent (regenerate_parent closure), never the fan-out.
    """
    fanout_partial = subagents_ok < subagents_total

    def _stamp_meta(d):
        # Renderer reads meta.rr_degraded to force the illustrative scatter +
        # footnote when an exact timeline can't be derived.
        m = d.get("meta")
        d["meta"] = ({**m, "rr_degraded": rr_degraded}
                     if isinstance(m, dict) else {"rr_degraded": rr_degraded})

    _stamp_meta(dossier_dict)

    # ---- rendering ---------------------------------------------------------
    _patch_request(app, request_id, stage="rendering",
                   tokens_input=tokens_in, tokens_output=tokens_out,
                   rr_calls=rr_call_count)
    html_path, _json_path = _render(dossier_dict, request_id, render_timeout)
    html = Path(html_path).read_text(encoding="utf-8")

    # ---- lint (retry on blocking, up to heavy_lint_retry_max; parent-only) -
    _patch_request(app, request_id, stage="lint")
    lint_result = depth_lint(
        html, (dossier_dict.get("scoring") or {}).get("tier"), rr_degraded=rr_degraded,
    )
    LOG.info("depth_lint: %s", lint_result)
    retries_done = 0
    while lint_result["blocking"] and retries_done < lint_retry_max:
        retries_done += 1
        LOG.warning("blocking lint hits — regenerating parent (%d/%d): %s",
                    retries_done, lint_retry_max, lint_result["hits"])
        _patch_request(app, request_id, stage="synthesis_retry")
        try:
            dossier_dict, usage2 = regenerate_parent()
        except Exception as e:
            _patch_request(app, request_id, status="failed",
                           error_message=f"parent retry failed: {str(e)[:500]}")
            raise _BlockingError(f"parent retry failed: {e}")
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
        _patch_request(app, request_id, stage="lint")
        lint_result = depth_lint(
            html, (dossier_dict.get("scoring") or {}).get("tier"), rr_degraded=rr_degraded,
        )

    # ---- upload ------------------------------------------------------------
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

    # Terminal: partial on any HARD lint hit (missing section / zero sources) at
    # any tier, RR degradation, a missing fan-out subagent, or SOFT cell-level
    # hits beyond the tier-aware tolerance (HOT/WARM strict; COLD/COOL tolerate
    # sparse data) — same partial-status semantics the UI already understands.
    tier = (dossier_dict.get("scoring") or {}).get("tier")
    is_partial = bool(
        lint_result["hard_total"] > 0
        or rr_degraded
        or fanout_partial
        or _soft_hits_exceed_tolerance(
            lint_result, settings, tier, "heavy_lint_soft_tolerance")
    )
    terminal_status = "partial" if is_partial else "succeeded"
    _patch_request(app, request_id,
                   status=terminal_status, stage="done",
                   lead_id=str(result["id"]))
    # Success → drop the checkpoint (best-effort; left on failure for resume).
    checkpoint.cleanup(app, request_id)

    LOG.info(
        "heavy pipeline complete: request_id=%s lead_id=%s status=%s "
        "tokens=%s/%s rr_calls=%s subagents=%s/%s",
        request_id, result["id"], terminal_status,
        tokens_in, tokens_out, rr_call_count, subagents_ok, subagents_total,
    )

    for p in (html_path,):
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:
            pass


def _run_resume(app, request_id, reason):
    """Finish a request from its Stratus checkpoint — no fan-out re-run, so no
    research tokens are re-spent. Runs parent synthesis (unless a parent
    checkpoint already exists) → render → lint → upload.
    """
    settings = load_settings(app)
    render_timeout = get_int(settings, "heavy_render_timeout_s", 180)
    lint_retry_max = get_int(settings, "heavy_lint_retry_max", 0)
    # A resume job runs ONLY parent synthesis + render in a fresh 900s budget,
    # so the parent can use nearly the whole ceiling (render is typically ~10s).
    # Floor it high so a dense HOT-lead parent — which on slower accounts can run
    # 600-750s — completes in this resume instead of timing out into another one.
    # If the parent completes (it returns the moment it's done), render has the
    # remaining budget; only a genuine 780s overrun forfeits render (→ clean
    # retry/fail, never a truncated dossier).
    parent_timeout_s = max(get_int(settings, "heavy_parent_timeout_s", 240), 780)

    _patch_request(app, request_id, status="running", stage="resuming")

    cp = checkpoint.read_fanout(app, request_id)
    if not cp:
        _patch_request(app, request_id, status="failed", stage="error",
                       error_message="resume requested but no fan-out checkpoint found")
        raise _BlockingError("no fanout checkpoint to resume from")

    intake = cp.get("intake") or {}
    user_id = cp.get("user_id")
    preflight_data = cp.get("preflight_data") or {}
    rr_baseline_for_synth = cp.get("rr_baseline_for_synth")
    rr_degraded = bool(cp.get("rr_degraded"))
    rr_degradation_reason = cp.get("rr_degradation_reason")
    rr_call_count = int(cp.get("rr_call_count") or 0)
    fragments = cp.get("fragments") or {}
    fanout_usage = cp.get("fanout_usage") or {}
    subagents_ok = int(cp.get("subagents_ok") or len(fragments))
    subagents_total = int(cp.get("subagents_total") or 4)

    if not user_id:
        _patch_request(app, request_id, status="failed", stage="error",
                       error_message="checkpoint missing user_id")
        raise _BlockingError("checkpoint missing user_id")

    # A timeout-triggered resume runs the parent DEGRADED (thinking off) if the
    # super-admin allows — likelier to finish than re-timeout. A sweep-driven
    # resume (reason="sweep") that is already the 2nd+ attempt degrades too: the
    # row only reaches a later attempt because earlier ones timed out, so treat
    # it the same as an explicit parent_timeout. (First resume stays full-quality.)
    _attempts_so_far = _get_resume_attempts(app, request_id)
    degrade = get_bool(settings, "heavy_resume_parent_degraded", True) and (
        reason == "parent_timeout" or _attempts_so_far >= 2
    )

    parent_kwargs = dict(
        rr_degraded=rr_degraded,
        rr_degradation_reason=rr_degradation_reason,
        parent_model=settings.get("heavy_parent_model"),
        parent_max_tokens=settings.get("heavy_parent_max_tokens"),
        parent_payload_max_chars=settings.get("heavy_parent_payload_max_chars"),
        parent_thinking_enabled=get_bool(settings, "heavy_parent_thinking_enabled", False),
        parent_thinking_budget=get_int(settings, "heavy_parent_thinking_budget", 0),
        parent_timeout_s=parent_timeout_s,
        log=LOG,
        on_stage=lambda s: _patch_request(app, request_id, stage=s),
    )

    # A resume runs in a fresh 900s budget. The auto-gate (elapsed≈0) naturally
    # picks sharded for a rich dossier on a slow account — which is exactly the
    # case that triggered the resume — while a fast account stays monolithic.
    # Computed unconditionally so the lint-retry closure always has it bound.
    use_sharded = _should_shard(
        settings, elapsed_s=0, render_reserve_s=render_timeout, lint_retry_max=lint_retry_max,
    )

    # If a prior resume already produced the parent dossier (then died in
    # render/upload), reuse it — never re-spend parent tokens.
    parent_cp = checkpoint.read_parent(app, request_id)
    if parent_cp and isinstance(parent_cp.get("dossier"), dict):
        LOG.info("resume: parent checkpoint exists — skipping synthesis entirely")
        dossier_dict = parent_cp["dossier"]
        total_usage = parent_cp.get("total_usage") or merge_usage(fanout_usage, parent_cp.get("parent_usage"))
    else:
        LOG.info("resume: loaded fan-out checkpoint (%d fragments) — running synthesis only "
                 "(sharded=%s)", len(fragments), use_sharded)
        try:
            dossier_dict, parent_usage = _synthesize(
                fragments, intake, preflight_data, rr_baseline_for_synth,
                settings=settings, parent_kwargs=parent_kwargs, use_sharded=use_sharded, degraded=degrade,
            )
        except ParentSynthesisTimeout:
            # BACKOFF: do NOT immediately self-redispatch. Immediate redispatch
            # clusters every attempt into the same slow window — the exact failure
            # mode that exhausts the cap during a sustained API-degradation spell.
            # Instead leave the row running with its durable checkpoint; the
            # time-gated Node stale-sweep (STALE_AFTER_MS = 15 min, triggered by the
            # inbox poll on GET /dossiers/generate) re-dispatches it, spacing each
            # retry >=15 min apart so a later attempt can land in a recovered window.
            # The fast first recovery already happened (parent job -> resume #1
            # immediately); only these re-timeouts back off. Zero research tokens are
            # re-spent on resume regardless, so spacing costs nothing.
            LOG.warning("parent synthesis timed out on resume — deferring to the 15-min "
                        "stale-sweep for backoff-spaced retry (no immediate redispatch)")
            _patch_request(app, request_id, stage="awaiting_synthesis")
            return
        except Exception as e:
            _patch_request(app, request_id, status="failed",
                           error_message=f"resume parent synthesis failed: {str(e)[:500]}")
            raise _BlockingError(f"resume parent synthesis failed: {e}")
        total_usage = merge_usage(fanout_usage, parent_usage)
        checkpoint.write_parent(app, request_id, {
            "schema": 1, "dossier": dossier_dict,
            "parent_usage": parent_usage, "total_usage": total_usage,
        })

    def _regenerate_parent():
        return _synthesize(
            fragments, intake, preflight_data, rr_baseline_for_synth,
            settings=settings, parent_kwargs=parent_kwargs, use_sharded=use_sharded, degraded=degrade,
        )

    _finalize(
        app, request_id,
        settings=settings,
        dossier_dict=dossier_dict,
        regenerate_parent=_regenerate_parent,
        intake=intake, user_id=user_id,
        rr_degraded=rr_degraded, rr_degradation_reason=rr_degradation_reason,
        rr_call_count=rr_call_count,
        subagents_ok=subagents_ok, subagents_total=subagents_total,
        tokens_in=int(total_usage.get("input", 0) or 0),
        tokens_out=int(total_usage.get("output", 0) or 0),
        render_timeout=render_timeout, lint_retry_max=lint_retry_max,
    )
