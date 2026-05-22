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

from lib.db import catalyst_datetime, select_one  # noqa: E402
from lib.depth_lint import depth_lint  # noqa: E402
from lib.fanout import run_heavy_synthesis  # noqa: E402
from lib.store_lead import store_lead  # noqa: E402


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

    LOG.info("starting heavy pipeline for request_id=%s", request_id)
    try:
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


def _render(dossier_dict, request_id):
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
        timeout=180,
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


def _run_pipeline(app, request_id):
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
            domain, company=company_guess, timeout=10, log=sys.stderr,
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
        client = RocketReachClient()
        rr_baseline = client.run_baseline_enrichment(
            domain=domain,
            company_name=company_guess,
            contact_name=intake.get("name"),
            contact_linkedin=intake.get("linkedin_url"),
            contact_email=intake.get("email"),
            max_bulk_profiles=20,
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
    try:
        dossier_dict, usage, fanout_meta = run_heavy_synthesis(
            intake, preflight_data, rr_baseline_for_synth,
            rr_degraded=rr_degraded,
            rr_degradation_reason=rr_degradation_reason,
            log=LOG,
            # Each subagent caps at 600s of wall time, plus parent synthesis;
            # patch heartbeat-only stage flip mid-way so the poller doesn't
            # think we stalled.
            on_stage=lambda s: _patch_request(app, request_id, stage=s),
        )
    except Exception as e:
        _patch_request(app, request_id, status="failed",
                       error_message=f"heavy synthesis failed: {str(e)[:500]}")
        raise _BlockingError(f"heavy synthesis failed: {e}")

    tokens_in = int(usage.get("input", 0) or 0)
    tokens_out = int(usage.get("output", 0) or 0)
    subagents_ok = fanout_meta.get("subagents_ok", 0)
    subagents_total = fanout_meta.get("subagents_total", 4)
    fanout_partial = subagents_ok < subagents_total

    # ---- rendering ---------------------------------------------------------
    _patch_request(app, request_id, stage="rendering",
                   tokens_input=tokens_in, tokens_output=tokens_out,
                   rr_calls=rr_call_count)
    html_path, json_path = _render(dossier_dict, request_id)
    html = Path(html_path).read_text(encoding="utf-8")

    # ---- lint --------------------------------------------------------------
    _patch_request(app, request_id, stage="lint")
    tier = (dossier_dict.get("scoring") or {}).get("tier")
    lint_result = depth_lint(html, tier, rr_degraded=rr_degraded)
    LOG.info("depth_lint: %s", lint_result)
    # Heavy run does NOT retry on lint — the fan-out already invested the
    # token budget; a second pass would push past the 15-min Job cap. Any
    # blocking lint hits surface as partial status (renderer's empty-state
    # markers still produce a viewable dossier, just lower density).

    # ---- upload ------------------------------------------------------------
    _patch_request(app, request_id, stage="upload")
    company_name = ((dossier_dict.get("company") or {}).get("name") or "Unknown")
    last_name = ((intake.get("name") or "").strip().split(" ") or ["Lead"])[-1]
    date_str = time.strftime("%Y-%m-%d")
    filename = f"ELISS_{_slug(company_name)}_{_slug(last_name)}_{date_str}.html"

    try:
        result = store_lead(app, user_id, filename, html, dossier_dict)
    except Exception as e:
        _patch_request(app, request_id, status="failed",
                       error_message=f"store_lead failed: {str(e)[:500]}")
        raise _BlockingError(f"store_lead failed: {e}")

    # Terminal: partial when ANY of {lint hit, fanout subagent missing,
    # rr coverage gap} — same partial-status semantics the UI already
    # understands; no schema change needed.
    is_partial = bool(lint_result["hits"] or rr_degraded or fanout_partial)
    terminal_status = "partial" if is_partial else "succeeded"
    _patch_request(app, request_id,
                   status=terminal_status,
                   stage="done",
                   lead_id=str(result["id"]))

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
