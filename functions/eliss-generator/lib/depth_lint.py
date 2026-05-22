"""Render-verification gate — scan rendered HTML for empty-state literals.

Implements feedback_eliss_render_verification_gate.md, but split into HARD
vs SOFT classes so we don't pay a 12-min synthesis retry on a single empty
table cell.

  - HARD hits = section-level failures the model can clearly fix on retry:
    missing executive brief, no applicable compliance frameworks. Any HARD
    hit on a HOT/WARM lead → blocking, regenerate once.

  - SOFT hits = isolated empty cells (an "Unknown" in one field, an em-dash
    in a heatmap cell, a "None detected" pill on one signal). These mean
    the model couldn't fully resolve a specific value, not that the section
    is missing. Surface as warnings → request gets `partial` status, but
    no retry. The 12-min synthesis cost wasn't shifting the needle here.
"""
import re

# Section-level failures — the model can re-generate these with a second
# pass. Each hit type uniquely identifies a whole section that came back empty.
_HARD_LITERALS = [
    ("no_executive_brief", re.compile(r"No executive brief")),
    ("no_applicable_frameworks", re.compile(r"No applicable frameworks")),
]

# Cell-level/field-level empty states — common when public data is genuinely
# missing for the prospect; retrying doesn't reliably fix them.
_SOFT_LITERALS = [
    ("unknown_field_value", re.compile(r'field-value">Unknown<')),
    ("em_dash_heatmap", re.compile(r">—<")),
    ("none_detected_pill", re.compile(r'class="empty-inline">None detected')),
    ("waterfall_empty", re.compile(r'<div class="waterfall-empty">')),
]


def _scan(html, literals):
    out = []
    total = 0
    for label, pattern in literals:
        matches = pattern.findall(html or "")
        if matches:
            out.append({"literal": label, "count": len(matches)})
            total += len(matches)
    return out, total


def depth_lint(html, tier, *, rr_degraded=False):
    """Score the rendered HTML against the empty-state floor.

    Args:
        rr_degraded: When True, SOFT literal hits are demoted to advisory
            (reported in the result but excluded from `hits` / `soft_total`
            / `blocking` calculations). In OSINT-only mode the firmographic
            cells are EXPECTED to be empty — counting them as defects
            produces a misleading lint summary and could trigger spurious
            synthesis retries. HARD literals (missing exec brief, missing
            frameworks) still fire — those are content failures unrelated
            to RR coverage.

    Returns:
        {
            "blocking": bool,    # True if HOT/WARM AND a HARD literal hit
            "partial":  bool,    # True if any hit (soft OR hard) and not blocking
            "hits": [{"literal": str, "count": int, "severity": "hard"|"soft"}],
            "hard_total": int,
            "soft_total": int,
            "soft_total_suppressed": int,  # soft hits hidden by rr_degraded
            "tier_treated_as_blocking": bool,
            "rr_degraded": bool,
        }
    """
    hard_hits, hard_total = _scan(html, _HARD_LITERALS)
    soft_hits, soft_total = _scan(html, _SOFT_LITERALS)

    tier_upper = (tier or "").upper()
    treat_as_blocking = tier_upper in ("HOT", "WARM")

    if rr_degraded:
        soft_total_reported = 0
        soft_total_suppressed = soft_total
        soft_hits_reported = []
    else:
        soft_total_reported = soft_total
        soft_total_suppressed = 0
        soft_hits_reported = soft_hits

    blocking = bool(hard_hits) and treat_as_blocking
    any_hit = bool(hard_hits or soft_hits_reported)
    partial = any_hit and not blocking

    hits = [{**h, "severity": "hard"} for h in hard_hits] + [
        {**h, "severity": "soft"} for h in soft_hits_reported
    ]

    return {
        "blocking": blocking,
        "partial": partial,
        "hits": hits,
        "hard_total": hard_total,
        "soft_total": soft_total_reported,
        "soft_total_suppressed": soft_total_suppressed,
        "total_hits": hard_total + soft_total_reported,
        "tier_treated_as_blocking": treat_as_blocking,
        "rr_degraded": rr_degraded,
    }
