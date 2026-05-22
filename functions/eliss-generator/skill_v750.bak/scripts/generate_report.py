#!/usr/bin/env python3
"""
ELISS Report Generator — Produces professional HTML/PDF intelligence reports from JSON dossier data.

The canonical version is the `ELISS_VERSION` constant below (and the top-level
`VERSION` file). Do NOT hardcode version strings elsewhere in this file; the
v6.2.3 bug was exactly that.

Usage:
    python generate_report.py <dossier.json> [--output-dir <dir>]
                                             [--format html|pdf|both]
                                             [--log <leads_log.json>]
                                             [--validate-only]
                                             [--no-enrich] [--save-enriched]

Flags:
    --format           Which artifact(s) to render. Default: both.
    --log              Path to leads_log.json — enables peer-benchmark bar.
    --validate-only    Schema-check the JSON and exit 0 on pass, non-zero on
                       fail. No HTML/PDF is written. (v6.2.5+)
    --no-enrich        Skip RocketReach enrichment even if RR_API_KEY is set.
    --save-enriched    Also write <base>.enriched.json alongside HTML/PDF.
"""

import argparse
import json
import math
import os
import re
import sys
import textwrap
from datetime import datetime
from pathlib import Path

# Single source of truth for the ELISS version. Update this one line, and the
# value flows to: HTML footer banner, default for meta.version when JSON omits
# it, and the inline analyst tag rewriter that backfills outdated dossier
# version stamps. Never hardcode the version string anywhere else in this file.
ELISS_VERSION = '7.5.3'

# User-facing display version — major.minor only, no patch digit. Shown in
# Tab 1 header brand-mark, Tab 2 analyst tag, and the footer. The canonical
# three-part ELISS_VERSION stays the source-of-truth for tooling (tests,
# bump script, pyproject metadata); only the rendered HTML surface uses
# this shortened form. Derived, not hardcoded, so a `bump_version.py` run
# propagates automatically to the display.
ELISS_DISPLAY_VERSION = '.'.join(ELISS_VERSION.split('.')[:2])


TIER_CONFIG = {
    'HOT':  {'color': '#ef4444', 'bg': 'rgba(239,68,68,0.12)', 'gradient': 'linear-gradient(135deg, #ef4444, #dc2626)', 'label': 'PURSUE NOW'},
    'WARM': {'color': '#f59e0b', 'bg': 'rgba(245,158,11,0.12)', 'gradient': 'linear-gradient(135deg, #f59e0b, #d97706)', 'label': 'ACTIVE NURTURE'},
    'COOL': {'color': '#3b82f6', 'bg': 'rgba(59,130,246,0.12)', 'gradient': 'linear-gradient(135deg, #3b82f6, #2563eb)', 'label': 'MONITOR'},
    'COLD': {'color': '#6b7280', 'bg': 'rgba(107,114,128,0.12)', 'gradient': 'linear-gradient(135deg, #6b7280, #4b5563)', 'label': 'LOW PRIORITY'},
}

CONF_CONFIG = {
    'HIGH':   {'color': '#22c55e', 'bg': 'rgba(34,197,94,0.12)'},
    'MEDIUM': {'color': '#f59e0b', 'bg': 'rgba(245,158,11,0.12)'},
    'LOW':    {'color': '#ef4444', 'bg': 'rgba(239,68,68,0.12)'},
}

DIM_COLORS = {
    'fit': '#8b5cf6',
    'intent': '#22c55e',
    'timing': '#f59e0b',
    'budget': '#3b82f6',
}

PRESSURE_COLORS = {
    'HIGH':   '#ef4444',
    'MEDIUM': '#f59e0b',
    'LOW':    '#22c55e',
}


def escape_html(text):
    """Escape HTML special characters."""
    if text is None:
        return ''
    if not isinstance(text, str):
        text = str(text)
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _extract_value(field, default=''):
    """Return a display string from a structured-value dict, a bare string, or None.

    The dossier JSON marks evidence-bearing fields as
    ``{'value': str, 'confidence': str, 'tier': str, 'evidence': str}`` while
    legacy fields are bare strings. Tab 1 f-strings used to call
    ``escape_html(d.get(...))`` which rendered the literal Python dict repr
    when the field was structured. This unwraps both shapes uniformly.
    """
    if field is None:
        return default
    if isinstance(field, dict):
        v = field.get('value')
        return v if isinstance(v, str) and v else default
    if isinstance(field, str):
        return field
    return str(field)


_LEAD_TITLE_PROCESS_NOISE = (
    'verification incomplete',
    'unverified after',
    'after 1 osint angle', 'after 2 osint angles', 'after 3 osint angles',
    'after 4 osint angles', 'after 5 osint angles', 'after 6 osint angles',
    'after 7 osint angles', 'after 8 osint angles', 'after 9 osint angles',
    'unknown — verification', 'unknown - verification',
    'unknown role', 'unknown title', 'role unknown', 'title unknown',
)


def _clean_lead_title(raw_title, placeholder='Title to be confirmed'):
    """v7.5.2 — strip process prose from lead.title before it hits the header.

    The Tab 1 lead-sub line and the Person Profile field-value both render
    ``lead.title`` directly. When verification fails, analysts have written
    things like ``"Unknown — verification incomplete after 4 OSINT angles"``
    into the title field. That prose belongs in ``data_quality.gaps[]``,
    not the dossier header. This guard normalizes the field so the header
    stays clean even when authoring discipline slips.
    """
    if not raw_title:
        return placeholder
    s = str(raw_title).strip()
    if not s:
        return placeholder
    lc = s.lower()
    if lc == 'unknown' or lc.startswith('unknown —') or lc.startswith('unknown -'):
        return placeholder
    if any(marker in lc for marker in _LEAD_TITLE_PROCESS_NOISE):
        return placeholder
    return s


def _resolve_executive_brief(data):
    """Pick the best executive-brief text the dossier can supply.

    The markdown input path (``fallback_from_markdown``) auto-derives a brief
    from ``md_content[:500]`` so the JSON path needs the same symmetry: when
    ``executive_brief`` is empty/missing, fall back to the first paragraph of
    ``full_dossier_markdown``. Without this, JSON-rendered Tab 1 always shows
    "No executive brief provided." even when the full dossier text is rich.
    """
    brief = (data.get('executive_brief') or '').strip()
    if brief:
        return brief
    md = data.get('full_dossier_markdown') or ''
    if not md:
        return 'No executive brief provided.'
    for para in re.split(r'\n\s*\n', md):
        cleaned = para.strip()
        if cleaned and not cleaned.startswith('#') and len(cleaned) > 40:
            return (cleaned[:500] + '...') if len(cleaned) > 500 else cleaned
    return md[:500] + ('...' if len(md) > 500 else '')


# v7.1.3 — RocketReach provenance pill emitter for Tab 1 (raw HTML) render paths.
# Tab 2 uses the ᴿᴿ glyph which inline_md rewrites to this same span; Tab 1
# emits HTML directly so it needs the span inline. The class name + tooltip
# stay in lockstep with inline_md + the .rr-pill CSS rule so both tabs render
# identically.
_RR_PILL_HTML = (
    '<span class="rr-pill" '
    'title="Sourced from RocketReach premium account (Tier-B, verified)"></span>'
)


def _rr_pill(flag):
    """Return the RR provenance pill when `flag` is truthy, else empty string."""
    return _RR_PILL_HTML if flag else ''


def _format_rr_revenue(n):
    """Render a numeric revenue (int/float) returned by RocketReach as a dollar
    string. $25,000,000 → '$25M'. Falls back to the raw value if not numeric.

    v7.1.5 — Round-up promotes the unit so 999_999 → '$1M' (not '$1000K') and
    999_499 → '$999K'. The previous chained ``>= 1_000_000`` thresholds picked
    the bucket *before* rounding, so 999_999 fell into the K branch and
    rounded its quotient (999.999) to 1000 → '$1000K'. The fix is to compute
    each bucket's rounded value first, then check whether that rounded value
    has crossed into the next-larger unit's range.
    """
    if isinstance(n, bool):
        return ''
    if not isinstance(n, (int, float)):
        return ''
    if n <= 0:
        return ''

    if n >= 1_000_000_000:
        return f'${n/1_000_000_000:.1f}B'.replace('.0B', 'B')

    # Pick the bucket on the raw value (no rounding) so that 999_499 stays in
    # the K-bucket (where it correctly rounds to '$999K') and only crosses to
    # the M-bucket if the K-rounded value bumps into the next unit (the
    # 999_999 → '$1M' edge case).
    if n >= 1_000_000:
        return f'${int(round(n/1_000_000))}M'

    rounded_k = int(round(n / 1_000))
    if rounded_k >= 1_000:  # round-up promoted K → M (e.g. 999_999 → $1M)
        return f'${rounded_k // 1_000}M'
    if rounded_k >= 1:
        return f'${rounded_k}K'

    return f'${int(n):,}'


# =============================================================================
#  SVG VISUALIZATION HELPERS
# =============================================================================

def svg_score_gauge(score, max_score=100, size=160, tier='WARM'):
    """
    Circular score gauge — the big number.

    Sizing: uses viewBox + CSS max-width so it scales fluidly with its container
    instead of locking to fixed pixel dimensions (which caused the digits to
    bleed outside the ring on mobile).

    Typography: the score uses dominant-baseline + dy='0.35em' for true vertical
    centering across browsers (the old `cy - 8` magic-number trick broke when the
    SVG was rendered at any size other than 160px). Font weight is 700 (not 800),
    so glyphs like '88' don't optically push past the ring stroke. The font-size
    is computed as a fraction of the viewBox so the number scales with the gauge.
    """
    tc = TIER_CONFIG.get(tier, TIER_CONFIG['WARM'])
    # Use viewBox coordinates internally; the rendered size comes from CSS.
    vb = 160
    cx = cy = vb // 2
    stroke_w = 11
    # Inner radius leaves enough whitespace inside the ring for the number to
    # breathe — 3-digit scores like 100 must still fit comfortably.
    r = (vb // 2) - (stroke_w // 2) - 4
    circumference = 2 * math.pi * r
    pct = min(score / max_score, 1.0) if max_score else 0
    dash = circumference * pct
    gap = circumference - dash

    # Font size scales with the digit count so '100' isn't bigger than '88'
    score_str = str(score)
    if len(score_str) >= 3:
        score_font_size = 36
    else:
        score_font_size = 42

    return f'''<svg viewBox="0 0 {vb} {vb}" xmlns="http://www.w3.org/2000/svg" \
style="display:block;width:100%;height:auto;max-width:{size}px;margin:0 auto" \
role="img" aria-label="Score {score} out of {max_score}">
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#cbd5e1" stroke-width="{stroke_w}"/>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{tc['color']}" stroke-width="{stroke_w}"
    stroke-dasharray="{dash:.1f} {gap:.1f}" stroke-linecap="round"
    transform="rotate(-90 {cx} {cy})"/>
  <text x="{cx}" y="{cy - 6}" text-anchor="middle" dominant-baseline="central" \
fill="{tc['color']}" font-size="{score_font_size}" font-weight="700" \
font-family="Inter,sans-serif" letter-spacing="-1">{score}</text>
  <text x="{cx}" y="{cy + 22}" text-anchor="middle" dominant-baseline="central" \
fill="#94a3b8" font-size="12" font-weight="500" font-family="Inter,sans-serif">/ {max_score}</text>
</svg>'''


def svg_dimension_bar(label, score, max_score, color, confidence='MEDIUM'):
    """Horizontal bar for one dimension — used in the score hero."""
    pct = min(score / max_score, 1.0) * 100 if max_score else 0
    cc = CONF_CONFIG.get(confidence, CONF_CONFIG['MEDIUM'])

    return f'''<div class="dim-row">
  <div class="dim-header">
    <span class="dim-name">{label}</span>
    <span class="dim-score" style="color:{color}">{score}<span class="dim-max">/{max_score}</span></span>
  </div>
  <div class="dim-track">
    <div class="dim-fill" style="width:{pct}%;background:{color}"></div>
  </div>
  <div class="dim-conf" style="color:{cc['color']}">{confidence}</div>
</div>'''


def svg_radar_chart(scoring, size=280):
    """4-axis radar chart showing Fit / Intent / Timing / Budget as a shape.

    ViewBox is deliberately wide (size + 180) so that horizontal axis labels
    ("INTENT", "BUDGET") have generous room to render without clipping at the
    SVG boundary. The radar drawing itself uses a smaller r_max centered within.
    """
    # ViewBox: extra horizontal padding for horizontal axis labels
    label_pad_h = 90  # padding on left and right
    label_pad_v = 30  # padding on top and bottom
    vb_w = size + label_pad_h * 2
    vb_h = size + label_pad_v * 2
    cx = vb_w // 2
    cy = vb_h // 2
    r_max = (size // 2) - 10
    axes = [
        ('FIT',    scoring.get('fit',    {}).get('score', 0), 25, DIM_COLORS['fit']),
        ('INTENT', scoring.get('intent', {}).get('score', 0), 25, DIM_COLORS['intent']),
        ('TIMING', scoring.get('timing', {}).get('score', 0), 30, DIM_COLORS['timing']),
        ('BUDGET', scoring.get('budget', {}).get('score', 0), 20, DIM_COLORS['budget']),
    ]

    n = len(axes)
    points = []
    label_pts = []
    for i, (name, score, max_s, color) in enumerate(axes):
        angle = -math.pi / 2 + (2 * math.pi * i / n)
        pct = min(score / max_s, 1.0) if max_s else 0
        px = cx + math.cos(angle) * r_max * pct
        py = cy + math.sin(angle) * r_max * pct
        points.append((px, py))
        # Labels sit just outside the grid
        offset = 20
        lx = cx + math.cos(angle) * (r_max + offset)
        ly = cy + math.sin(angle) * (r_max + offset)
        label_pts.append((lx, ly, name, color, score, max_s))

    polygon_pts = ' '.join(f'{p[0]:.1f},{p[1]:.1f}' for p in points)

    grid_rings = ''
    for pct in (0.25, 0.5, 0.75, 1.0):
        ring_pts = []
        for i in range(n):
            angle = -math.pi / 2 + (2 * math.pi * i / n)
            rx = cx + math.cos(angle) * r_max * pct
            ry = cy + math.sin(angle) * r_max * pct
            ring_pts.append(f'{rx:.1f},{ry:.1f}')
        grid_rings += f'<polygon points="{" ".join(ring_pts)}" fill="none" stroke="#cbd5e1" stroke-width="1"/>'

    axis_lines = ''
    for i in range(n):
        angle = -math.pi / 2 + (2 * math.pi * i / n)
        ax = cx + math.cos(angle) * r_max
        ay = cy + math.sin(angle) * r_max
        axis_lines += f'<line x1="{cx}" y1="{cy}" x2="{ax:.1f}" y2="{ay:.1f}" stroke="#94a3b8" stroke-width="1"/>'

    labels_svg = ''
    for lx, ly, name, color, score, max_s in label_pts:
        anchor = 'middle' if abs(lx - cx) < 5 else ('start' if lx > cx else 'end')
        labels_svg += (
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" dy="0.35em" '
            f'font-size="12" font-weight="700" fill="{color}" font-family="Inter,sans-serif">'
            f'{name}</text>'
            f'<text x="{lx:.1f}" y="{ly + 15:.1f}" text-anchor="{anchor}" '
            f'font-size="10" fill="#94a3b8" font-family="Inter,sans-serif">'
            f'{score}/{max_s}</text>'
        )

    data_dots = ''
    for (px, py), (_, _, _, color, _, _) in zip(points, label_pts):
        data_dots += f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{color}" stroke="#ffffff" stroke-width="2"/>'

    # Render fluidly: viewBox sets the coordinate system, CSS sets the rendered
    # size. max-width caps it on desktop; on mobile it shrinks to fill the column.
    render_max = size + 80
    return f'''<svg viewBox="0 0 {vb_w} {vb_h}" preserveAspectRatio="xMidYMid meet" \
xmlns="http://www.w3.org/2000/svg" \
style="display:block;width:100%;height:auto;max-width:{render_max}px;margin:0 auto;overflow:visible">
  {grid_rings}
  {axis_lines}
  <polygon points="{polygon_pts}" fill="rgba(99,102,241,0.20)" stroke="#6366f1" stroke-width="2" stroke-linejoin="round"/>
  {data_dots}
  {labels_svg}
</svg>'''


def svg_intent_donut(intent_data, size=200):
    """Donut chart showing the breakdown of Intent points across signal categories."""
    signals = intent_data.get('signals', []) if isinstance(intent_data, dict) else []

    if not signals:
        score = intent_data.get('score', 0) if isinstance(intent_data, dict) else 0
        max_s = 25
        pct = min(score / max_s, 1.0) if max_s else 0
        cx = cy = size // 2
        r = (size // 2) - 20
        circ = 2 * math.pi * r
        dash = circ * pct
        gap = circ - dash
        return f'''<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" \
style="display:block;width:100%;height:auto;max-width:{size}px;margin:0 auto">
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#cbd5e1" stroke-width="14"/>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{DIM_COLORS['intent']}" stroke-width="14"
    stroke-dasharray="{dash:.1f} {gap:.1f}" stroke-linecap="round" transform="rotate(-90 {cx} {cy})"/>
  <text x="{cx}" y="{cy - 4}" text-anchor="middle" dominant-baseline="central" \
fill="{DIM_COLORS['intent']}" font-size="30" font-weight="700" font-family="Inter,sans-serif" letter-spacing="-1">{score}</text>
  <text x="{cx}" y="{cy + 18}" text-anchor="middle" dominant-baseline="central" \
fill="#94a3b8" font-size="10" font-family="Inter,sans-serif">/ {max_s} intent</text>
</svg>'''

    palette = ['#22c55e', '#10b981', '#06b6d4', '#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#ef4444']
    cx = cy = size // 2
    r = (size // 2) - 20
    circ = 2 * math.pi * r
    total = sum(max(s.get('points', 0), 0) for s in signals) or 1

    slices = ''
    offset = 0
    legend_rows = []
    for i, s in enumerate(signals):
        pts = max(s.get('points', 0), 0)
        if pts <= 0:
            continue
        slice_pct = pts / total
        dash = circ * slice_pct
        gap = circ - dash
        color = palette[i % len(palette)]
        slices += (
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="14" '
            f'stroke-dasharray="{dash:.2f} {gap:.2f}" stroke-dashoffset="{-offset:.2f}" '
            f'transform="rotate(-90 {cx} {cy})"/>'
        )
        offset += dash
        legend_rows.append((color, s.get('category', 'Signal'), pts))

    total_score = intent_data.get('score', 0)
    donut_svg = f'''<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" \
style="display:block;width:100%;height:auto;max-width:{size}px;margin:0 auto">
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#cbd5e1" stroke-width="14"/>
  {slices}
  <text x="{cx}" y="{cy - 4}" text-anchor="middle" dominant-baseline="central" \
fill="{DIM_COLORS['intent']}" font-size="30" font-weight="700" font-family="Inter,sans-serif" letter-spacing="-1">{total_score}</text>
  <text x="{cx}" y="{cy + 18}" text-anchor="middle" dominant-baseline="central" \
fill="#94a3b8" font-size="10" font-family="Inter,sans-serif">/ 25 intent</text>
</svg>'''

    legend_html = '<div class="donut-legend">'
    for color, name, pts in legend_rows:
        legend_html += f'<div class="donut-row"><span class="donut-swatch" style="background:{color}"></span><span class="donut-label">{escape_html(name)}</span><span class="donut-val">+{pts}</span></div>'
    legend_html += '</div>'

    return f'<div class="donut-wrap">{donut_svg}{legend_html}</div>'


def svg_signal_timeline(signals_data, width=760, height=220):
    """Timeline plot of buying signals across recent time.

    v6.0: Color-codes dots by `signal_category` (enum) so procurement-cycle
    signals visually distinguish from general hiring/compliance signals.
    Legacy positive/negative coloring is preserved as a fallback when the
    category field is omitted.

    v6.0 categories (and colors):
      - 'procurement_cycle'     → #8b5cf6 purple (RFP/contract/FY-boundary)
      - 'budget_event'          → #06b6d4 cyan (budget passage/amendment)
      - 'audit_finding'         → #f59e0b amber (audit/deadline)
      - 'grant_funding'         → #10b981 emerald (grant award)
      - 'compliance_deadline'   → #ec4899 pink (regulatory deadline)
      - 'vendor_evaluation'     → #a855f7 violet (active bake-off/eval)
      - 'executive_change'      → #0ea5e9 sky (new DMU member arriving)
      - 'mergers_acquisitions'  → #eab308 yellow (M&A integration)
      - 'conference_speaking'   → #14b8a6 teal (speaker slots)
      - 'partnership'           → #d946ef fuchsia (SI/integrator)
      - 'hiring'                → #22c55e green (default positive)
      - 'breach_incident'       → #ef4444 red (incident signals)
      - 'compliance'            → #f97316 orange (general compliance)
      - 'technology_change'     → #3b82f6 blue (tech migration)
      - 'general' / unset       → #22c55e green positive / #ef4444 red risk
    """
    pos = signals_data.get('positive', []) or []
    neg = signals_data.get('negative', []) or []

    # v6.0 category → color mapping. Canonical; kept in sync with CSS legend
    # rendered below the timeline for dark-theme Tab 1 + light-theme print.
    CAT_COLORS = {
        'procurement_cycle':    ('#8b5cf6', 'Procurement cycle'),
        'budget_event':         ('#06b6d4', 'Budget event'),
        'audit_finding':        ('#f59e0b', 'Audit finding'),
        'grant_funding':        ('#10b981', 'Grant funding'),
        'compliance_deadline':  ('#ec4899', 'Compliance deadline'),
        'vendor_evaluation':    ('#a855f7', 'Vendor evaluation'),
        'executive_change':     ('#0ea5e9', 'Executive change'),
        'mergers_acquisitions': ('#eab308', 'M&A integration'),
        'conference_speaking':  ('#14b8a6', 'Conference / speaking'),
        'partnership':          ('#d946ef', 'Partnership / integrator'),
        'hiring':               ('#22c55e', 'Hiring'),
        'breach_incident':      ('#ef4444', 'Breach / incident'),
        'compliance':           ('#f97316', 'Compliance signal'),
        'technology_change':    ('#3b82f6', 'Technology change'),
        'general':              ('#22c55e', 'General positive'),
    }

    all_sigs = []
    for s in pos:
        age = s.get('age_days', 30)
        if not isinstance(age, (int, float)):
            age = 30
        cat = s.get('signal_category', 'general')
        all_sigs.append({
            'age': max(0, min(age, 365)),
            'pts': abs(s.get('points', 1)),
            'label': s.get('signal', s.get('source', 'Signal')),
            'source': s.get('source', ''),
            'sign': 'pos',
            'category': cat,
        })
    for s in neg:
        age = s.get('age_days', 60)
        if not isinstance(age, (int, float)):
            age = 60
        imp = s.get('impact', s.get('points', -10))
        if isinstance(imp, str):
            m = re.search(r'-?\d+', imp)
            imp = int(m.group()) if m else -10
        all_sigs.append({
            'age': max(0, min(age, 365)),
            'pts': abs(imp),
            'label': s.get('flag', s.get('signal', 'Risk')),
            'source': s.get('evidence', s.get('source', '')),
            'sign': 'neg',
            # Negative signals don't get custom category coloring; always red
            'category': s.get('signal_category', 'breach_incident'),
        })

    if not all_sigs:
        return '<div class="timeline-empty">No time-stamped signals available</div>'

    left_pad, right_pad, top_pad, bottom_pad = 50, 30, 24, 40
    plot_w = width - left_pad - right_pad
    plot_h = height - top_pad - bottom_pad

    def x_for_age(age):
        return left_pad + plot_w * (1 - (age / 365))

    gridlines = ''
    for age_mark, lbl in [(7, '7d'), (30, '30d'), (90, '90d'), (180, '180d'), (365, '1yr')]:
        x = x_for_age(age_mark)
        gridlines += (
            f'<line x1="{x:.1f}" y1="{top_pad}" x2="{x:.1f}" y2="{top_pad + plot_h}" stroke="#cbd5e1" stroke-width="1"/>'
            f'<text x="{x:.1f}" y="{top_pad + plot_h + 16}" text-anchor="middle" font-size="10" fill="#94a3b8" font-family="Inter,sans-serif">{lbl}</text>'
        )

    gridlines += f'<text x="{left_pad}" y="{top_pad - 10}" font-size="10" fill="#94a3b8" font-family="Inter,sans-serif" font-weight="600">← newer       SIGNAL FRESHNESS       older →</text>'

    dots = ''
    all_sigs.sort(key=lambda s: s['age'])
    categories_seen = set()
    for i, sig in enumerate(all_sigs):
        x = x_for_age(sig['age'])
        y_offset = (i % 4) * (plot_h / 4) + (plot_h / 8)
        y = top_pad + y_offset if sig['sign'] == 'pos' else top_pad + plot_h - y_offset - 10
        radius = 4 + min(sig['pts'] * 0.8, 14)

        # v6.0: color from category. Negatives override to red regardless of
        # category, since the dominant visual cue for risk flags is still color.
        if sig['sign'] == 'neg':
            color = '#ef4444'
        else:
            color, _ = CAT_COLORS.get(sig['category'], CAT_COLORS['general'])
        categories_seen.add(sig['category'] if sig['sign'] == 'pos' else 'risk_flag')

        # v6.1: Tooltip text — word-aware shortening at 90 chars (was hard
        # 40-char slice that cut mid-word and let HTML entities like &amp;
        # bleed into the visible string). 90 chars renders comfortably on
        # any platform's hover tooltip; textwrap.shorten breaks on word
        # boundaries and appends an ellipsis only when actually truncated.
        raw_label = sig['label'] if sig['label'] else 'Signal'
        label = textwrap.shorten(raw_label, width=90, placeholder='…')
        cat_label = CAT_COLORS.get(sig['category'], CAT_COLORS['general'])[1]
        title = f'{label} — {cat_label} ({sig["pts"]} pts, {sig["age"]}d)'
        dots += (
            f'<g class="tl-dot"><title>{escape_html(title)}</title>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{color}" opacity="0.25"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius * 0.45:.1f}" fill="{color}"/>'
            f'</g>'
        )

    # v6.0 dynamic legend — shows only the categories actually present in this
    # signal set to avoid visual clutter. Renders below the SVG as HTML so wrap
    # and multi-line layout work naturally.
    legend_items = []
    # Order: put procurement-cycle categories first (they're the v6.0 highlight),
    # then trigger events, then ambient categories. v6.1: 'breach_incident'
    # added — was previously plotted on the chart (red dot) but missing from
    # this list, so the legend chip never appeared and red dots were unexplained.
    order = [
        'procurement_cycle', 'budget_event', 'audit_finding', 'grant_funding',
        'compliance_deadline', 'vendor_evaluation', 'executive_change',
        'mergers_acquisitions', 'conference_speaking', 'partnership',
        'breach_incident', 'hiring', 'compliance', 'technology_change', 'general',
    ]
    for cat in order:
        if cat in categories_seen:
            color, label = CAT_COLORS[cat]
            legend_items.append(
                f'<span class="tl-legend-item">'
                f'<span class="tl-legend-dot" style="background:{color}"></span>'
                f'<span class="tl-legend-label">{escape_html(label)}</span>'
                f'</span>'
            )
    if 'risk_flag' in categories_seen:
        legend_items.append(
            '<span class="tl-legend-item">'
            '<span class="tl-legend-dot" style="background:#ef4444"></span>'
            '<span class="tl-legend-label">Risk flag</span>'
            '</span>'
        )
    legend_html = f'<div class="tl-legend">{"".join(legend_items)}</div>' if legend_items else ''

    return f'''<div class="signal-timeline-wrap"><svg width="100%" viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet" style="max-width:100%;display:block">
  {gridlines}
  {dots}
</svg>{legend_html}</div>'''


def svg_source_quality_donut(sources, size=220):
    """
    v5.7: Source Quality Donut — Tier A / B / C distribution across all cited sources.

    This is an instant-credibility check: a dossier built predominantly on Tier-C
    (aggregator/inferred) sources caps at MEDIUM confidence per SKILL.md rules. A
    dossier rich in Tier-A (authoritative — gov filings, company press releases,
    SEC filings) is fundamentally more trustworthy. The donut visualizes that
    balance at a glance.

    Accepts the v5.6+ `{url, tier}` dict format AND the legacy flat-URL-array form
    (legacy entries are counted as Tier-C since their reliability wasn't declared).
    Also accepts a dict-of-lists (per-category sources) or a flat list.
    """
    # Flatten: sources may be a dict keyed by category (person/company/technology...)
    # with values being lists of {url, tier} dicts OR flat URL strings.
    all_entries = []
    if isinstance(sources, dict):
        for entries in sources.values():
            if isinstance(entries, list):
                all_entries.extend(entries)
    elif isinstance(sources, list):
        all_entries.extend(sources)

    counts = {'A': 0, 'B': 0, 'C': 0}
    for e in all_entries:
        if isinstance(e, dict):
            tier = str(e.get('tier', 'C')).upper()
            if tier not in counts:
                tier = 'C'
            counts[tier] += 1
        else:
            # Legacy flat-URL string — tier wasn't declared, count as C
            counts['C'] += 1

    total = counts['A'] + counts['B'] + counts['C']

    # Empty state — no sources cited
    if total == 0:
        return ('<div class="source-donut-empty">'
                '<p class="empty">No sources cited. '
                'Re-run the analyst step to populate source attribution.</p>'
                '</div>')

    # Geometry
    vb = size
    cx = cy = vb // 2
    r_outer = (vb // 2) - 16
    stroke_w = 26
    r = r_outer - (stroke_w // 2)
    circumference = 2 * math.pi * r

    tier_colors = {
        'A': {'color': '#22c55e', 'label': 'Tier A — Authoritative'},
        'B': {'color': '#f59e0b', 'label': 'Tier B — Reputable secondary'},
        'C': {'color': '#9ca3af', 'label': 'Tier C — Aggregator / inferred'},
    }

    # Build arcs in order A → B → C
    arcs = []
    rotate_start = -90  # Start at 12 o'clock
    for tier in ('A', 'B', 'C'):
        n = counts[tier]
        if n == 0:
            continue
        pct = n / total
        arc_len = circumference * pct
        gap = circumference - arc_len
        arcs.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
            f'stroke="{tier_colors[tier]["color"]}" stroke-width="{stroke_w}" '
            f'stroke-dasharray="{arc_len:.2f} {gap:.2f}" '
            f'transform="rotate({rotate_start} {cx} {cy})"/>'
        )
        rotate_start += pct * 360

    # Center text: total count, optionally flagging if A-count is zero
    a_ratio = counts['A'] / total
    if a_ratio >= 0.40:
        center_label_color = '#22c55e'
        center_sublabel = 'STRONG'
    elif a_ratio >= 0.20:
        center_label_color = '#f59e0b'
        center_sublabel = 'MIXED'
    else:
        center_label_color = '#ef4444'
        center_sublabel = 'SOFT'

    center_svg = (
        f'<text x="{cx}" y="{cy - 10}" text-anchor="middle" dominant-baseline="central" '
        f'fill="#1e293b" font-size="28" font-weight="700" font-family="Inter,sans-serif">{total}</text>'
        f'<text x="{cx}" y="{cy + 12}" text-anchor="middle" dominant-baseline="central" '
        f'fill="#94a3b8" font-size="10" font-weight="500" font-family="Inter,sans-serif" '
        f'letter-spacing="1">sources</text>'
        f'<text x="{cx}" y="{cy + 28}" text-anchor="middle" dominant-baseline="central" '
        f'fill="{center_label_color}" font-size="10" font-weight="700" font-family="Inter,sans-serif" '
        f'letter-spacing="1">{center_sublabel}</text>'
    )

    donut_svg = (
        f'<svg viewBox="0 0 {vb} {vb}" xmlns="http://www.w3.org/2000/svg" '
        f'style="display:block;width:100%;height:auto;max-width:{size}px" '
        f'role="img" aria-label="Source quality breakdown: {counts["A"]} Tier A, {counts["B"]} Tier B, {counts["C"]} Tier C">'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#e5e7eb" stroke-width="{stroke_w}"/>'
        f'{"".join(arcs)}'
        f'{center_svg}'
        f'</svg>'
    )

    # Legend
    legend_parts = []
    for tier in ('A', 'B', 'C'):
        tc = tier_colors[tier]
        pct = (counts[tier] / total * 100) if total > 0 else 0
        legend_parts.append(
            f'<div class="sq-legend-row">'
            f'<span class="sq-swatch" style="background:{tc["color"]}"></span>'
            f'<span class="sq-legend-label">{escape_html(tc["label"])}</span>'
            f'<span class="sq-legend-count">{counts[tier]} <span class="sq-legend-pct">({pct:.0f}%)</span></span>'
            f'</div>'
        )
    legend_html = f'<div class="sq-legend">{"".join(legend_parts)}</div>'

    # Interpretive caption
    if a_ratio >= 0.40:
        caption = 'Source base is strong — claims rest heavily on authoritative sources.'
    elif a_ratio >= 0.20:
        caption = 'Source base is mixed — claims resting solely on Tier-C aggregators cap at MEDIUM confidence per ELISS scoring rules.'
    else:
        caption = 'Source base is soft — fewer than 20% of sources are Tier-A. Consider gathering additional authoritative sources before high-stakes use.'

    return (
        f'<div class="source-quality-wrap">'
        f'<div class="source-quality-chart">{donut_svg}</div>'
        f'<div class="source-quality-side">'
        f'{legend_html}'
        f'<div class="sq-caption">{escape_html(caption)}</div>'
        f'</div>'
        f'</div>'
    )


def svg_dmu_ghost_map(org_intel, lead=None, size_w=760, size_h=560):
    """
    DMU + Ghost Stakeholder Map — layout matches the operator's preferred
    reference design:

        Top row:    Economic Buyer (left)        Potential Blocker (right)
        Mid row:                    Champion   Primary Contact
        Bottom row: Ghost 1 (left)  Ghost 2 (center)

    Edges:
      * Primary Contact → Champion — horizontal solid (gray)
      * Champion top-left → EB bottom-right — diagonal solid (gray)
      * Each Ghost → Champion bottom — straight dashed (amber)

    Label placement: every node has labels BELOW its circle EXCEPT the
    Champion, whose labels are placed ABOVE the circle. The Champion is the
    only node approached by ghost edges from below; those edges terminate at
    the Champion's bottom (cx, cy+r), so keeping labels below would put them
    directly in the edges' path. Flipping Champion's labels above lifts the
    entire label stack into the otherwise-empty space between the Champion's
    top and the Economic Buyer row.

    Champion title uses a tighter truncation (20 chars vs the standard 24)
    so the title's left edge stays clear of the diagonal Champion→EB edge,
    which crosses y=117 at x=329 — a standard-width title would extend to
    x≈322 and graze the edge by 7px.

    All label-vs-edge clearances verified mathematically: minimum 11.7px on
    any edge/label pair in this layout.
    """
    economic_buyer = org_intel.get('economic_buyer', {}) or {}
    technical_eval = org_intel.get('technical_evaluator', {}) or {}
    champion = org_intel.get('champion', {}) or {}
    blocker = org_intel.get('blocker', {}) or {}
    ghosts = org_intel.get('future_stakeholders', []) or []
    # v6.2.1 — additional named stakeholders that don't fit the EB/Champion/
    # Tech-Eval/Blocker quartet. Most common roles: 'Influencer', 'Sponsor',
    # 'EB-delegated' (deputy who actually controls budget), 'User Champion'.
    # First entry renders at top-center between EB and Blocker as a violet node.
    # Schema: [{role, name, title, relevance?}]
    additional_stakeholders = org_intel.get('additional_stakeholders', []) or []
    contact_name = (lead or {}).get('name', '') if lead else ''
    contact_title = (lead or {}).get('title', '') if lead else ''

    def has_person(role):
        n = role.get('name', '') or ''
        return bool(n.strip()) and n.strip().lower() not in ('unknown', '—', '-', 'n/a', 'tbd')

    def truncate(text, max_chars):
        text = (text or '').strip()
        return text if len(text) <= max_chars else text[: max_chars - 1] + '…'

    r_outer = 32

    def render_node(cx, cy, name, title, node_type='solid', color='#3b82f6',
                    sublabel='', labels_position='below', title_max=24):
        """
        Render a DMU node: colored circle + 3-line label stack (name / title /
        sublabel) positioned either above or below the circle.
        """
        name_disp = truncate(name, 20)
        title_disp = truncate(title or '', title_max)
        # Initials: strip any leading non-alphanumeric prefix from each word so
        # parenthesized placeholders like "(Vacant) Information Security
        # Engineer" yield "VI" instead of "(I", and "(Unidentified)
        # Procurement Officer" yields "UP" instead of "(P".
        parts = []
        for word in (name_disp or '?').split():
            cleaned = re.sub(r'^[^A-Za-z0-9]+', '', word)
            if cleaned:
                parts.append(cleaned)
        initials = ''.join(p[0].upper() for p in parts[:2]) if parts else '?'

        if node_type == 'dashed':
            stroke_dash = ' stroke-dasharray="4,3"'
            fill_opacity = '0.08'
            stroke_width = 2
        elif node_type == 'primary':
            stroke_dash = ''
            fill_opacity = '0.15'
            stroke_width = 3
        else:
            stroke_dash = ''
            fill_opacity = '0.12'
            stroke_width = 2

        # Label stack: name furthest, sublabel closest to circle — reading
        # order top→bottom is preserved whether placed above or below.
        if labels_position == 'above':
            y_name = cy - r_outer - 40       # furthest (top of stack)
            y_title = cy - r_outer - 26
            y_sublabel = cy - r_outer - 12   # closest to circle (bottom of stack)
        else:
            y_name = cy + r_outer + 16       # closest to circle (top of stack)
            y_title = cy + r_outer + 30
            y_sublabel = cy + r_outer + 44   # furthest (bottom of stack)

        return (
            f'<g class="dmu-node">'
            f'<circle cx="{cx}" cy="{cy}" r="{r_outer}" '
            f'stroke="{color}" stroke-width="{stroke_width}"{stroke_dash} '
            f'fill="{color}" fill-opacity="{fill_opacity}"/>'
            f'<text x="{cx}" y="{cy + 1}" text-anchor="middle" '
            f'dominant-baseline="central" fill="{color}" font-size="15" '
            f'font-weight="700" font-family="Inter,sans-serif">'
            f'{escape_html(initials)}</text>'
            f'<text class="dmu-name" x="{cx}" y="{y_name}" text-anchor="middle" '
            f'font-size="11" font-weight="600" font-family="Inter,sans-serif">'
            f'{escape_html(name_disp)}</text>'
            f'<text class="dmu-title" x="{cx}" y="{y_title}" text-anchor="middle" '
            f'font-size="9" font-family="Inter,sans-serif">'
            f'{escape_html(title_disp)}</text>'
            f'<text x="{cx}" y="{y_sublabel}" text-anchor="middle" fill="{color}" '
            f'font-size="9" font-weight="700" letter-spacing="0.6" '
            f'font-family="Inter,sans-serif">{escape_html(sublabel)}</text>'
            f'</g>'
        )

    nodes_svg = []
    edges_svg = []

    # v6.2.3 — REDESIGNED LAYOUT for visual balance and zero label overlap.
    #
    # Previous layout (v6.2.2) packed 5 columns into 760px (col centers at 120,
    # 260, 400, 540, 680 — only 140px apart) which left labels touching at
    # narrow viewports and looked cramped. New layout uses a clean 3-column
    # grid evenly spaced at 200px intervals, plus two flanking columns for the
    # Tech-Eval/Primary-Contact (offset right) and the Blocker/EB asymmetry
    # case. Vertical: 4 visual bands (top / mid / bottom / ghost-labels) with
    # generous ~140px row pitch so label stacks (~50px tall) never get within
    # 70px of the next row's stack.
    #
    #   top   y= 80   ┌─ EB ──────── INF ──────── BL ─┐    (3 nodes evenly spaced)
    #   mid   y=290   │       CHAMP ── TECHEVAL       │    (2 nodes, center + right)
    #   ghost y=470   │   GHOST     GHOST     GHOST   │    (up to 3 ghosts evenly spaced)
    #
    # Column centers (200px pitch): left=180, center=380, right=580
    # Plus right-offset for Tech Eval at 540, and far-right safety at 640.
    # Total horizontal span: 160-660 (centered in 760 viewBox with 50px gutters).
    #
    # Vertical math (v7.1.4 — pitched widened from 170/155 to 210/180 px):
    #   - Top labels-below: ends at y =  80+76 = 156
    #   - Mid labels-above (Champion): starts at y = 290-72 = 218 → 62px gap ✓✓
    #   - Mid labels-below (Tech Eval): ends at y = 290+76 = 366
    #   - Ghost circle top edge: 470-32 = 438 → 72px circle-to-label gap ✓✓
    #   - Ghost labels-below: ends at y = 470+76 = 546 (within new viewBox h=560)
    col_x = {'left': 180, 'center': 380, 'right': 580, 'far_right': 640}
    # v7.1.4 — Row pitch widened from 170/155 to 210/195 px to remove the
    # cramped 10–22 px effective gap between adjacent label stacks. Each row's
    # 3-line label block is ~50 px tall (font-size 11 + 9 + 9 with 14 px line
    # height), so a 60 px clear band between stacks reads as breathing room
    # rather than near-collision. viewBox height grew 490 → 560 to match.
    row_y = {'top': 80, 'mid': 290, 'bottom': 470}

    has_eb = has_person(economic_buyer)
    has_ch = has_person(champion)
    has_bl = has_person(blocker)
    tech_is_contact = (contact_name and technical_eval.get('name', '').strip() == contact_name.strip())
    has_contact_or_tech = has_person(technical_eval) or bool(contact_name)

    # ---- Edges rendered FIRST so nodes draw on top of them ------------------

    # Primary Contact → Champion (horizontal solid)
    if has_ch and has_contact_or_tech:
        edges_svg.append(
            f'<line x1="{col_x["right"] - r_outer}" y1="{row_y["mid"]}" '
            f'x2="{col_x["center"] + r_outer}" y2="{row_y["mid"]}" '
            f'stroke="#94a3b8" stroke-width="1.5"/>'
        )

    # Champion ↔ Economic Buyer — single diagonal solid line from Champion's
    # top-left perimeter to EB's bottom-right perimeter, used regardless of
    # Influencer presence.
    #
    # v7.1.5 — Removed the Influencer-routing branch. The previous routing
    # (horizontal EB→Influencer + vertical Influencer→Champion) drew a
    # vertical line at x=col_x['center'] from y=row_y['top']+r_outer down to
    # y=row_y['mid']-r_outer that passed STRAIGHT THROUGH the Influencer
    # node's own labels (positioned below its circle at the same x). Visually
    # the line punched through the Influencer's name, title, and role pill.
    #
    # The diagonal does NOT cross any Influencer text: it goes from EB's
    # bottom-right (~x=202, y=102) to Champion's top-left (~x=358, y=267),
    # so at the height where Influencer labels sit (y≈124–162, centered on
    # x=col_x['center']=380), the diagonal is at x≈250–290 — well left of
    # the centered Influencer label bbox (x≈320–440). The Influencer node
    # remains visually present at top-center but is not connected by an
    # explicit edge; its EB-delegated relationship is conveyed by proximity
    # plus its own role label.
    if has_ch and has_eb:
        edges_svg.append(
            f'<line x1="{col_x["center"] - 22}" y1="{row_y["mid"] - 22}" '
            f'x2="{col_x["left"] + 22}" y2="{row_y["top"] + 22}" '
            f'stroke="#94a3b8" stroke-width="1.5"/>'
        )

    # Ghost positions (matching reference HTML exactly): col_x['left'], col_x['center'], col_x['right']
    ghost_positions = [col_x['left'], col_x['center'], col_x['right']]

    # Ghosts → Champion (dashed amber). v6.1.2 geometry — both endpoints on
    # respective peripheries, just like the gray solid lines above.
    #
    # Previously (v6.1) the line ORIGINATED at the ghost circle's CENTER and
    # passed through the ghost's interior. Even with the ghost circle painted
    # on top (fill-opacity 0.08) the dashed line was visibly traceable through
    # the circle, breaking the "neat, edge-to-edge" look that the gray solid
    # Primary→Champion and Champion→EB lines have. Same fix applied to both
    # endpoints now: walk r_outer pixels along the connecting vector from
    # each circle's center, so the line's two endpoints sit precisely on the
    # respective peripheries on the side facing the other circle.
    #
    # Each ghost still hits the champion at a UNIQUE perimeter point (because
    # the angle of approach differs per ghost), preserving the v6.1 fix that
    # eliminated the "all lines stacking on one pixel" issue.
    if has_ch and ghosts:
        cx_ch, cy_ch = col_x["center"], row_y["mid"]
        for idx in range(min(len(ghosts), 3)):
            gx = ghost_positions[idx] if idx < len(ghost_positions) else col_x['far_right']
            gy = row_y['bottom']
            dx, dy = cx_ch - gx, cy_ch - gy
            d = (dx * dx + dy * dy) ** 0.5
            if d < 2 * r_outer:
                # Circles overlap (or are exactly touching); no meaningful edge.
                continue
            ux, uy = dx / d, dy / d                  # unit vector ghost → champion
            sx = gx + ux * r_outer                   # ghost-side perimeter point
            sy = gy + uy * r_outer
            ex = cx_ch - ux * r_outer                # champion-side perimeter point
            ey = cy_ch - uy * r_outer
            edges_svg.append(
                f'<line x1="{sx:.2f}" y1="{sy:.2f}" '
                f'x2="{ex:.2f}" y2="{ey:.2f}" '
                f'stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4,3"/>'
            )

    # ---- Nodes --------------------------------------------------------------

    if has_eb:
        nodes_svg.append(render_node(
            col_x['left'], row_y['top'],
            economic_buyer.get('name', ''), economic_buyer.get('title', ''),
            node_type='solid', color='#3b82f6', sublabel='ECONOMIC BUYER',
            labels_position='below'
        ))

    if has_ch:
        # KEY: labels ABOVE to clear the ghost-edge corridor below the circle.
        # Title truncated to 20 chars (vs 24 default) to stay clear of the
        # diagonal Champion→EB edge at the title row.
        nodes_svg.append(render_node(
            col_x['center'], row_y['mid'],
            champion.get('name', ''), champion.get('title', ''),
            node_type='solid', color='#22c55e', sublabel='CHAMPION',
            labels_position='above', title_max=20
        ))

    if has_person(technical_eval):
        node_type = 'primary' if tech_is_contact else 'solid'
        color = '#8b5cf6' if tech_is_contact else '#06b6d4'
        sublabel = 'PRIMARY CONTACT' if tech_is_contact else 'TECHNICAL EVALUATOR'
        nodes_svg.append(render_node(
            col_x['right'], row_y['mid'],
            technical_eval.get('name', ''), technical_eval.get('title', ''),
            node_type=node_type, color=color, sublabel=sublabel,
            labels_position='below'
        ))
    elif contact_name:
        nodes_svg.append(render_node(
            col_x['right'], row_y['mid'],
            contact_name, contact_title,
            node_type='primary', color='#8b5cf6', sublabel='PRIMARY CONTACT',
            labels_position='below'
        ))

    if has_bl:
        nodes_svg.append(render_node(
            col_x['right'], row_y['top'],
            blocker.get('name', ''), blocker.get('title', ''),
            node_type='solid', color='#ef4444', sublabel='POTENTIAL BLOCKER',
            labels_position='below'
        ))

    # v6.2.1 — Additional stakeholders. First named entry renders at top-center
    # between EB (top-left) and Blocker (top-right). Color: violet (#a855f7) to
    # differentiate from the four primary slot colors. We render at most one in
    # the visualization to avoid overcrowding; the markdown ORGANIZATIONAL
    # INTELLIGENCE table is the authoritative full list.
    has_additional = False
    additional_role_label = ''
    if additional_stakeholders:
        first = additional_stakeholders[0] or {}
        if has_person(first):
            has_additional = True
            additional_role_label = (first.get('role', 'INFLUENCER') or 'INFLUENCER').upper()
            nodes_svg.append(render_node(
                col_x['center'], row_y['top'],
                first.get('name', ''), first.get('title', ''),
                node_type='solid', color='#a855f7', sublabel=additional_role_label,
                labels_position='below'
            ))

    for idx, g in enumerate(ghosts[:3]):
        gx = ghost_positions[idx] if idx < len(ghost_positions) else col_x['far_right']
        # v7.1.4 — Truncate arrival to keep the GHOST · ETA sublabel visually
        # bounded. Some dossiers carry full sentences in `estimated_arrival`
        # (e.g. "Unlikely FY26 given budget contraction; plausible FY27 if a
        # second incident occurs or insurer/state pressure mounts" — 127
        # chars), which SVG <text> renders as one un-wrapped line that
        # overflows the viewBox horizontally and visually collides with
        # neighboring nodes' labels. Cap at 22 chars so the full sublabel
        # ("GHOST · ETA " + arrival = ~34 chars) fits inside one node's
        # visual lane.
        arrival = truncate(g.get('estimated_arrival', '?'), 22)
        role_title = g.get('role', '')
        sublabel = f'GHOST · ETA {arrival}'
        nodes_svg.append(render_node(
            gx, row_y['bottom'],
            role_title or 'Open Role', g.get('status', ''),
            node_type='dashed', color='#f59e0b', sublabel=sublabel,
            labels_position='below'
        ))

    if not nodes_svg:
        return ('<div class="dmu-map-empty">'
                '<p class="empty">No DMU data provided. Populate '
                'org_intelligence.{economic_buyer, champion, technical_evaluator} '
                'to visualize the decision-making unit.</p>'
                '</div>')

    # ---- Legend -------------------------------------------------------------
    legend_items = []
    if has_eb:
        legend_items.append('<span class="dmu-legend-item"><span class="dmu-swatch" style="background:#3b82f6"></span>Economic Buyer</span>')
    if has_ch:
        legend_items.append('<span class="dmu-legend-item"><span class="dmu-swatch" style="background:#22c55e"></span>Champion</span>')
    if has_contact_or_tech:
        if tech_is_contact or not has_person(technical_eval):
            legend_items.append('<span class="dmu-legend-item"><span class="dmu-swatch" style="background:#8b5cf6"></span>Primary Contact</span>')
        else:
            legend_items.append('<span class="dmu-legend-item"><span class="dmu-swatch" style="background:#06b6d4"></span>Technical Evaluator</span>')
    if has_bl:
        legend_items.append('<span class="dmu-legend-item"><span class="dmu-swatch" style="background:#ef4444"></span>Potential Blocker</span>')
    if has_additional:
        # Title-case the role (was uppercased for the SVG sublabel)
        legend_label = additional_role_label.title() if additional_role_label else 'Influencer'
        legend_items.append(f'<span class="dmu-legend-item"><span class="dmu-swatch" style="background:#a855f7"></span>{escape_html(legend_label)}</span>')
    if ghosts:
        legend_items.append('<span class="dmu-legend-item"><span class="dmu-swatch" style="background:#f59e0b;border:2px dashed #f59e0b"></span>Ghost Stakeholder (open req)</span>')

    legend_html = f'<div class="dmu-legend">{"".join(legend_items)}</div>'

    return (
        f'<div class="dmu-map-wrap">'
        f'<svg viewBox="0 0 {size_w} {size_h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="display:block;width:100%;height:auto;max-width:{size_w}px" '
        f'role="img" aria-label="Decision-making unit and ghost stakeholder map">'
        f'{"".join(edges_svg)}'
        f'{"".join(nodes_svg)}'
        f'</svg>'
        f'{legend_html}'
        f'</div>'
    )

def build_compliance_heatmap(compliance_list):
    """Compliance framework heatmap (HTML/CSS, not SVG)."""
    if not compliance_list:
        return '<p class="empty">No applicable frameworks identified</p>'

    rows_html = ''
    for c in compliance_list:
        pressure = str(c.get('pressure', 'LOW')).upper()
        pcolor = PRESSURE_COLORS.get(pressure, '#6b7280')
        # Two key conventions exist in production dossiers: `_fit` (GDPR, DORA,
        # newer playbook) and `_angle` (NYDFS, legacy v6.x). Read both so the
        # heatmap populates regardless of which the analyst (or upstream
        # markdown) used.
        ad_angle = escape_html(c.get('ad360_fit') or c.get('ad360_angle') or '—')
        log_angle = escape_html(c.get('log360_fit') or c.get('log360_angle') or '—')
        urgency = escape_html(c.get('urgency', '—'))
        fw = escape_html(c.get('framework', ''))

        rows_html += f'''<div class="heatmap-row">
  <div class="heatmap-framework">
    <div class="heatmap-name">{fw}</div>
    <div class="heatmap-urgency">{urgency}</div>
  </div>
  <div class="heatmap-pressure" style="background:{pcolor}20;color:{pcolor};border:1px solid {pcolor}40">
    <span class="heatmap-dot" style="background:{pcolor}"></span>{pressure}
  </div>
  <div class="heatmap-cell heatmap-ad">
    <div class="heatmap-cell-label">AD360</div>
    <div class="heatmap-cell-text">{ad_angle}</div>
  </div>
  <div class="heatmap-cell heatmap-log">
    <div class="heatmap-cell-label">Log360</div>
    <div class="heatmap-cell-text">{log_angle}</div>
  </div>
</div>'''

    return f'<div class="heatmap">{rows_html}</div>'


def svg_budget_waterfall(budget, width=760, height=220, company=None):
    """
    Waterfall: Revenue -> IT budget -> Security budget -> Deal size.

    The parser must be careful — budget fields often contain prose like:
      "$2.5M-$4.0M annually (ESTIMATED)"        (range — use midpoint)
      "12-20% of IT"                            (percent string — NOT a dollar)
      "284 employees x $8K/emp = $2.3M IT"      (multiple numbers — need $ prefix)
    Revenue can also live in company.revenue_estimate or company.revenue.
    `calculation_basis` is prose and MUST NOT be treated as a dollar source.
    """

    def parse_money(s):
        """Parse a dollar string → float. Handles ranges ($2M-$4M), suffixes (K/M/B),
        and ignores non-dollar numbers by requiring the $ prefix. Returns None if no
        valid dollar amount is found. For ranges, returns the midpoint.

        v7.1.3 — also accepts raw numeric input (int/float). RocketReach's
        `/company/lookup` returns `revenue` as an integer (e.g. 25000000); the
        prior string-only guard silently dropped it, wasting an enrichment
        credit. bool is rejected explicitly — True/False aren't dollar amounts.
        """
        if isinstance(s, bool):
            return None
        if isinstance(s, (int, float)):
            return float(s) if s > 0 else None
        if not s or not isinstance(s, str):
            return None
        cleaned = s.replace(',', '').replace('–', '-').replace('—', '-')
        # Find ALL $-prefixed amounts (with optional K/M/B suffix).
        # Requiring the $ prefix is what prevents us from eating '284 employees'
        # or '12% of IT' as if they were dollar values.
        matches = re.findall(r'\$\s*([\d.]+)\s*([KMB]?)', cleaned, re.IGNORECASE)
        if not matches:
            return None
        values = []
        mults = {'K': 1e3, 'M': 1e6, 'B': 1e9, '': 1}
        for num_str, suf in matches:
            try:
                val = float(num_str)
                values.append(val * mults[suf.upper()])
            except (ValueError, KeyError):
                continue
        if not values:
            return None
        # If multiple $ amounts found in one field (e.g. a range "$2M-$4M"), use the
        # midpoint of min and max. This is more honest than picking the first number.
        return (min(values) + max(values)) / 2

    def first_valid(*candidates):
        for c in candidates:
            v = parse_money(c)
            if v is not None and v > 0:
                return v
        return None

    company = company or {}

    # --- Revenue: check multiple possible sources in order of reliability ---
    # 1. budget.estimated_revenue (explicit)
    # 2. company.revenue_estimate / company.revenue (often populated for public entities)
    # 3. company.operating_budget (municipal / non-profit context — closest analogue to revenue)
    # We intentionally do NOT fall back to calculation_basis — that's prose with
    # multiple numbers and was the source of the "$284 Revenue" bug.
    revenue = first_valid(
        budget.get('estimated_revenue'),
        company.get('revenue_estimate'),
        company.get('revenue'),
        company.get('operating_budget'),
        budget.get('revenue'),
    )

    it_spend = parse_money(budget.get('estimated_it_spend'))
    sec_spend = parse_money(budget.get('security_budget'))
    # v5.2: No silent fallback. If estimated_deal_size is missing, we render the
    # waterfall without the deal row and emit a visible warning. The old `or 40000`
    # default produced misleading charts at both ends of the prospect spectrum
    # (looked like a rounding error on enterprise budgets, plausible-but-fabricated
    # on small budgets). See references/dossier-template.md Deal Sizing Rubric.
    deal_size = parse_money(budget.get('estimated_deal_size'))

    # --- Sanity check: revenue must be >= IT spend (IT is a subset of revenue).
    # If violated, something was mis-parsed upstream; drop the revenue row rather
    # than render a misleading "IT is 880,000% of revenue" chart.
    if revenue and it_spend and revenue < it_spend:
        revenue = None

    if not (it_spend or sec_spend):
        return '<div class="waterfall-empty">Budget data not sufficient to render waterfall — see IT Budget section above</div>'

    stages = []
    if revenue:
        stages.append(('Revenue', revenue, '#64748b'))
    if it_spend:
        stages.append(('IT Budget', it_spend, '#3b82f6'))
    if sec_spend:
        stages.append(('Security Budget', sec_spend, '#8b5cf6'))
    if sec_spend:
        stages.append(('IAM and IGA', sec_spend * 0.12, '#22c55e'))
        stages.append(('SIEM', sec_spend * 0.15, '#14b8a6'))

    def fmt_money(v):
        if v >= 1e9:
            return f'${v/1e9:.1f}B'
        if v >= 1e6:
            return f'${v/1e6:.0f}M'
        if v >= 1e3:
            return f'${v/1e3:.0f}K'
        return f'${v:.0f}'

    def fmt_pct(pct):
        """Format a percentage for display. Clamps/flags nonsense values."""
        if pct <= 0:
            return ''
        if pct >= 1000:
            # Something is still wrong if we hit this — don't show a nonsense label.
            return ''
        if pct >= 100:
            return f'{pct:.0f}%'
        if pct >= 10:
            return f'{pct:.0f}%'
        if pct >= 1:
            return f'{pct:.1f}%'
        return f'{pct:.2f}%'

    max_val = max(s[1] for s in stages)
    min_val = min(s[1] for s in stages)

    def log_scale(v):
        if min_val <= 0 or max_val <= 0 or min_val == max_val:
            return v / max_val if max_val else 0
        return (math.log10(v) - math.log10(min_val * 0.5)) / (math.log10(max_val) - math.log10(min_val * 0.5))

    left_pad = 170  # Wider so "AD360+Log360 Deal" fits without clipping
    right_pad = 100
    bar_max = width - left_pad - right_pad
    row_h = (height - 30) / len(stages)

    svg_rows = ''
    for i, (label, val, color) in enumerate(stages):
        y = 20 + i * row_h
        bar_w = max(bar_max * log_scale(val), 40)
        pct_note = ''
        if i > 0 and stages[i-1][1]:
            # IAM/IGA and SIEM are both sub-budgets of Security Budget,
            # so they should both show "X% of Security Budget" — not
            # SIEM showing "125% of IAM and IGA" (which is meaningless).
            if label in ('IAM and IGA', 'SIEM'):
                # Find the Security Budget stage to reference
                sec_stage = next((s for s in stages if s[0] == 'Security Budget'), None)
                if sec_stage and sec_stage[1]:
                    pct = (val / sec_stage[1]) * 100
                    pct_str = fmt_pct(pct)
                    if pct_str:
                        pct_note = f'{pct_str} of {sec_stage[0]}'
            else:
                pct = (val / stages[i-1][1]) * 100
                pct_str = fmt_pct(pct)
                if pct_str:
                    pct_note = f'{pct_str} of {stages[i-1][0]}'

        # Label on left, bar in middle, money on right
        svg_rows += f'''
  <text x="{left_pad - 10}" y="{y + row_h/2 + 5}" text-anchor="end" font-size="12" font-weight="600" fill="#475569" font-family="Inter,sans-serif">{escape_html(label)}</text>
  <rect x="{left_pad}" y="{y + row_h/2 - 14}" width="{bar_w:.1f}" height="28" rx="4" fill="{color}" opacity="0.85"/>
  <text x="{left_pad + bar_w + 8}" y="{y + row_h/2 + 5}" font-size="13" font-weight="700" fill="{color}" font-family="Inter,sans-serif">{fmt_money(val)}</text>'''
        # Only render pct_note if the bar is wide enough (>100) so it doesn't clip
        if pct_note and bar_w > 100:
            svg_rows += f'''
  <text x="{left_pad + 8}" y="{y + row_h/2 + 5}" font-size="10" fill="#ffffff" font-weight="600" font-family="Inter,sans-serif">{escape_html(pct_note)}</text>'''
        elif pct_note:
            # For tiny bars, put the note to the right of the money label
            svg_rows += f'''
  <text x="{left_pad + bar_w + 8 + 50}" y="{y + row_h/2 + 18}" font-size="9" fill="#94a3b8" font-style="italic" font-family="Inter,sans-serif">{escape_html(pct_note)}</text>'''

    svg = f'''<svg width="100%" viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet" style="max-width:100%">
  {svg_rows}
</svg>'''

    # v5.2: If deal size was missing, emit a loud warning alongside the chart so
    # the reader knows the 4th bar is absent by design, not by accident.
    if not deal_size:
        warning = (
            '<div class="waterfall-warning">'
            '⚠ <strong>Deal size not specified.</strong> '
            'The dossier JSON is missing <code>estimated_deal_size</code> in '
            '<code>budget_analysis</code> — the AD360+Log360 Deal bar was intentionally '
            'omitted rather than fabricated. Apply the Deal Sizing Rubric in '
            '<code>references/dossier-template.md</code> and regenerate the report.'
            '</div>'
        )
        return warning + svg
    return svg


def svg_dmu_orgchart(org, width=760, height=380):
    """
    Decision-making unit visualization — 4 role cards connected to a central hub.

    Design choices:
      - Four quadrants, symmetric around the hub. Width is split 50/50 with equal gutters.
      - Cards use a subtle color-tinted fill (~12% alpha) with a coloured left border bar
        instead of full-colour backgrounds — this keeps the name readable on BOTH dark
        and light page backgrounds without needing a separate print remap.
      - Role label uses the role colour. Name uses high-contrast cream (dark theme) which
        is remapped by the print CSS to dark slate.
      - Long names/titles wrap across two lines instead of being hard-truncated mid-word.
      - Connection lines go from the inner edge of each card to the hub edge, not centre-
        to-centre, so they don't visually cross the card interior.
    """
    roles = [
        ('Economic Buyer',      org.get('economic_buyer', {}),       '#ef4444', 'Controls budget'),
        ('Champion',            org.get('champion', {}),             '#22c55e', 'Feels the pain'),
        ('Technical Evaluator', org.get('technical_evaluator', {}),  '#3b82f6', 'Runs POC'),
        ('Potential Blocker',   org.get('blocker', {}),              '#f59e0b', 'May resist'),
    ]

    # Layout geometry
    pad_x = 32
    gutter = 64                          # horizontal gap between left and right columns
    node_w = (width - 2 * pad_x - gutter) // 2
    node_h = 128                         # tall enough for 2-line name + 3-line title + sub
    row_gap = 36
    cx, cy = width // 2, height // 2

    # Quadrant positions: top-left, top-right, bottom-left, bottom-right
    top_y = cy - node_h - row_gap // 2
    bot_y = cy + row_gap // 2
    left_x = pad_x
    right_x = width - pad_x - node_w
    positions = [
        (left_x,  top_y),   # Economic Buyer  (TL)
        (right_x, top_y),   # Champion         (TR)
        (left_x,  bot_y),   # Technical Eval   (BL)
        (right_x, bot_y),   # Potential Blocker (BR)
    ]

    def wrap_text(text, max_chars, max_lines=2):
        """Split text into up to max_lines lines on word boundaries; ellipsize overflow."""
        if not text:
            return ['']
        if len(text) <= max_chars:
            return [text]
        words = text.split(' ')
        lines_out = ['']
        for w in words:
            # Try to fit on current line
            candidate = (lines_out[-1] + ' ' + w).strip() if lines_out[-1] else w
            if len(candidate) <= max_chars:
                lines_out[-1] = candidate
            else:
                if len(lines_out) < max_lines:
                    lines_out.append(w)
                else:
                    # Out of lines — ellipsize the last line
                    tail = lines_out[-1]
                    if len(tail) + 2 <= max_chars:
                        lines_out[-1] = tail + '…'
                    else:
                        lines_out[-1] = tail[:max_chars - 1] + '…'
                    break
        return [ln for ln in lines_out if ln]

    nodes = ''
    lines = ''
    for (role_label, person, color, sub), (x, y) in zip(roles, positions):
        if isinstance(person, dict):
            name = (person.get('name') or 'Unknown').strip()
            title = (person.get('title') or '').strip()
        else:
            name = 'Unknown'
            title = ''

        is_unknown = not name or name.lower() == 'unknown'

        # Connection line: from inner edge of card to hub edge
        is_left_col = x < cx
        card_edge_x = x + node_w if is_left_col else x
        card_edge_y = y + node_h // 2
        # Shorten line to not touch the hub (r=30)
        dx, dy = cx - card_edge_x, cy - card_edge_y
        dist = max((dx * dx + dy * dy) ** 0.5, 1)
        hub_r = 30
        hub_edge_x = cx - (dx / dist) * hub_r
        hub_edge_y = cy - (dy / dist) * hub_r
        lines += (
            f'<line x1="{card_edge_x}" y1="{card_edge_y}" '
            f'x2="{hub_edge_x:.1f}" y2="{hub_edge_y:.1f}" '
            f'stroke="{color}" stroke-opacity="0.35" stroke-width="1.5" stroke-dasharray="4 4"/>'
        )

        # Card styling — subtle tint + coloured left border bar
        card_fill = f'{color}1A'  # ~10% alpha — works on dark and light pages
        card_stroke = f'{color}66' if not is_unknown else '#cbd5e180'
        name_lines = wrap_text(name, 22, max_lines=2)
        title_lines = wrap_text(title, 30, max_lines=3)

        # Card shape
        nodes += (
            f'\n  <rect x="{x}" y="{y}" width="{node_w}" height="{node_h}" rx="12" '
            f'fill="{card_fill}" stroke="{card_stroke}" stroke-width="1.5"/>'
        )
        # Coloured accent bar on the left edge
        nodes += (
            f'\n  <rect x="{x}" y="{y}" width="4" height="{node_h}" rx="2" fill="{color}"/>'
        )

        # Role label (color-matched, all-caps)
        nodes += (
            f'\n  <text x="{x + 16}" y="{y + 22}" font-size="9.5" font-weight="700" '
            f'fill="{color}" font-family="Inter,sans-serif" letter-spacing="1">'
            f'{escape_html(role_label.upper())}</text>'
        )

        # Name — up to 2 wrapped lines. Use cream/slate that remaps well for print.
        name_y = y + 44
        for i, nl in enumerate(name_lines[:2]):
            nodes += (
                f'\n  <text x="{x + 16}" y="{name_y + i * 17}" font-size="14" '
                f'font-weight="700" fill="#e2e8f0" font-family="Inter,sans-serif">'
                f'{escape_html(nl)}</text>'
            )

        # Title — start below the name block, up to 3 wrapped lines
        title_start_y = name_y + len(name_lines[:2]) * 17 + 2
        for i, tl in enumerate(title_lines[:3]):
            nodes += (
                f'\n  <text x="{x + 16}" y="{title_start_y + i * 13}" font-size="11" '
                f'fill="#94a3b8" font-family="Inter,sans-serif">'
                f'{escape_html(tl)}</text>'
            )

        # Sub-label (italic, bottom)
        nodes += (
            f'\n  <text x="{x + 16}" y="{y + node_h - 10}" font-size="9.5" '
            f'fill="#94a3b8" font-style="italic" font-family="Inter,sans-serif">'
            f'{escape_html(sub)}</text>'
        )

    # Central hub
    hub = (
        f'\n  <circle cx="{cx}" cy="{cy}" r="30" fill="#0f172a" stroke="#6366f1" stroke-width="2"/>'
        f'\n  <circle cx="{cx}" cy="{cy}" r="22" fill="none" stroke="#6366f1" stroke-width="1" stroke-opacity="0.35"/>'
        f'\n  <text x="{cx}" y="{cy - 2}" text-anchor="middle" font-size="11" font-weight="700" '
        f'fill="#818cf8" font-family="Inter,sans-serif" letter-spacing="1.5">DMU</text>'
        f'\n  <text x="{cx}" y="{cy + 12}" text-anchor="middle" font-size="8.5" '
        f'fill="#94a3b8" font-family="Inter,sans-serif">Deal Map</text>'
    )

    return (
        f'<svg width="100%" viewBox="0 0 {width} {height}" '
        f'preserveAspectRatio="xMidYMid meet" style="max-width:100%;display:block">'
        f'{lines}{nodes}{hub}\n</svg>'
    )


def svg_peer_benchmark(score, peer_scores, width=700, height=80):
    """Horizontal bar showing where this lead ranks among peers from leads_log.json."""
    if not peer_scores:
        return ''

    below = sum(1 for s in peer_scores if s < score)
    percentile = int((below / len(peer_scores)) * 100) if peer_scores else 0

    buckets = [0, 0, 0, 0]
    for s in peer_scores:
        if s >= 75:
            buckets[3] += 1
        elif s >= 50:
            buckets[2] += 1
        elif s >= 30:
            buckets[1] += 1
        else:
            buckets[0] += 1

    total = len(peer_scores)
    colors = ['#6b7280', '#3b82f6', '#f59e0b', '#ef4444']
    labels = ['COLD', 'COOL', 'WARM', 'HOT']

    bar_h = 24
    bar_y = 28
    bar_w_total = width

    segs = ''
    offset = 0
    for i, (b, color, lbl) in enumerate(zip(buckets, colors, labels)):
        seg_w = (b / total) * bar_w_total if total else 0
        if seg_w > 0:
            segs += f'<rect x="{offset:.1f}" y="{bar_y}" width="{seg_w:.1f}" height="{bar_h}" fill="{color}" opacity="0.7"/>'
            if seg_w > 40:
                segs += f'<text x="{offset + seg_w/2:.1f}" y="{bar_y + 16}" text-anchor="middle" font-size="10" font-weight="700" fill="#fff" font-family="Inter,sans-serif">{lbl} ({b})</text>'
        offset += seg_w

    marker_x = (score / 100) * bar_w_total
    marker = f'''
  <line x1="{marker_x:.1f}" y1="{bar_y - 6}" x2="{marker_x:.1f}" y2="{bar_y + bar_h + 6}" stroke="#0f172a" stroke-width="2.5"/>
  <polygon points="{marker_x-6:.1f},{bar_y - 6} {marker_x+6:.1f},{bar_y - 6} {marker_x:.1f},{bar_y}" fill="#0f172a"/>
  <text x="{marker_x:.1f}" y="{bar_y - 10}" text-anchor="middle" font-size="11" font-weight="700" fill="#0f172a" font-family="Inter,sans-serif">THIS LEAD: {score}</text>'''

    return f'''<svg width="100%" viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet" style="max-width:100%">
  <text x="0" y="14" font-size="11" font-weight="600" fill="#94a3b8" font-family="Inter,sans-serif">
    PIPELINE POSITION — this lead ranks in the {percentile}th percentile of {total} tracked leads
  </text>
  {segs}
  {marker}
</svg>'''


# =============================================================================
#  HTML SECTION BUILDERS
# =============================================================================

def build_verdict_banner(data):
    """5-second verdict banner — shows at top of report.

    Gives a rep scanning 20 dossiers an instant read: Tier + Action + one-sentence
    key insight + contact.
    """
    scoring = data.get('scoring', {})
    recs = data.get('recommendations', {})
    lead = data.get('lead', {})
    company = data.get('company', {})
    tier = scoring.get('tier', 'WARM')
    tc = TIER_CONFIG.get(tier, TIER_CONFIG['WARM'])
    action = recs.get('action', 'MONITOR')
    score = scoring.get('final_score', scoring.get('composite', 0))

    # Pull a one-line insight
    insight = data.get('executive_brief', '')
    if insight:
        # Take the first sentence
        m = re.match(r'(.+?[.!?])\s', insight + ' ')
        insight = m.group(1) if m else insight[:180]
    else:
        insight = 'No executive brief available.'

    outreach = recs.get('outreach', {})
    next_step = ''
    if recs.get('next_steps'):
        next_step = recs['next_steps'][0]
    elif outreach.get('hook'):
        next_step = f"Outreach: {outreach.get('channel', 'Email')} — {outreach.get('hook', '')}"

    return f'''<div class="verdict-banner" style="background:{tc['bg']};border:2px solid {tc['color']}">
  <div class="verdict-tier-pill" style="background:{tc['gradient']}">
    <div class="verdict-score">{score}</div>
    <div class="verdict-tier">{tier}</div>
  </div>
  <div class="verdict-body">
    <div class="verdict-headline">
      <span style="color:{tc['color']};font-weight:800">{action}</span> — {escape_html(lead.get('name', 'Unknown'))} @ {escape_html(company.get('name', 'Unknown'))}
    </div>
    <div class="verdict-insight">{escape_html(insight)}</div>
    {f'<div class="verdict-next">→ {escape_html(next_step)}</div>' if next_step else ''}
  </div>
</div>'''


def build_validation_visual(scoring):
    """Visualize which validation rules fired (caps, decay, triangulation)."""
    val = scoring.get('validation', {})
    neg_mods = scoring.get('negative_modifiers', [])

    rules = []
    if val.get('stale_cap'):
        rules.append(('STALE CAP', 'Data >90d old — score capped at 74', '#f59e0b'))
    if val.get('confidence_cap'):
        rules.append(('LOW CONF CAP', 'Overall confidence LOW — score capped at 74', '#f59e0b'))
    decay_wks = val.get('decay_weeks', 0)
    if val.get('decay_applied') or (isinstance(decay_wks, (int, float)) and decay_wks > 0):
        rules.append(('DECAY', f'Signal age {decay_wks}wk — ×0.95^{decay_wks} decay applied', '#3b82f6'))

    intent = scoring.get('intent', {})
    if isinstance(intent, dict):
        if intent.get('triangulation_applied'):
            rules.append(('TRIANGULATION', 'Intent from single category — ×0.80 penalty', '#8b5cf6'))
        # v6.1: Detect Intent score capping. Two signals can fire:
        #   (a) explicit `raw_total` field set by the analyst (preferred), or
        #   (b) inferred from the signals[] array — if Σ points > score and
        #       score == max, the cap was applied implicitly.
        # Previously this was invisible: a 39-pt raw Intent capped to 25
        # would show "Clean score — no caps applied" on the validation panel
        # while the dossier markdown clearly noted the cap. Inconsistency
        # eroded trust in the panel as a single source of truth.
        score = intent.get('score', 0) or 0
        max_score = intent.get('max', 25) or 25
        raw = intent.get('raw_total')
        if raw is None:
            sigs = intent.get('signals', [])
            if isinstance(sigs, list):
                try:
                    raw = sum(int(s.get('points', 0) or 0) for s in sigs if isinstance(s, dict))
                except (TypeError, ValueError):
                    raw = score
        if isinstance(raw, (int, float)) and raw > score and score >= max_score:
            rules.append((
                'INTENT CAP',
                f'Cap @ {int(max_score)} — raw {int(raw)} pts trimmed to ceiling',
                '#eab308'
            ))

    # Negative modifiers
    for nm in neg_mods:
        if isinstance(nm, str):
            rules.append(('NEG MOD', nm, '#ef4444'))
        elif isinstance(nm, dict):
            # Support all common key names across dossier versions:
            # 'label', 'modifier', 'name', 'signal', 'reason'
            label = (nm.get('label')
                     or nm.get('modifier')
                     or nm.get('name')
                     or nm.get('signal')
                     or nm.get('reason')
                     or 'Unknown modifier')
            impact = nm.get('impact', nm.get('points', ''))
            evidence = nm.get('evidence', '')
            desc = label
            if impact:
                desc += f' ({impact})'
            rules.append(('NEG MOD', desc, '#ef4444'))
        else:
            rules.append(('NEG MOD', str(nm), '#ef4444'))

    # Deal execution risks (separate from structural negative_modifiers per the
    # scoring rubric — risks aggregate into risk_adjusted_composite, modifiers
    # subtract from composite). Without this block the panel rendered "Clean
    # score" while the score had moved by total_risk_adjustment.
    risks = scoring.get('deal_execution_risks', []) or []
    for r in risks:
        if isinstance(r, str):
            rules.append(('RISK ADJ', r, '#f97316'))
        elif isinstance(r, dict):
            label = (r.get('risk')
                     or r.get('label')
                     or r.get('name')
                     or r.get('description')
                     or 'Unknown risk')
            adjustment = r.get('adjustment', r.get('points', r.get('impact', '')))
            desc = label
            if adjustment:
                desc += f' ({adjustment})'
            rules.append(('RISK ADJ', desc, '#f97316'))
        else:
            rules.append(('RISK ADJ', str(r), '#f97316'))

    if not rules:
        return '<div class="validation-clean">✓ Clean score — no caps, decay, or negative modifiers applied</div>'

    rule_html = ''
    for tag, desc, color in rules:
        rule_html += f'''<div class="val-rule" style="border-left:3px solid {color}">
  <span class="val-tag" style="color:{color};background:{color}18">{tag}</span>
  <span class="val-desc">{escape_html(desc)}</span>
</div>'''

    return f'<div class="validation-list">{rule_html}</div>'


# =============================================================================
#  v5.7 EVIDENCE-URL CHIP HELPER
# =============================================================================

def render_evidence_chips(urls, aria_context='evidence'):
    """
    v5.7: Render a list of evidence URLs as inline numbered link chips.

    Usage: appended after escaped evidence/basis text. Returns an empty string
    when urls is None/empty so call sites can compose safely. Each chip links
    target=_blank and carries rel=noopener for safe outbound navigation.

    Example output: ' <span class="evidence-chips"><a class="evidence-chip"
    href="..." target="_blank" rel="noopener">[1]</a><a ...>[2]</a></span>'
    """
    if not urls:
        return ''
    # Accept either a list of strings or a list of {url, label} dicts (future-proofing)
    chips = []
    for i, u in enumerate(urls, 1):
        if isinstance(u, dict):
            href = u.get('url', '')
            label = u.get('label', f'[{i}]')
        else:
            href = str(u)
            label = f'[{i}]'
        if not href:
            continue
        chips.append(
            f'<a class="evidence-chip" href="{escape_html(href)}" '
            f'target="_blank" rel="noopener" '
            f'aria-label="{aria_context} source {i}: {escape_html(href)}" '
            f'title="{escape_html(href)}">{escape_html(label)}</a>'
        )
    if not chips:
        return ''
    return f' <span class="evidence-chips">{"".join(chips)}</span>'


def build_signals_html(signals):
    """Build the buying signals list section (complements the timeline)."""
    html_parts = []
    pos = signals.get('positive', []) or []
    neg = signals.get('negative', []) or []

    if pos:
        html_parts.append('<h3>Positive Signals</h3>')
        for s in pos:
            age = s.get('age_days', '?')
            age_label = f"{age}d ago" if isinstance(age, int) and age < 90 else f"{age}"
            conf = s.get('confidence', 'MEDIUM')
            cc = CONF_CONFIG.get(conf, CONF_CONFIG['MEDIUM'])
            evidence_chips = render_evidence_chips(s.get('evidence_urls'), aria_context='signal')
            html_parts.append(f'''<div class="signal-item signal-positive">
  <div class="signal-main">
    <span class="signal-badge" style="background:{DIM_COLORS['intent']}20;color:{DIM_COLORS['intent']}">+{s.get('points', '?')}</span>
    <span class="signal-text">{escape_html(s.get('signal', ''))}</span>
  </div>
  <div class="signal-meta">
    <span>{escape_html(s.get('source', ''))}{evidence_chips}</span>
    <span class="signal-age">{age_label}</span>
    <span class="conf-tag" style="color:{cc['color']}">{conf}</span>
  </div>
</div>''')

    if neg:
        html_parts.append('<h3>Risk Flags</h3>')
        for s in neg:
            evidence_chips = render_evidence_chips(s.get('evidence_urls'), aria_context='risk flag')
            html_parts.append(f'''<div class="signal-item signal-negative">
  <div class="signal-main">
    <span class="signal-badge" style="background:rgba(239,68,68,0.15);color:#ef4444">{escape_html(str(s.get('impact', '?')))}</span>
    <span class="signal-text">{escape_html(s.get('flag', s.get('signal', '')))}</span>
  </div>
  <div class="signal-meta"><span>{escape_html(s.get('evidence', s.get('source', '')))}{evidence_chips}</span></div>
</div>''')

    net = signals.get('net_assessment', '')
    if net:
        html_parts.append(f'<div class="net-assessment"><strong>Net Assessment:</strong> {escape_html(net)}</div>')

    return '\n'.join(html_parts) if html_parts else '<p class="empty">No signals detected</p>'


def build_recommendations_html(recs, tier):
    """Strategic recommendations section."""
    tc = TIER_CONFIG.get(tier, TIER_CONFIG['WARM'])
    action = recs.get('action', 'MONITOR')

    steps_html = ''
    for i, step in enumerate(recs.get('next_steps', []), 1):
        steps_html += f'<div class="step-item"><span class="step-num">{i}</span><span>{escape_html(step)}</span></div>'

    ad360_html = ''.join(f'<li>{escape_html(p)}</li>' for p in recs.get('ad360_talking_points', []))
    log360_html = ''.join(f'<li>{escape_html(p)}</li>' for p in recs.get('log360_talking_points', []))

    obj_html = ''
    for obj in recs.get('objections', []):
        obj_html += f'''<div class="objection-item">
  <div class="obj-q">"{escape_html(obj.get('objection', ''))}"</div>
  <div class="obj-a">{escape_html(obj.get('response', ''))}</div>
</div>'''

    outreach = recs.get('outreach', {})
    outreach_html = ''
    if outreach:
        outreach_html = f'''<div class="outreach-box">
  <strong>Outreach:</strong> {escape_html(outreach.get('channel', 'Email'))} — {escape_html(outreach.get('timing', ''))}
  <div class="outreach-hook"><em>Hook: {escape_html(outreach.get('hook', ''))}</em></div>
</div>'''

    return f'''
<div class="action-banner" style="background:{tc['bg']};border-left:4px solid {tc['color']}">
  <span class="action-label" style="color:{tc['color']}">{action}</span>
</div>
{steps_html}
<div class="talking-grid">
  <div class="talk-col"><h4>AD360 Talking Points</h4><ul>{ad360_html}</ul></div>
  <div class="talk-col"><h4>Log360 Talking Points</h4><ul>{log360_html}</ul></div>
</div>
{obj_html}
{outreach_html}'''


# =============================================================================
#  v7.2 — Recommended Outreach (Email Sequence)
# =============================================================================

# Voice palette for the email cards. Each voice is the inspiration name (Google
# Cloud / Apple Enterprise / Microsoft Azure enterprise sales styles); the
# rendered badge uses the short label below. Colors picked to be distinct from
# tier/threat palettes already on the Exec Summary tab.
VOICE_CONFIG = {
    'technical':    {'label': 'TECHNICAL',    'color': '#4285f4', 'bg': 'rgba(66,133,244,0.12)',  'desc': 'Technical depth, data-forward'},
    'executive':    {'label': 'EXECUTIVE',    'color': '#a3a3a3', 'bg': 'rgba(163,163,163,0.12)', 'desc': 'Minimal, outcome-first'},
    'consultative': {'label': 'CONSULTATIVE', 'color': '#00a4ef', 'bg': 'rgba(0,164,239,0.12)',   'desc': 'Consultative, governance-led'},
}

# v7.4 — Backward compatibility: pre-rename dossiers used Google/Apple/Microsoft
# as voice keys. Resolve those through this alias map at the lookup site so
# cached/external dossiers continue rendering with the right colour and label.
_LEGACY_VOICE_ALIASES = {'google': 'technical', 'apple': 'executive', 'microsoft': 'consultative'}


def build_recommended_outreach_html(outreach_emails):
    """v7.2: Recommended Outreach — 3 dossier-driven follow-up email cards.

    Expects a list of email dicts:
        {slot:1|2|3, template_id, template_name, voice, subject, body,
         rationale, triggered_by}

    Renders cards with:
      - voice badge (Technical/Executive/Consultative)
      - template name + slot pill
      - subject line (bold)
      - body (preformatted)
      - rationale block ("Why this email for this prospect")
      - copy-to-clipboard button (HTML only — JS no-op in PDF)
    """
    if not outreach_emails:
        return '<p class="empty">No outreach sequence generated for this prospect.</p>'

    cards = []
    for i, email in enumerate(outreach_emails, 1):
        if not isinstance(email, dict):
            continue
        slot = email.get('slot', i)
        voice_key = (email.get('voice') or '').strip().lower()
        voice_key = _LEGACY_VOICE_ALIASES.get(voice_key, voice_key)
        voice = VOICE_CONFIG.get(voice_key, VOICE_CONFIG['consultative'])
        template_name = email.get('template_name') or email.get('template_id') or 'Outreach Email'
        subject = email.get('subject', '')
        body = email.get('body', '')
        rationale = email.get('rationale', '')
        triggered_by = email.get('triggered_by') or []
        triggered_html = ''
        if triggered_by:
            chips = ''.join(
                f'<span class="trig-chip">{escape_html(t)}</span>'
                for t in triggered_by if t
            )
            if chips:
                triggered_html = f'<div class="trig-row">{chips}</div>'

        # Plain-text payload for the copy button (subject + blank line + body).
        copy_payload = f'Subject: {subject}\n\n{body}'
        # JSON-escape for safe embedding inside data-attribute. We render via
        # json.dumps to handle quotes/newlines/unicode, then HTML-escape the
        # surrounding attribute boundary.
        copy_attr = escape_html(json.dumps(copy_payload))

        cards.append(f'''
<div class="outreach-card" data-slot="{slot}">
  <div class="outreach-card-head">
    <div class="outreach-meta">
      <span class="slot-pill">EMAIL {slot}</span>
      <span class="voice-badge" style="color:{voice['color']};background:{voice['bg']};border-color:{voice['color']}">
        {voice['label']} VOICE
      </span>
      <span class="template-name">{escape_html(template_name)}</span>
    </div>
    <button class="copy-btn" type="button"
            data-copy-payload="{copy_attr}"
            aria-label="Copy email {slot} to clipboard">
      Copy
    </button>
  </div>
  {triggered_html}
  <div class="outreach-subject"><span class="subj-label">Subject</span> {escape_html(subject)}</div>
  <pre class="outreach-body">{escape_html(body)}</pre>
  <div class="outreach-rationale">
    <div class="rationale-label">Why this email for this prospect</div>
    <div class="rationale-text">{escape_html(rationale)}</div>
  </div>
</div>''')

    intro = ('<p class="outreach-intro">Three dossier-driven follow-up emails. '
             'Voice and angle selected from the prospect\'s strongest signals — '
             'see <em>references/outreach-playbook.md</em> for the template '
             'library and selection rules.</p>')
    return intro + '\n'.join(cards)


def load_peer_scores(log_path):
    """Load peer scores from leads_log.json for benchmarking."""
    if not log_path or not Path(log_path).exists():
        return []
    try:
        content = Path(log_path).read_text(encoding='utf-8')
        data = json.loads(content)
        # Accept either a list or a dict with 'leads' key
        leads = data if isinstance(data, list) else data.get('leads', [])
        return [int(l.get('score', 0)) for l in leads if isinstance(l.get('score'), (int, float))]
    except (json.JSONDecodeError, OSError):
        return []


# =============================================================================
#  v5.6 BUILD FUNCTIONS — Competitive Matrix, Ghost Stakeholders,
#                         Deal Execution Risks, Pre-Mortem, Rep Readiness
# =============================================================================

LIKELIHOOD_COLORS = {
    'Likely':   {'color': '#ef4444', 'bg': 'rgba(239,68,68,0.15)'},
    'Possible': {'color': '#f59e0b', 'bg': 'rgba(245,158,11,0.15)'},
    'Unlikely': {'color': '#6b7280', 'bg': 'rgba(107,114,128,0.15)'},
}

THREAT_COLORS = {
    'Critical': {'color': '#ef4444', 'bg': 'rgba(239,68,68,0.18)', 'icon': '🔴'},
    'Moderate': {'color': '#f59e0b', 'bg': 'rgba(245,158,11,0.18)', 'icon': '🟡'},
    'Low':      {'color': '#22c55e', 'bg': 'rgba(34,197,94,0.18)',  'icon': '🟢'},
}


def build_competitive_matrix_html(technology):
    """v5.6: Competitive Threat Matrix + Readiness Score."""
    matrix = technology.get('competitive_threat_matrix', []) or []
    readiness = technology.get('competitive_readiness_score')
    readiness_basis = technology.get('competitive_readiness_basis', '')

    if not matrix and readiness is None:
        return '<p class="empty">Competitive matrix not provided. ELISS requires this section — re-run the analyst step.</p>'

    parts = []

    # Readiness score badge row
    if readiness is not None:
        try:
            r = int(readiness)
        except (TypeError, ValueError):
            r = 5
        if r >= 8:
            rc = {'color': '#22c55e', 'bg': 'rgba(34,197,94,0.15)', 'label': 'Strong position'}
        elif r >= 5:
            rc = {'color': '#f59e0b', 'bg': 'rgba(245,158,11,0.15)', 'label': 'Competitive, POC required'}
        else:
            rc = {'color': '#ef4444', 'bg': 'rgba(239,68,68,0.15)', 'label': 'Uphill battle'}
        parts.append(f'''<div class="readiness-row">
  <div class="readiness-badge" style="background:{rc['bg']};color:{rc['color']};border-color:{rc['color']}">
    <div class="readiness-num">{r}<span class="readiness-denom">/10</span></div>
    <div class="readiness-label">{rc['label']}</div>
  </div>
  <div class="readiness-basis">
    <div class="readiness-basis-title">Competitive Readiness (vs. most likely incumbent)</div>
    <div class="readiness-basis-text">{escape_html(readiness_basis) if readiness_basis else 'No basis provided.'}</div>
  </div>
</div>''')

    # Matrix table
    if matrix:
        rows_html = []
        for row in matrix:
            comp = escape_html(row.get('competitor', '?'))
            likelihood = row.get('presence_likelihood', 'Possible')
            lc = LIKELIHOOD_COLORS.get(likelihood, LIKELIHOOD_COLORS['Possible'])
            basis = escape_html(row.get('basis', ''))
            basis_chips = render_evidence_chips(row.get('basis_urls'), aria_context='competitive basis')
            angle = escape_html(row.get('displacement_angle', ''))
            threat = row.get('threat_level', 'Moderate')
            tc = THREAT_COLORS.get(threat, THREAT_COLORS['Moderate'])
            rows_html.append(f'''<tr>
  <td class="ct-competitor"><strong>{comp}</strong></td>
  <td><span class="likelihood-badge" style="background:{lc['bg']};color:{lc['color']}">{escape_html(likelihood)}</span></td>
  <td class="ct-basis">{basis}{basis_chips}</td>
  <td class="ct-angle">{angle}</td>
  <td><span class="threat-badge" style="background:{tc['bg']};color:{tc['color']}">{tc['icon']} {escape_html(threat)}</span></td>
</tr>''')
        parts.append(f'''<div class="md-table-wrap comp-matrix-wrap">
  <table class="md-table comp-matrix">
    <thead><tr>
      <th>Competitor</th>
      <th>Presence</th>
      <th>Evidence / Basis</th>
      <th>Displacement Angle</th>
      <th>Threat</th>
    </tr></thead>
    <tbody>{''.join(rows_html)}</tbody>
  </table>
</div>''')

    return '\n'.join(parts)


# =============================================================================
#  v7.4 — Demo Playbook (persona-anchored AD360 + Log360 scripts)
# =============================================================================
DEMO_PRODUCT_COLORS = {
    'AD360':  {'color': '#6366f1', 'bg': 'rgba(99,102,241,0.10)', 'tint': 'rgba(99,102,241,0.18)'},
    'Log360': {'color': '#0ea5e9', 'bg': 'rgba(14,165,233,0.10)', 'tint': 'rgba(14,165,233,0.18)'},
}


def build_demo_playbook_html(demo):
    """v7.4: Demo Playbook — persona-anchored AD360 + Log360 demo scripts.

    Expects a dict shape:
        {
          persona: str,                # who the demo is for
          opening_hook: str,           # 90-second cold open, dossier-grounded
          ad360: {
            value_moments: [{title, why_it_matters, tell_show_tell}],
            discovery_questions: [str],
            top_objections: [{objection, response}],
            cta: str,
          },
          log360: { ...same shape... }
        }

    Returns '' on missing/empty input so the caller's lambda wrapper hides
    the whole section. Both ad360 and log360 sub-blocks are individually
    optional — render whichever the analyst populated.
    """
    if not isinstance(demo, dict) or not demo:
        return ''

    persona = _extract_value(demo.get('persona'), '')
    hook = _extract_value(demo.get('opening_hook'), '')
    head = ''
    if persona or hook:
        head_parts = ['<div class="demo-head">']
        if persona:
            head_parts.append(
                f'<div class="demo-persona">'
                f'<span class="demo-label">FOR</span>'
                f'<span class="demo-persona-text">{escape_html(persona)}</span>'
                f'</div>'
            )
        if hook:
            head_parts.append(
                f'<div class="demo-hook">'
                f'<span class="demo-label">OPENING HOOK</span>'
                f'<span class="demo-hook-text">{escape_html(hook)}</span>'
                f'</div>'
            )
        head_parts.append('</div>')
        head = ''.join(head_parts)

    def _product_block(prod_key, prod_data):
        if not isinstance(prod_data, dict) or not prod_data:
            return ''
        pc = DEMO_PRODUCT_COLORS.get(prod_key, DEMO_PRODUCT_COLORS['AD360'])

        moments = prod_data.get('value_moments') or []
        moment_cards = []
        for i, m in enumerate(moments, 1):
            if not isinstance(m, dict):
                continue
            title = escape_html(_extract_value(m.get('title')))
            why = escape_html(_extract_value(m.get('why_it_matters')))
            script = escape_html(_extract_value(m.get('tell_show_tell')))
            moment_cards.append(
                f'<div class="demo-moment">'
                f'<div class="demo-moment-num" style="background:{pc["tint"]};color:{pc["color"]}">VALUE MOMENT {i}</div>'
                f'<div class="demo-moment-title">{title}</div>'
                f'<div class="demo-moment-why"><strong>Why it matters:</strong> {why}</div>'
                f'<div class="demo-moment-script">{script}</div>'
                f'</div>'
            )
        moments_html = ''.join(moment_cards) if moment_cards else '<p class="empty">No value moments authored.</p>'

        qs = [q for q in (prod_data.get('discovery_questions') or []) if q]
        qs_html = ''.join(f'<li>{escape_html(q)}</li>' for q in qs) if qs else ''

        objs = prod_data.get('top_objections') or []
        obj_cards = []
        for o in objs:
            if not isinstance(o, dict):
                continue
            obj_text = escape_html(_extract_value(o.get('objection')))
            resp_text = escape_html(_extract_value(o.get('response')))
            obj_cards.append(
                f'<div class="demo-obj">'
                f'<div class="demo-obj-q">&ldquo;{obj_text}&rdquo;</div>'
                f'<div class="demo-obj-a">{resp_text}</div>'
                f'</div>'
            )
        objs_html = ''.join(obj_cards)

        cta = escape_html(_extract_value(prod_data.get('cta'), ''))
        cta_html = (f'<div class="demo-cta">'
                    f'<span class="demo-cta-label">CTA</span>'
                    f'<span class="demo-cta-text">{cta}</span>'
                    f'</div>') if cta else ''

        return (
            f'<div class="demo-product" style="border-left:4px solid {pc["color"]};background:{pc["bg"]}">'
            f'<div class="demo-product-head" style="color:{pc["color"]}">{prod_key}</div>'
            f'<div class="demo-section-title">3 Value Moments &mdash; not a feature tour</div>'
            f'{moments_html}'
            + (f'<div class="demo-section-title">Discovery Questions</div><ul class="demo-qs">{qs_html}</ul>' if qs_html else '')
            + (f'<div class="demo-section-title">Top Objections</div>{objs_html}' if objs_html else '')
            + cta_html
            + '</div>'
        )

    blocks = head + _product_block('AD360', demo.get('ad360')) + _product_block('Log360', demo.get('log360'))
    if not blocks.strip():
        return ''
    return blocks


def build_ghost_stakeholders_html(org_intel):
    """v5.6: Ghost Stakeholder cards — open roles that will own the decision."""
    ghosts = org_intel.get('future_stakeholders', []) or []
    if not ghosts:
        return ('<div class="ghost-empty">'
                '<strong>No ghost stakeholders detected.</strong> '
                'ELISS requires this section — confirm the analyst searched the careers page, '
                'LinkedIn Jobs, and relevant job boards before accepting an empty list.'
                '</div>')

    cards = []
    for g in ghosts:
        role = escape_html(g.get('role', 'Unknown role'))
        status = escape_html(g.get('status', 'Status unknown'))
        arrival = escape_html(g.get('estimated_arrival', 'Unknown'))
        scope = escape_html(g.get('role_scope', ''))
        risk = escape_html(g.get('risk', ''))
        opp = escape_html(g.get('opportunity', ''))
        action = escape_html(g.get('action', ''))
        cards.append(f'''<div class="ghost-card">
  <div class="ghost-card-header">
    <span class="ghost-icon">👤</span>
    <div class="ghost-role">{role}</div>
    <div class="ghost-meta">
      <span class="ghost-status">{status}</span>
      <span class="ghost-arrival">ETA: {arrival}</span>
    </div>
  </div>
  <div class="ghost-body">
    {f'<div class="ghost-field"><div class="ghost-field-label">Scope</div><div class="ghost-field-text">{scope}</div></div>' if scope else ''}
    {f'<div class="ghost-field ghost-risk"><div class="ghost-field-label">Risk</div><div class="ghost-field-text">{risk}</div></div>' if risk else ''}
    {f'<div class="ghost-field ghost-opp"><div class="ghost-field-label">Opportunity</div><div class="ghost-field-text">{opp}</div></div>' if opp else ''}
    {f'<div class="ghost-field ghost-action"><div class="ghost-field-label">Action</div><div class="ghost-field-text">{action}</div></div>' if action else ''}
  </div>
</div>''')
    return '\n'.join(cards)


def build_deal_execution_risks_html(scoring):
    """v5.6: Deal Execution Risks table + Risk-Adjusted Composite."""
    risks = scoring.get('deal_execution_risks', []) or []
    total = scoring.get('total_risk_adjustment')
    adjusted = scoring.get('risk_adjusted_composite')
    raw = scoring.get('final_score', scoring.get('composite', 0))

    if not risks and total is None and adjusted is None:
        return ('<p class="empty">'
                'Deal execution risks not provided. ELISS requires this section — '
                'an empty execution-risks list is almost always a sign the analyst hasn\'t looked hard enough.'
                '</p>')

    parts = []

    # Risk-adjusted badge strip
    if adjusted is not None:
        try:
            raw_i = int(raw)
            adj_i = int(adjusted)
            delta = adj_i - raw_i
        except (TypeError, ValueError):
            raw_i, adj_i, delta = 0, 0, 0
        delta_label = f'{delta:+d}' if delta != 0 else '0'
        delta_color = '#ef4444' if delta < 0 else '#22c55e' if delta > 0 else '#6b7280'
        parts.append(f'''<div class="risk-adjusted-strip">
  <div class="ras-cell">
    <div class="ras-label">Raw Composite</div>
    <div class="ras-value">{raw_i}<span class="ras-denom">/100</span></div>
  </div>
  <div class="ras-arrow" style="color:{delta_color}">→ {delta_label}</div>
  <div class="ras-cell ras-adj">
    <div class="ras-label">Risk-Adjusted</div>
    <div class="ras-value" style="color:{delta_color}">{adj_i}<span class="ras-denom">/100</span></div>
  </div>
</div>''')

    # Risk table
    if risks:
        rows_html = []
        for r in risks:
            desc = escape_html(r.get('risk', ''))
            weight = r.get('weight', 0)
            try:
                w_i = int(weight)
            except (TypeError, ValueError):
                w_i = 0
            w_label = f'{w_i:+d}' if w_i != 0 else '0'
            w_color = '#ef4444' if w_i < 0 else '#22c55e' if w_i > 0 else '#6b7280'
            evidence = escape_html(r.get('evidence', ''))
            evidence_chips = render_evidence_chips(r.get('evidence_urls'), aria_context='execution risk')
            mitigation = escape_html(r.get('mitigation', ''))
            cred = r.get('mitigation_credibility', 'MEDIUM')
            cc = CONF_CONFIG.get(cred, CONF_CONFIG['MEDIUM'])
            rows_html.append(f'''<tr>
  <td class="der-weight"><span class="der-weight-badge" style="color:{w_color}">{w_label}</span></td>
  <td class="der-risk"><strong>{desc}</strong></td>
  <td class="der-evidence">{evidence}{evidence_chips}</td>
  <td class="der-mitigation">{mitigation}</td>
  <td class="der-cred"><span class="conf-tag" style="color:{cc['color']}">{escape_html(cred)}</span></td>
</tr>''')
        parts.append(f'''<div class="md-table-wrap der-wrap">
  <table class="md-table der-table">
    <thead><tr>
      <th>Weight</th>
      <th>Risk Factor</th>
      <th>Evidence</th>
      <th>Mitigation</th>
      <th>Credibility</th>
    </tr></thead>
    <tbody>{''.join(rows_html)}</tbody>
  </table>
</div>''')

    return '\n'.join(parts)


def build_pre_mortem_html(pre_mortem):
    """v5.6: Pre-Mortem — why we might lose this deal."""
    items = pre_mortem or []
    if not items:
        return ('<p class="empty">'
                'Pre-mortem not provided. ELISS requires 3–5 specific, evidence-grounded loss scenarios — '
                're-run the analyst step.'
                '</p>')

    blocks = []
    for i, item in enumerate(items, 1):
        scenario = escape_html(item.get('scenario', ''))
        why = escape_html(item.get('why_it_could_happen', ''))
        why_chips = render_evidence_chips(item.get('evidence_urls'), aria_context='pre-mortem evidence')
        mit = escape_html(item.get('mitigation', ''))
        signal = escape_html(item.get('earliest_signal', ''))
        blocks.append(f'''<div class="pm-item">
  <div class="pm-num">{i}</div>
  <div class="pm-body">
    <div class="pm-scenario">{scenario}</div>
    {f'<div class="pm-why">{why}{why_chips}</div>' if why else ''}
    <div class="pm-detail"><span class="pm-label">Mitigation:</span> {mit}</div>
    {f'<div class="pm-detail pm-signal"><span class="pm-label">Earliest signal:</span> {signal}</div>' if signal else ''}
  </div>
</div>''')
    return '\n'.join(blocks)


def build_rep_readiness_html(checklist):
    """v5.6: Rep Readiness Checklist."""
    items = checklist or []
    if not items:
        return ('<p class="empty">'
                'Rep readiness checklist not provided. ELISS requires 5–8 account-specific items.'
                '</p>')

    lis = ''.join(f'<li class="rr-item"><span class="rr-box">☐</span><span class="rr-text">{escape_html(str(item))}</span></li>' for item in items)
    return f'<ul class="rr-list">{lis}</ul>'


# =============================================================================
#  v6.2 — WAVE 1 INFOGRAPHICS
#  Four additive visualizations that complement (never replace) existing
#  tables and charts:
#    1. Score Attribution Bar    — where the score came from, signal-by-signal
#    2. Scenario Cards           — three what-if score modulators
#    3. Web Tech Fingerprint     — categorized tech-stack badge grid
#    4. Decision Tree Flowchart  — branching SVG tree of first-call signals
# Every function returns '' if its source data isn't in the JSON, so the
# section is silently omitted on dossiers that don't include the new fields.
# =============================================================================

# Category colors used by attribution bar — kept in sync with svg_signal_timeline
# so a signal's segment in the attribution bar matches its dot in the timeline.
_ATTR_CAT_COLORS = {
    'Security incident': '#ef4444', 'breach_incident': '#ef4444', 'security_incident': '#ef4444',
    'Compliance need': '#ec4899', 'compliance_deadline': '#ec4899', 'compliance_need': '#ec4899',
    'compliance': '#f97316',
    'AD pain': '#8b5cf6', 'ad_pain': '#8b5cf6',
    'Security hiring': '#22c55e', 'hiring': '#22c55e', 'security_hiring': '#22c55e',
    'Tech investment': '#3b82f6', 'technology_change': '#3b82f6', 'tech_investment': '#3b82f6',
    'budget_event': '#06b6d4',
    'grant_funding': '#10b981',
    'audit_finding': '#f59e0b',
    'executive_change': '#0ea5e9',
    'mergers_acquisitions': '#eab308',
    'conference_speaking': '#14b8a6',
    'partnership': '#d946ef',
    'vendor_evaluation': '#a855f7',
    'general': '#22c55e',
    'procurement_cycle': '#8b5cf6',
}

def _attr_color(label):
    """Resolve a category label to a stable hex color; fall back to indigo.

    v7.2.1: case-insensitive + keyword-based fallback so analyst-written
    categories like "Compliance Need" (capital N) or "AD/IAM Pain (proxy)"
    don't all collapse to indigo and render the attribution bar as a single
    color. Tries exact match first, then a normalized lookup, then keyword
    matching against common buying-signal vocabularies.
    """
    if not label:
        return '#6366f1'
    # 1. exact match (preserves prior behaviour)
    if label in _ATTR_CAT_COLORS:
        return _ATTR_CAT_COLORS[label]
    # 2. normalize: lowercase + strip parentheticals + replace underscores
    norm = label.lower().split('(')[0].strip().replace('_', ' ')
    for key, color in _ATTR_CAT_COLORS.items():
        if key.lower().replace('_', ' ') == norm:
            return color
    # 3. keyword fallback (priority order — first match wins)
    keyword_map = [
        (('breach', 'ransomware', 'incident', 'attack'),     '#ef4444'),  # red
        (('compliance', 'audit', 'regulatory', 'regulation', 'framework'), '#ec4899'),  # pink
        (('ad pain', 'iam pain', 'identity pain', 'ad/iam'), '#8b5cf6'),  # purple
        (('hiring', 'recruit'),                              '#22c55e'),  # green
        (('tech', 'modernization', 'platform', 'cloud', 'investment'), '#3b82f6'),  # blue
        (('budget', 'spend', 'capex', 'opex'),               '#06b6d4'),  # cyan
        (('grant', 'funding'),                               '#10b981'),  # emerald
        (('procurement', 'rfp', 'renewal'),                  '#f97316'),  # orange
        (('leadership', 'ciso', 'cio', 'change'),            '#a855f7'),  # violet
        (('direct', 'inquiry', 'engagement'),                '#f59e0b'),  # amber
    ]
    for keywords, color in keyword_map:
        if any(kw in norm for kw in keywords):
            return color
    # 4. fallback indigo
    return '#6366f1'


def build_score_attribution_bar(scoring):
    """v6.2: Horizontal stacked bar showing the per-signal contribution to the
    Intent score. Each segment is sized by `points` and colored by category.
    Renders the cap line if intent.raw_total > intent.score (intent was capped).

    Falls back to '' if scoring.intent.signals is missing or empty.
    """
    intent = (scoring or {}).get('intent', {}) or {}
    sigs = intent.get('signals', []) or []
    sigs = [s for s in sigs if isinstance(s, dict) and s.get('points')]
    if not sigs:
        return ''

    raw_total = intent.get('raw_total') or sum(int(s.get('points', 0) or 0) for s in sigs)
    capped_at = intent.get('score', intent.get('max', 25)) or 25
    max_axis = max(raw_total, capped_at, 1)

    # Build segments (sized proportional to raw_total, the actual sum of points).
    # If intent was capped, the bar still shows the FULL raw contribution so
    # the rep can see what was discounted.
    segments_html = ''
    legend_html = ''
    cum = 0
    for i, s in enumerate(sigs):
        pts = int(s.get('points', 0) or 0)
        if pts <= 0:
            continue
        cat = s.get('category', 'general')
        color = _attr_color(cat)
        pct = (pts / max_axis) * 100
        evidence = s.get('evidence', '')
        title = f'{cat} (+{pts} pts)\n{evidence}' if evidence else f'{cat} (+{pts} pts)'
        segments_html += (
            f'<div class="attr-seg" style="width:{pct:.2f}%;background:{color}" '
            f'title="{escape_html(title)}">'
            f'<span class="attr-seg-label">+{pts}</span>'
            f'</div>'
        )
        legend_html += (
            f'<div class="attr-leg-row">'
            f'<span class="attr-leg-dot" style="background:{color}"></span>'
            f'<span class="attr-leg-cat">{escape_html(cat)}</span>'
            f'<span class="attr-leg-pts">+{pts}</span>'
            f'<span class="attr-leg-evidence">{escape_html(evidence[:120])}</span>'
            f'</div>'
        )
        cum += pts

    # Cap-line position (where the score was capped to)
    cap_pct = (capped_at / max_axis) * 100
    cap_overlay = ''
    cap_caption = ''
    if raw_total > capped_at:
        cap_overlay = (
            f'<div class="attr-cap-line" style="left:{cap_pct:.2f}%">'
            f'<div class="attr-cap-flag">CAP @ {capped_at}</div>'
            f'</div>'
        )
        cap_caption = (
            f'<div class="attr-caption">'
            f'<strong>{raw_total}</strong> raw points → '
            f'<strong>{capped_at}</strong> after Intent triangulation cap. '
            f'<span class="attr-caption-note">'
            f'The {raw_total - capped_at}-point ceiling is the methodology guarding against '
            f'over-weighting a single buying-signal cluster.'
            f'</span></div>'
        )
    else:
        cap_caption = (
            f'<div class="attr-caption">'
            f'<strong>{raw_total}</strong> raw points = <strong>{capped_at}</strong> Intent score '
            f'(no cap applied).'
            f'</div>'
        )

    return f'''<div class="attr-wrap">
  <div class="attr-bar-shell">
    <div class="attr-bar">{segments_html}</div>
    {cap_overlay}
  </div>
  {cap_caption}
  <div class="attr-legend">{legend_html}</div>
</div>'''


def build_scenario_cards(scoring):
    """v6.2: Three (or more) what-if scenario cards. Each card shows
    before→after score, before→after tier, the logic, and the trigger to
    watch for. Returns '' if no scenarios array is present.
    """
    scenarios = (scoring or {}).get('scenarios', []) or []
    if not scenarios:
        return ''

    cards_html = ''
    for sc in scenarios:
        if not isinstance(sc, dict):
            continue
        delta = sc.get('delta', 0)
        before = sc.get('before_score', '?')
        after = sc.get('after_score', '?')
        before_tier = sc.get('before_tier', '')
        after_tier = sc.get('after_tier', '')
        kind = sc.get('kind', 'positive' if (isinstance(delta, (int, float)) and delta >= 0) else 'negative')
        accent = {'positive': '#22c55e', 'negative': '#ef4444', 'pivot': '#f59e0b', 'neutral': '#6366f1'}.get(kind, '#6366f1')
        delta_str = f'+{delta}' if isinstance(delta, (int, float)) and delta > 0 else str(delta)
        tier_change = ''
        if before_tier and after_tier:
            if before_tier == after_tier:
                tier_change = f'<span class="sc-tier-stable">{escape_html(after_tier)}</span>'
            else:
                tier_change = (
                    f'<span class="sc-tier-old">{escape_html(before_tier)}</span>'
                    f'<span class="sc-tier-arrow">→</span>'
                    f'<span class="sc-tier-new" style="color:{accent}">{escape_html(after_tier)}</span>'
                )

        cards_html += f'''<div class="sc-card" style="border-color:{accent}40">
  <div class="sc-card-head" style="background:{accent}12">
    <div class="sc-delta-pill" style="background:{accent};color:#fff">{escape_html(str(delta_str))} pts</div>
    <div class="sc-score-shift">
      <span class="sc-score-old">{escape_html(str(before))}</span>
      <span class="sc-score-arrow" style="color:{accent}">→</span>
      <span class="sc-score-new" style="color:{accent}">{escape_html(str(after))}</span>
      <span class="sc-score-suffix">/100</span>
    </div>
    <div class="sc-tier-row">{tier_change}</div>
  </div>
  <div class="sc-card-body">
    <div class="sc-label">{escape_html(sc.get('label', ''))}</div>
    <div class="sc-block">
      <div class="sc-block-title">Why it shifts</div>
      <div class="sc-block-text">{escape_html(sc.get('logic', ''))}</div>
    </div>
    <div class="sc-block sc-trigger" style="border-left-color:{accent}">
      <div class="sc-block-title" style="color:{accent}">Trigger to watch</div>
      <div class="sc-block-text">{escape_html(sc.get('trigger', ''))}</div>
    </div>
  </div>
</div>'''

    return f'<div class="sc-grid">{cards_html}</div>'


def build_web_fingerprint(technology):
    """v6.2: Categorized badge grid showing the lead's web property tech
    stack — frontend libs, analytics, chat, CDN, CMS, email-marketing.
    Each badge shows the tech name, a confidence dot, and an evidence tooltip.
    Returns '' if no web_fingerprint object is present.
    """
    fp = (technology or {}).get('web_fingerprint', {}) or {}
    if not fp:
        return ''

    # Display order + icons + accent colors
    # v7.5.3 — added 'framework' (ASP.NET / Next.js / Django / etc.) which
    # the v7.5 preflight emits but the v6.2-era renderer was ignoring.
    cat_meta = [
        ('frontend',         '🧩', 'Frontend libraries',      '#6366f1'),
        ('framework',        '🛠️', 'Framework',              '#0ea5e9'),
        ('analytics',        '📊', 'Analytics',               '#06b6d4'),
        ('chat',             '💬', 'Chat / messaging',        '#22c55e'),
        ('cdn',              '⚡', 'CDN / edge',              '#f59e0b'),
        ('cms',              '📝', 'CMS',                     '#a855f7'),
        ('email_marketing',  '✉️', 'Email marketing',         '#ec4899'),
    ]
    conf_dot = {
        'HIGH':   '#22c55e',
        'MEDIUM': '#f59e0b',
        'LOW':    '#94a3b8',
    }

    cards_html = ''
    rendered_any = False
    for key, icon, title, accent in cat_meta:
        items = fp.get(key, []) or []
        if not items:
            cards_html += (
                f'<div class="wf-cat wf-cat-empty">'
                f'<div class="wf-cat-head">'
                f'<span class="wf-cat-icon">{icon}</span>'
                f'<span class="wf-cat-title">{escape_html(title)}</span>'
                f'</div>'
                f'<div class="wf-cat-empty-text">— none detected —</div>'
                f'</div>'
            )
            continue
        rendered_any = True
        badges = ''
        for it in items:
            # v7.5.3 — accept both shapes: rich dict {name, version, confidence, evidence}
            # OR plain string (the v7.5 preflight script emits strings). Previously the
            # renderer dropped every string with `continue`, so category counts showed
            # correctly but the badge body rendered empty. Backward compatible.
            if isinstance(it, str):
                if not it.strip():
                    continue
                name = it.strip()
                ver = ''
                conf = 'MEDIUM'
                ev = ''
            elif isinstance(it, dict):
                name = it.get('name', '?')
                ver = it.get('version', '')
                conf = (it.get('confidence') or 'MEDIUM').upper()
                ev = it.get('evidence', '')
            else:
                continue
            ver_html = f'<span class="wf-ver">{escape_html(ver)}</span>' if ver else ''
            # v6.2.2 — Tooltip was previously the raw `evidence` string, which
            # often looked like raw code/path text to non-technical readers
            # (e.g. "/lib/jquery-3.7.1.min.js script tag in coppelltx.gov footer").
            # Build a structured, labeled tooltip instead. Browser-native title
            # attributes support newlines via literal \n. Order: vendor name +
            # version, confidence label, then evidence prefixed with "Evidence:"
            # so the reader knows what they're looking at.
            tip_lines = []
            vendor_line = name
            if ver:
                vendor_line += f' {ver}'
            tip_lines.append(vendor_line)
            tip_lines.append(f'{conf} confidence')
            if ev:
                tip_lines.append(f'Evidence: {ev}')
            tooltip = '\n'.join(tip_lines)
            badges += (
                f'<div class="wf-badge" style="border-color:{accent}40" title="{escape_html(tooltip)}">'
                f'<span class="wf-conf-dot" style="background:{conf_dot.get(conf, "#94a3b8")}"></span>'
                f'<span class="wf-name">{escape_html(name)}</span>'
                f'{ver_html}'
                f'</div>'
            )
        cards_html += (
            f'<div class="wf-cat" style="border-top:3px solid {accent}">'
            f'<div class="wf-cat-head">'
            f'<span class="wf-cat-icon">{icon}</span>'
            f'<span class="wf-cat-title">{escape_html(title)}</span>'
            f'<span class="wf-cat-count">{len(items)}</span>'
            f'</div>'
            f'<div class="wf-cat-body">{badges}</div>'
            f'</div>'
        )

    if not rendered_any:
        return ''

    legend = (
        '<div class="wf-legend">'
        '<span class="wf-legend-item"><span class="wf-conf-dot" style="background:#22c55e"></span>HIGH confidence</span>'
        '<span class="wf-legend-item"><span class="wf-conf-dot" style="background:#f59e0b"></span>MEDIUM</span>'
        '<span class="wf-legend-item"><span class="wf-conf-dot" style="background:#94a3b8"></span>LOW / inferred</span>'
        '<span class="wf-legend-hint">Hover any badge to see evidence (script tags, response headers, asset hosts).</span>'
        '</div>'
    )
    return f'<div class="wf-grid">{cards_html}</div>{legend}'


def build_rocketreach_enrichment(data):
    """v7.1.3 — RocketReach firmographic enrichment section for Tab 1.

    Surfaces the data the baseline enrichment pass writes that was previously
    invisible: the full RR techstack (`technology.techstack_from_rr`), the
    department-headcount rollup (`org_intelligence.departments_headcount`),
    the per-department workforce growth trajectory (`technology.growth_trajectory`),
    industry keywords (`company.industry_keywords`), SIC/NAICS codes, and the
    RocketReach profile URL for deep-link audit. Returns '' when none of these
    fields are present so the section hides gracefully on dossiers generated
    pre-v7.1.3 or when RR_API_KEY was unset.
    """
    co = (data or {}).get('company', {}) or {}
    tech = (data or {}).get('technology', {}) or {}
    org = (data or {}).get('org_intelligence', {}) or {}

    rr_techstack = tech.get('techstack_from_rr') or []
    growth = tech.get('growth_trajectory') or []
    depts = org.get('departments_headcount') or {}
    rr_profile_url = co.get('rr_profile_url') or ''
    industry_keywords = co.get('industry_keywords') or []
    naics = co.get('naics_codes') or []
    sic = co.get('sic_codes') or []
    year_founded = co.get('year_founded')
    rr_address = co.get('rr_address') or co.get('address') or {}
    rr_company_phone = co.get('company_phone') if co.get('_rocketreach_company_phone') else None
    rr_company_linkedin = co.get('company_linkedin') if co.get('_rocketreach_company_linkedin') else None

    if not any([rr_techstack, growth, depts, rr_profile_url, industry_keywords,
                naics, sic, year_founded, rr_address, rr_company_phone,
                rr_company_linkedin]):
        return ''

    parts: list[str] = []

    # Header — compact meta-row with profile deep-link, founding year, HQ address.
    # v7.1.3 post-review: removed the redundant RR Employees/Revenue/Industry
    # rows (already shown in Company Profile) and the description blurb
    # (verbose, low-signal for sales context).
    header_bits: list[str] = []
    if rr_profile_url:
        # Pill removed — the section title already names the source unambiguously,
        # so a trailing "RR" glyph on the one link that literally says
        # "RocketReach Profile" is pure noise.
        header_bits.append(
            f'<a class="rr-header-link" href="{escape_html(rr_profile_url)}" '
            f'target="_blank" rel="noopener">'
            f'<span class="rr-header-link-label">RocketReach Profile</span>'
            f'<span class="rr-header-link-arrow">↗</span>'
            f'</a>'
        )
    if year_founded:
        year_val = escape_html(str(year_founded)[:4])  # trim ISO date to year only
        header_bits.append(
            f'<div class="rr-header-meta">'
            f'<span class="rr-header-meta-label">Founded</span>'
            f'<span class="rr-header-meta-value">{year_val}</span>'
            f'</div>'
        )
    if isinstance(rr_address, dict) and rr_address.get('description'):
        header_bits.append(
            f'<div class="rr-header-meta">'
            f'<span class="rr-header-meta-label">Headquarters</span>'
            f'<span class="rr-header-meta-value">{escape_html(rr_address["description"])}</span>'
            f'</div>'
        )
    if rr_company_phone:
        header_bits.append(
            f'<div class="rr-header-meta">'
            f'<span class="rr-header-meta-label">Phone</span>'
            f'<span class="rr-header-meta-value">{escape_html(str(rr_company_phone))}</span>'
            f'</div>'
        )
    if rr_company_linkedin:
        header_bits.append(
            f'<div class="rr-header-meta">'
            f'<span class="rr-header-meta-label">LinkedIn</span>'
            f'<span class="rr-header-meta-value"><a href="{escape_html(rr_company_linkedin)}" '
            f'target="_blank" rel="noopener" style="color:inherit;text-decoration:underline">View</a></span>'
            f'</div>'
        )
    if header_bits:
        parts.append(
            f'<div class="rr-enrich-header">{"".join(header_bits)}</div>'
        )

    # Codes + keywords strip
    code_bits: list[str] = []
    if industry_keywords:
        top = industry_keywords[:10]
        pills = ''.join(
            f'<span class="rr-kw-pill">{escape_html(str(k))}</span>' for k in top
        )
        code_bits.append(
            f'<div class="rr-subblock">'
            f'<div class="rr-subblock-label">Industry Keywords</div>'
            f'<div class="rr-subblock-value">{pills}</div>'
            f'</div>'
        )
    if naics:
        code_bits.append(
            f'<div class="rr-subblock">'
            f'<div class="rr-subblock-label">NAICS</div>'
            f'<div class="rr-subblock-value rr-codes">{escape_html(", ".join(map(str, naics[:5])))}</div>'
            f'</div>'
        )
    if sic:
        code_bits.append(
            f'<div class="rr-subblock">'
            f'<div class="rr-subblock-label">SIC</div>'
            f'<div class="rr-subblock-value rr-codes">{escape_html(", ".join(map(str, sic[:5])))}</div>'
            f'</div>'
        )
    if code_bits:
        parts.append(f'<div class="rr-enrich-codes">{"".join(code_bits)}</div>')

    # Techstack — capped tighter (40 → still representative, denser layout)
    if rr_techstack:
        top_stack = rr_techstack[:40]
        pills = ''.join(
            f'<span class="rr-tech-chip">{escape_html(str(t))}</span>'
            for t in top_stack
        )
        more_suffix = ''
        if len(rr_techstack) > 40:
            more_suffix = (
                f'<span class="rr-tech-more">+{len(rr_techstack) - 40} more</span>'
            )
        parts.append(
            f'<div class="rr-enrich-block">'
            f'<div class="rr-enrich-block-head">'
            f'<span class="rr-enrich-block-title">Confirmed Tech Stack</span>'
            f'<span class="rr-enrich-block-count">{len(rr_techstack)} technologies</span>'
            f'</div>'
            f'<div class="rr-tech-grid">{pills}{more_suffix}</div>'
            f'</div>'
        )

    # Headcount + Trajectory live inside a shared two-column wrapper so they
    # pack side-by-side on wide viewports instead of stacking and bloating the
    # section's vertical height. Each block still hides independently when its
    # data source is empty.
    dept_block_html = ''
    trend_block_html = ''

    if depts and isinstance(depts, dict):
        rows: list[tuple[str, int]] = []
        for label, val in depts.items():
            if not label or label in ('unknown', ''):
                continue
            if isinstance(val, (int, float)):
                rows.append((str(label).replace('_', ' ').title(), int(val)))
            elif isinstance(val, dict):
                n = val.get('after') if isinstance(val.get('after'), (int, float)) else val.get('count')
                if isinstance(n, (int, float)):
                    rows.append((str(label).replace('_', ' ').title(), int(n)))
        if rows:
            rows.sort(key=lambda r: r[1], reverse=True)
            total = sum(r[1] for r in rows)
            max_n = max(r[1] for r in rows) or 1
            bars = ''
            for label, n in rows:
                width_pct = max(4, int(n / max_n * 100))
                bars += (
                    f'<div class="rr-dept-row">'
                    f'<div class="rr-dept-label">{escape_html(label)}</div>'
                    f'<div class="rr-dept-bar-track">'
                    f'<div class="rr-dept-bar-fill" style="width:{width_pct}%"></div>'
                    f'</div>'
                    f'<div class="rr-dept-value">{n}</div>'
                    f'</div>'
                )
            dept_block_html = (
                f'<div class="rr-enrich-block">'
                f'<div class="rr-enrich-block-head">'
                f'<span class="rr-enrich-block-title">Department Headcount</span>'
                f'<span class="rr-enrich-block-count">{total} total · {len(rows)} depts</span>'
                f'</div>'
                f'<div class="rr-dept-grid">{bars}</div>'
                f'</div>'
            )

    # Growth trajectory — walk backwards to find the most recent quarter with
    # non-zero movement. The RR `company_growth` payload is often padded with
    # flat-zero quarters (holiday freezes, budget freezes, sampling windows);
    # showing "all zeros" for the latest quarter would hide the real signal.
    if growth and isinstance(growth, list):
        latest = {}
        moves: list[tuple[str, int]] = []
        for entry in reversed(growth):
            if not isinstance(entry, dict):
                continue
            vals = entry.get('values') or {}
            cand_moves: list[tuple[str, int]] = []
            for dept, m in (vals or {}).items():
                if not dept or dept in ('unknown', ''):
                    continue
                if isinstance(m, dict):
                    net = m.get('net')
                    if isinstance(net, (int, float)) and net != 0:
                        cand_moves.append((str(dept).replace('_', ' ').title(), int(net)))
            if cand_moves:
                latest = entry
                moves = cand_moves
                break
        vals = latest.get('values') or {}
        if isinstance(vals, dict) and vals:
            if moves:
                moves.sort(key=lambda r: r[1], reverse=True)
                qtr_label = f"{latest.get('year','?')} Q{latest.get('quarter','?')}"
                rows_html = ''
                for dept, net in moves:
                    cls = 'rr-trend-up' if net > 0 else 'rr-trend-down'
                    arrow = '▲' if net > 0 else '▼'
                    rows_html += (
                        f'<div class="rr-trend-row">'
                        f'<span class="rr-trend-dept">{escape_html(dept)}</span>'
                        f'<span class="rr-trend-delta {cls}">{arrow} {abs(net)}</span>'
                        f'</div>'
                    )
                trend_block_html = (
                    f'<div class="rr-enrich-block">'
                    f'<div class="rr-enrich-block-head">'
                    f'<span class="rr-enrich-block-title">Workforce Trajectory</span>'
                    f'<span class="rr-enrich-block-count">{escape_html(qtr_label)}</span>'
                    f'</div>'
                    f'<div class="rr-trend-grid">{rows_html}</div>'
                    f'</div>'
                )

    # Emit the headcount/trajectory pair as a responsive two-column row so the
    # section reads left-to-right on wide viewports instead of stacking.
    if dept_block_html and trend_block_html:
        parts.append(
            f'<div class="rr-enrich-pair">{dept_block_html}{trend_block_html}</div>'
        )
    elif dept_block_html:
        parts.append(dept_block_html)
    elif trend_block_html:
        parts.append(trend_block_html)

    return ''.join(parts)


def build_rocketreach_enrichment_tab2(data, data_level_hint=None):
    """v7.1.4 — Tab 2 variant of the RocketReach Enrichment section.

    Tab 2 (Complete Intelligence Dossier) is a prose-first surface rendered
    entirely through the markdown-to-HTML pipeline — indigo `.md-h2` section
    headers, indigo-bordered `.md-h3` sub-heads, `.md-li-kv` key-value
    bullets, `.md-table` tabular data. Dropping the Tab-1 champagne card
    in here looked like a UI transplant from another report. This builder
    emits the same *data* using the native Tab-2 classes, so the section
    reads as part of the analyst narrative rather than an infographic pasted
    on top.

    Excludes Industry Keywords, Founded, HQ per v7.1.4 design review —
    prose readers don't need the location/founding metadata (they have it
    upstream in the Company Profile markdown), and the keyword pills were
    visual noise in a text-heavy surface.

    `data_level_hint` is an optional already-rendered Tab 2 HTML string. We
    probe it for `COMPANY PROFILE` and match BOTH the DOM tag AND the CSS
    class it renders with — the markdown renderer sometimes emits `<h3
    class="md-h2">` (an h2-*styled* h3), in which case matching only the tag
    demotes the section visually. The CLASS drives the styling rules, so we
    mirror it. Sub-heads step down one class level (md-h2 → md-h3,
    md-h3 → md-h4) and one DOM-tag level.
    """
    # v7.1.4 post-review: use BOTH the DOM tag and the `md-*` class from
    # COMPANY PROFILE. Defaults target a v7.1.2 template-compliant dossier
    # (## SECTION → <h3 class="md-h2">, ### Sub → <h4 class="md-h3">).
    section_tag = 'h3'
    section_cls = 'md-h2'
    sub_tag = 'h4'
    sub_cls = 'md-h3'
    if isinstance(data_level_hint, str) and data_level_hint:
        m = re.search(
            r'<(h[234])\b([^>]*)>\s*(?:<a\b[^<]*</a>)?\s*COMPANY\s+PROFILE',
            data_level_hint, flags=re.IGNORECASE,
        )
        if m:
            section_tag = m.group(1).lower()
            cls_match = re.search(r'class\s*=\s*"([^"]*)"', m.group(2) or '')
            if cls_match:
                # Pick the first md-h* token in the class list
                md_class = next(
                    (t for t in cls_match.group(1).split()
                     if re.fullmatch(r'md-h[1-6]', t)),
                    None,
                )
                if md_class:
                    section_cls = md_class
                    # Step sub one class level deeper (md-h2 → md-h3)
                    cur = int(md_class[-1])
                    sub_cls = f'md-h{min(cur + 1, 6)}'
            # DOM tag for sub is one level deeper too
            cur_tag = int(section_tag[1])
            sub_tag = f'h{min(cur_tag + 1, 6)}'
    h_main = section_tag
    h_sub = sub_tag
    h_main_cls = section_cls
    h_sub_cls = sub_cls
    co = (data or {}).get('company', {}) or {}
    tech = (data or {}).get('technology', {}) or {}
    org = (data or {}).get('org_intelligence', {}) or {}

    rr_techstack = tech.get('techstack_from_rr') or []
    growth = tech.get('growth_trajectory') or []
    depts = org.get('departments_headcount') or {}
    rr_profile_url = co.get('rr_profile_url') or ''
    rr_company_phone = co.get('company_phone') if co.get('_rocketreach_company_phone') else None
    rr_company_linkedin = co.get('company_linkedin') if co.get('_rocketreach_company_linkedin') else None
    naics = co.get('naics_codes') or []
    sic = co.get('sic_codes') or []

    if not any([rr_techstack, growth, depts, rr_profile_url, rr_company_phone,
                rr_company_linkedin, naics, sic]):
        return ''

    parts: list[str] = []
    # v7.1.4 — Match the markdown renderer's convention of prepending a
    # copy-link anchor inside every section header. Without this, the RR
    # header visibly lacks the `#` prefix every other section shows.
    def _md_anchor(slug):
        return (
            f'<a class="md-anchor" href="#{slug}" '
            f'aria-label="Link to this section" '
            f'title="Copy link to this section">#</a>'
        )

    parts.append(
        f'<{h_main} class="{h_main_cls}" id="rocketreach-firmographic-enrichment">'
        f'{_md_anchor("rocketreach-firmographic-enrichment")}'
        f'ROCKETREACH FIRMOGRAPHIC ENRICHMENT</{h_main}>'
    )

    # Opening blockquote — analyst-voice framing per dossier-template Rule 4.
    # Label kept to one of the documented sentinels (Why/Mitigation/Action/
    # Trigger/Watch for/Note/Key insight) so the markdown parser would
    # recognise it on round-trip. `Key insight` renders in the same cyan
    # md-callout-note palette as `Note`.
    parts.append(
        '<blockquote class="md-callout md-callout-note">'
        '<span class="md-callout-label">Key insight</span>'
        'Every field below is sourced from one billable '
        'RocketReach <code>/company/lookup</code> call — authoritative vendor data, '
        'independent of the free-OSINT inference that powered the rest of this dossier.'
        '</blockquote>'
    )

    # Contact + code key-value list (skip industry keywords / founded / HQ).
    kv_items: list[str] = []
    if rr_profile_url:
        kv_items.append(
            f'<li class="md-li-kv">'
            f'<span class="md-li-kv-key">RocketReach Profile</span>'
            f'<span class="md-li-kv-val">'
            f'<a href="{escape_html(rr_profile_url)}" target="_blank" rel="noopener">'
            f'{escape_html(rr_profile_url)}</a></span></li>'
        )
    if rr_company_phone:
        kv_items.append(
            f'<li class="md-li-kv">'
            f'<span class="md-li-kv-key">Company Phone</span>'
            f'<span class="md-li-kv-val">{escape_html(str(rr_company_phone))}</span></li>'
        )
    if rr_company_linkedin:
        kv_items.append(
            f'<li class="md-li-kv">'
            f'<span class="md-li-kv-key">Company LinkedIn</span>'
            f'<span class="md-li-kv-val">'
            f'<a href="{escape_html(rr_company_linkedin)}" target="_blank" rel="noopener">'
            f'{escape_html(rr_company_linkedin)}</a></span></li>'
        )
    if naics:
        kv_items.append(
            f'<li class="md-li-kv">'
            f'<span class="md-li-kv-key">NAICS</span>'
            f'<span class="md-li-kv-val">{escape_html(", ".join(map(str, naics[:5])))}</span></li>'
        )
    if sic:
        kv_items.append(
            f'<li class="md-li-kv">'
            f'<span class="md-li-kv-key">SIC</span>'
            f'<span class="md-li-kv-val">{escape_html(", ".join(map(str, sic[:5])))}</span></li>'
        )
    if kv_items:
        parts.append(f'<ul class="md-list">{"".join(kv_items)}</ul>')

    # Tech stack — prose list (comma-separated) under an H3
    if rr_techstack:
        top = rr_techstack[:60]
        more_suffix = f' … <em>and {len(rr_techstack) - 60} more</em>' if len(rr_techstack) > 60 else ''
        parts.append(
            f'<{h_sub} class="{h_sub_cls}" id="rr-tech-stack">'
            f'{_md_anchor("rr-tech-stack")}'
            f'Confirmed Tech Stack '
            f'<span style="font-weight:500;color:#6b7280">· {len(rr_techstack)} technologies</span>'
            f'</{h_sub}>'
        )
        parts.append(
            f'<p class="md-p">'
            f'{escape_html(", ".join(str(t) for t in top))}{more_suffix}'
            f'</p>'
        )

    # Department headcount + Workforce trajectory — collect into separate
    # cells, then emit side-by-side in a 2-column `.rr-tab2-pair` grid so
    # the section doesn't waste vertical real estate stacking a 9-row
    # dept table above a 2-row trajectory table. Responsive fallback:
    # stacks at <720px viewport.
    dept_cell_html = ''
    trend_cell_html = ''

    if depts and isinstance(depts, dict):
        rows: list[tuple[str, int]] = []
        for label, val in depts.items():
            if not label or label in ('unknown', ''):
                continue
            if isinstance(val, (int, float)):
                rows.append((str(label).replace('_', ' ').title(), int(val)))
            elif isinstance(val, dict):
                n = val.get('after') if isinstance(val.get('after'), (int, float)) else val.get('count')
                if isinstance(n, (int, float)):
                    rows.append((str(label).replace('_', ' ').title(), int(n)))
        if rows:
            rows.sort(key=lambda r: r[1], reverse=True)
            total = sum(r[1] for r in rows)
            head = (
                f'<{h_sub} class="{h_sub_cls}" id="rr-dept-headcount">'
                f'{_md_anchor("rr-dept-headcount")}'
                f'Department Headcount '
                f'<span style="font-weight:500;color:#6b7280">· {total} total across {len(rows)} departments</span>'
                f'</{h_sub}>'
            )
            tbl = ['<div class="md-table-wrap"><table class="md-table">'
                   '<thead><tr><th>Department</th><th style="text-align:right">Headcount</th></tr></thead><tbody>']
            for label, n in rows:
                tbl.append(
                    f'<tr><td>{escape_html(label)}</td>'
                    f'<td style="text-align:right;font-variant-numeric:tabular-nums">{n}</td></tr>'
                )
            tbl.append('</tbody></table></div>')
            dept_cell_html = head + ''.join(tbl)

    # Workforce trajectory — walk backward to find most-recent non-flat quarter
    if growth and isinstance(growth, list):
        latest = {}
        moves: list[tuple[str, int]] = []
        for entry in reversed(growth):
            if not isinstance(entry, dict):
                continue
            vals = entry.get('values') or {}
            cand: list[tuple[str, int]] = []
            for dept, m in (vals or {}).items():
                if not dept or dept in ('unknown', ''):
                    continue
                if isinstance(m, dict):
                    net = m.get('net')
                    if isinstance(net, (int, float)) and net != 0:
                        cand.append((str(dept).replace('_', ' ').title(), int(net)))
            if cand:
                latest = entry
                moves = cand
                break
        if moves:
            moves.sort(key=lambda r: r[1], reverse=True)
            qtr_label = f"{latest.get('year','?')} Q{latest.get('quarter','?')}"
            head = (
                f'<{h_sub} class="{h_sub_cls}" id="rr-trajectory">'
                f'{_md_anchor("rr-trajectory")}'
                f'Workforce Trajectory '
                f'<span style="font-weight:500;color:#6b7280">· {escape_html(qtr_label)}</span>'
                f'</{h_sub}>'
            )
            tbl = ['<div class="md-table-wrap"><table class="md-table">'
                   '<thead><tr><th>Department</th><th style="text-align:right">Net Change</th></tr></thead><tbody>']
            for dept, net in moves:
                arrow = '▲' if net > 0 else '▼'
                color = '#15803d' if net > 0 else '#b91c1c'
                tbl.append(
                    f'<tr><td>{escape_html(dept)}</td>'
                    f'<td style="text-align:right;color:{color};font-weight:700;'
                    f'font-variant-numeric:tabular-nums">{arrow} {abs(net)}</td></tr>'
                )
            tbl.append('</tbody></table></div>')
            trend_cell_html = head + ''.join(tbl)

    # Flush as side-by-side pair when both present; single-column fallback
    # keeps each standalone cell looking correct.
    if dept_cell_html and trend_cell_html:
        parts.append(
            f'<div class="rr-tab2-pair">'
            f'<div class="rr-tab2-pair-cell">{dept_cell_html}</div>'
            f'<div class="rr-tab2-pair-cell">{trend_cell_html}</div>'
            f'</div>'
        )
    elif dept_cell_html:
        parts.append(dept_cell_html)
    elif trend_cell_html:
        parts.append(trend_cell_html)

    return ''.join(parts)


def build_rr_person_extras(person):
    """v7.1.3 — append RocketReach-sourced contact rows to the Person Profile
    section. Surfaces linkedin_url, phone, rr_profile_url deep-link,
    social_links (github/twitter/facebook), location (city/state), and a
    one-line job-history summary — all marked with the ᴿᴿ pill so the rep
    sees at a glance which contact channels RR verified.

    Returns '' when none of the RR-sourced person fields are present, so
    legacy dossiers render without empty rows under Person Profile.
    """
    p = person or {}
    rows: list[str] = []

    def _field(label, value_html):
        return (
            f'<div class="field"><span class="field-label">{escape_html(label)}</span>'
            f'<span class="field-value">{value_html}</span></div>'
        )

    linkedin = p.get('linkedin_url')
    if linkedin:
        rows.append(_field(
            'LinkedIn',
            f'<a href="{escape_html(linkedin)}" target="_blank" rel="noopener" '
            f'style="color:#2563eb">{escape_html(linkedin)}</a>'
            + _rr_pill(p.get('_rocketreach_linkedin_url')),
        ))

    phone = p.get('phone')
    if phone:
        grade_tag = ''
        if p.get('email_grade'):
            grade_tag = f' <span class="field-tag tag-estimated">Grade {escape_html(p["email_grade"])}</span>'
        rows.append(_field(
            'Phone',
            escape_html(str(phone)) + _rr_pill(p.get('_rocketreach_phone')) + grade_tag,
        ))

    rr_profile = p.get('rr_profile_url')
    if rr_profile:
        rows.append(_field(
            'RocketReach Profile',
            f'<a href="{escape_html(rr_profile)}" target="_blank" rel="noopener" '
            f'style="color:#ff6b35;font-weight:600">View ↗</a>' + _RR_PILL_HTML,
        ))

    social = p.get('social_links') or {}
    if isinstance(social, dict) and social:
        icons = {
            'github': ('GitHub', '#0d1117'),
            'twitter': ('Twitter', '#1d9bf0'),
            'facebook': ('Facebook', '#1877f2'),
            'angellist': ('AngelList', '#333'),
            'aboutme': ('About.me', '#4575b4'),
            'youtube': ('YouTube', '#ff0000'),
        }
        links_html = ''
        for k, url in social.items():
            if k == 'linkedin':  # already shown above
                continue
            label, color = icons.get(k, (k.title(), '#475569'))
            links_html += (
                f'<a href="{escape_html(url)}" target="_blank" rel="noopener" '
                f'style="color:{color};text-decoration:none;margin-right:10px;'
                f'font-size:13px">{escape_html(label)} ↗</a>'
            )
        if links_html:
            rows.append(_field('Social', links_html + _rr_pill(p.get('_rocketreach_social_links'))))

    city = p.get('city')
    state = p.get('state')
    if city or state:
        loc = ', '.join(filter(None, [city, state, p.get('country')]))
        rows.append(_field('Location', escape_html(loc) + _RR_PILL_HTML))

    jh = p.get('job_history') or []
    if isinstance(jh, list) and jh:
        # Previous 3 roles summarized as "Title @ Employer"
        summary_bits = []
        for job in jh[:3]:
            if not isinstance(job, dict):
                continue
            t = job.get('title') or ''
            e = job.get('employer') or ''
            if t or e:
                summary_bits.append(f'{escape_html(t)} @ {escape_html(e)}')
        if summary_bits:
            rows.append(_field(
                'Career Path',
                ' · '.join(summary_bits) + _rr_pill(p.get('_rocketreach_job_history')),
            ))

    edu = p.get('education') or []
    if isinstance(edu, list) and edu:
        first = edu[0] if isinstance(edu[0], dict) else {}
        bits = []
        if first.get('degree'):
            bits.append(escape_html(str(first['degree'])))
        if first.get('institution'):
            bits.append(escape_html(str(first['institution'])))
        if bits:
            rows.append(_field(
                'Education',
                ', '.join(bits) + _rr_pill(p.get('_rocketreach_education')),
            ))

    skills = p.get('skills') or p.get('skills_rr') or []
    if isinstance(skills, list) and skills:
        pills = ''.join(
            f'<span class="tech-pill">{escape_html(str(s))}</span>'
            for s in skills[:8]
        )
        more = f' <span class="empty-inline">+{len(skills)-8} more</span>' if len(skills) > 8 else ''
        flag = p.get('_rocketreach_skills') or ('skills_rr' in p)
        rows.append(_field('Skills', pills + more + _rr_pill(flag)))

    return ''.join(rows)


def build_decision_tree(recommendations):
    """v6.2: Hand-rolled SVG flowchart for the first-call decision tree.
    Layout: a single trigger event diamond at the top branches into N
    horizontal "if-then-outcome" rows. Renders as inline SVG sized to the
    branch count so it scales cleanly on every viewport. Returns '' if no
    decision_tree object is present.
    """
    dt = (recommendations or {}).get('decision_tree', {}) or {}
    branches = dt.get('branches', []) or []
    branches = [b for b in branches if isinstance(b, dict) and (b.get('if') or b.get('then'))]
    if not branches:
        return ''

    trigger = dt.get('trigger_event', 'Trigger event')
    intro = dt.get('intro', '')
    kind_color = {
        'positive': '#22c55e',
        'ideal':    '#10b981',
        'compete':  '#f59e0b',
        'pivot':    '#8b5cf6',
        'negative': '#ef4444',
        'neutral':  '#6366f1',
    }

    # HTML/CSS-based flowchart — more accessible + responsive than raw SVG
    # for branching content with long text. The trunk and branch lines are
    # decorative borders/pseudo-elements styled in CSS.
    rows_html = ''
    for i, b in enumerate(branches):
        accent = kind_color.get(b.get('kind', 'neutral'), '#6366f1')
        cond = b.get('if', '')
        action = b.get('then', '')
        outcome = b.get('outcome', '')
        rows_html += f'''<div class="dt-row">
  <div class="dt-row-num" style="background:{accent}20;color:{accent}">{i+1}</div>
  <div class="dt-row-body">
    <div class="dt-cond" style="border-left-color:{accent}">
      <span class="dt-tag" style="background:{accent}20;color:{accent}">IF</span>
      <span class="dt-cond-text">{escape_html(cond)}</span>
    </div>
    <div class="dt-arrow" style="color:{accent}">↓</div>
    <div class="dt-action" style="border-color:{accent}40">
      <span class="dt-tag dt-tag-action" style="background:{accent};color:#fff">THEN</span>
      <span class="dt-action-text">{escape_html(action)}</span>
    </div>
    <div class="dt-outcome">
      <span class="dt-outcome-icon" style="color:{accent}">▸</span>
      <span class="dt-outcome-text">{escape_html(outcome)}</span>
    </div>
  </div>
</div>'''

    intro_html = f'<div class="dt-intro">{escape_html(intro)}</div>' if intro else ''
    return f'''<div class="dt-wrap">
  <div class="dt-trigger">
    <div class="dt-trigger-icon">▶</div>
    <div class="dt-trigger-body">
      <div class="dt-trigger-label">TRIGGER EVENT</div>
      <div class="dt-trigger-text">{escape_html(trigger)}</div>
    </div>
  </div>
  {intro_html}
  <div class="dt-branches">{rows_html}</div>
</div>'''


# =============================================================================
#  MAIN HTML TEMPLATE
# =============================================================================


def _rewrite_sources_section(md_text, sources_dict):
    """v7.1.5 — Rewrite Tab 2's RESEARCH SOURCES section into the bulleted-list
    style used by the canonical reference dossier.

    Input markdown commonly emits each category as a single dot-separated
    paragraph (e.g. ``**Person:** [link](url) [B] · [link](url) [B] · ...``).
    Tab 2 renders that as a wall of inline links — readable but hard to
    scan, and visually inconsistent with the Tab 1 source-quality donut.

    The reference dossier uses a per-category bulleted list with one bare
    URL per row + its tier badge. The renderer's auto-linkifier converts
    each row into ``<a class="md-link">URL ↗</a> <span class="md-tier-X">X</span>``
    automatically — no markdown-link syntax needed.

    This helper finds the ``## RESEARCH SOURCES`` section in `md_text` and
    rewrites it from ``sources_dict`` (the structured field that already
    feeds the Tab 1 donut). Counts always match the donut as a result.

    Returns the updated markdown (or the original unchanged if no
    structured sources are available, or no SOURCES heading is found).
    """
    if not md_text or not isinstance(sources_dict, dict) or not sources_dict:
        return md_text

    # Locate the SOURCES heading (## RESEARCH SOURCES, or any case variant).
    header_re = re.compile(
        r'^(#{2,3})\s*RESEARCH\s+SOURCES\s*$',
        re.IGNORECASE | re.MULTILINE,
    )
    m = header_re.search(md_text)
    if not m:
        return md_text

    section_start = m.start()
    header_end = m.end()

    # Find the next heading at the same level (or higher) to mark the
    # section's end.
    next_heading_re = re.compile(r'^#{1,3}\s', re.MULTILINE)
    next_match = next_heading_re.search(md_text, pos=header_end)
    section_end = next_match.start() if next_match else len(md_text)

    # Build the replacement section.
    out_lines = []
    out_lines.append(m.group(0))  # preserve original heading style
    out_lines.append('')
    out_lines.append(
        'Every URL below is tagged with its reliability tier. '
        '**A** = authoritative (gov filings, company press, .gov sites). '
        '**B** = reputable secondary (established press, primary LinkedIn '
        'profiles, RocketReach-verified contacts). '
        '**C** = aggregator / inferred (ZoomInfo, LeadIQ, analyst inference).'
    )
    out_lines.append('')

    cat_order = ['person', 'company', 'technology', 'financial', 'compliance']
    seen = set()
    ordered_keys = [k for k in cat_order if k in sources_dict] + [
        k for k in sources_dict.keys()
        if k not in cat_order and not seen.add(k)
    ]

    for cat in ordered_keys:
        urls = sources_dict.get(cat) or []
        if not urls:
            continue
        out_lines.append(f'**{cat.title()} ({len(urls)}):**')
        out_lines.append('')
        for entry in urls:
            if isinstance(entry, dict):
                url = entry.get('url', '')
                tier = (entry.get('tier') or 'C').upper()
            else:
                url = str(entry)
                tier = 'C'
            if not url:
                continue
            out_lines.append(f'- {url} [{tier}]')
        out_lines.append('')

    rewritten_section = '\n'.join(out_lines)
    return md_text[:section_start] + rewritten_section + md_text[section_end:]


def render_dossier_markdown(md_text):
    """
    Lightweight markdown-to-HTML renderer for the Complete Intelligence Dossier tab.
    Handles: headings (# to ####), bold (**text**), italic (*text*), tables (| a | b |),
    bullet lists (- item), numbered lists (1. item), horizontal rules (---), paragraphs,
    and line breaks. Escapes HTML by default. This is intentional and self-contained —
    we don't want a heavy dependency for a single rendering task.

    v5.7 additions:
      - Auto-link bare URLs in prose (http/https) → `<a target=_blank rel=noopener>`
      - Pill-style confidence/status tags: [CONFIRMED] [ESTIMATED] [INFERRED]
      - Badge-style source-tier markers: [A] [B] [C]
      - Anchor-link headings (slug-based id, click-to-copy affordance via title attr)
      - Better code/backtick rendering

    v6.2.1 addition:
      - Auto-strip ELISS internal version markers like "(v5.6+)", "(v6.1)",
        "(v6.2+)" from headings and inline bold tags. These are dev breadcrumbs
        from the SKILL.md template — they should never reach the customer-facing
        report, but analysts forget to remove them. Renderer now does it for them.
    """
    if not md_text:
        return '<p class="empty">No complete dossier provided.</p>'

    # v6.2.1 — strip ELISS internal version markers BEFORE rendering, so this
    # works regardless of whether the marker appears in a heading, an inline
    # bold span, or anywhere else. Pattern matches " (v5.6+)", "(v6.1)", "(v6.2+)"
    # — i.e. parenthesized 'v' + digits.digits + optional '+', preceded by 0+ spaces.
    md_text = re.sub(r'\s*\(v\d+\.\d+\+?\)', '', md_text)

    lines = md_text.replace('\r\n', '\n').split('\n')
    out = []
    i = 0
    in_list = None  # 'ul' or 'ol'
    in_table = False
    table_rows = []
    heading_counter = {}  # for disambiguating duplicate heading slugs

    def close_list():
        nonlocal in_list
        if in_list:
            out.append(f'</{in_list}>')
            in_list = None

    def close_table():
        nonlocal in_table, table_rows
        if in_table and table_rows:
            # First row is header, second row is separator (ignore), rest are body
            header = table_rows[0]
            body = table_rows[2:] if len(table_rows) > 2 else []
            out.append('<div class="md-table-wrap"><table class="md-table">')
            out.append('<thead><tr>' + ''.join(f'<th>{inline_md(c)}</th>' for c in header) + '</tr></thead>')
            if body:
                out.append('<tbody>')
                for row in body:
                    out.append('<tr>' + ''.join(f'<td>{inline_md(c)}</td>' for c in row) + '</tr>')
                out.append('</tbody>')
            out.append('</table></div>')
        in_table = False
        table_rows = []

    def slugify(text):
        # For heading anchors — lowercase, alphanumerics + hyphens only
        s = re.sub(r'<[^>]+>', '', text)  # strip any inline HTML that got through
        s = s.lower().strip()
        s = re.sub(r'[^a-z0-9\s\-]', '', s)
        s = re.sub(r'[\s\-]+', '-', s).strip('-')
        return s or 'section'

    def inline_md(text):
        """
        Inline markdown pass. v5.7 adds auto-linking, tier badges, and status pills.

        Order matters: escape first, then decorate. We apply auto-linking BEFORE
        anything else that could touch URL characters (e.g. parentheses in markdown
        link syntax) so our regex matches bare URLs cleanly.
        """
        # 1. Escape HTML special chars first — this also neutralizes any injected markup
        text = escape_html(text)

        # 2. v5.7 — Auto-link bare URLs in prose. Match http(s):// followed by non-space
        #    characters until we hit whitespace or end of input. Strip trailing punctuation
        #    that's almost certainly sentence-level (. , ; ) ] }), NOT part of the URL.
        def _linkify(match):
            url = match.group(0)
            trailing = ''
            # Pull off sentence-level punctuation — common pitfalls: "See x (at https://example.com)."
            while url and url[-1] in '.,;:)]}!?':
                trailing = url[-1] + trailing
                url = url[:-1]
            if not url:
                return match.group(0)
            return (
                f'<a class="md-link" href="{url}" target="_blank" rel="noopener" '
                f'title="{url}">{url}<span class="md-link-icon" aria-hidden="true">↗</span></a>'
                + trailing
            )
        # The `amp;` comes from earlier HTML-escape of `&`; keep the regex tolerant.
        text = re.sub(r'https?://[^\s<>"\']+', _linkify, text)

        # 3. Markdown links: [label](url) — supports standard markdown hyperlink syntax
        def _md_link(m):
            label = m.group(1)
            href = m.group(2)
            return (
                f'<a class="md-link" href="{href}" target="_blank" rel="noopener" '
                f'title="{href}">{label}<span class="md-link-icon" aria-hidden="true">↗</span></a>'
            )
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _md_link, text)

        # 4. v5.7 — Status pills: [CONFIRMED] [ESTIMATED] [INFERRED]
        pill_map = {
            'CONFIRMED': 'md-pill md-pill-confirmed',
            'ESTIMATED': 'md-pill md-pill-estimated',
            'INFERRED': 'md-pill md-pill-inferred',
        }
        def _pill(m):
            tag = m.group(1)
            cls = pill_map.get(tag, 'md-pill')
            return f'<span class="{cls}">{tag}</span>'
        text = re.sub(r'\[(CONFIRMED|ESTIMATED|INFERRED)\]', _pill, text)

        # 5. v5.7 — Source-tier badges: [A] [B] [C] — but only if they look like
        # standalone tags (preceded by whitespace or start-of-string, followed by
        # whitespace or end-of-string or common punctuation). This avoids false
        # positives on things like "[A]pple" in text.
        tier_map = {
            'A': ('md-tier md-tier-a', 'Tier A — Authoritative'),
            'B': ('md-tier md-tier-b', 'Tier B — Reputable secondary'),
            'C': ('md-tier md-tier-c', 'Tier C — Aggregator / inferred'),
        }
        def _tier(m):
            tag = m.group(1)
            cls, full = tier_map.get(tag, ('md-tier', ''))
            return f' <span class="{cls}" title="{full}">{tag}</span>'
        text = re.sub(r'(?<=[\s>])\[([ABC])\](?=[\s.,;:)]|$)', _tier, text)

        # 5b. v7.1 — RocketReach provenance marker. Convert the Unicode
        #   ᴿᴿ (U+1D3F × 2) glyph that appears after any RR-sourced value
        #   into an inline orange pill with a tooltip. The ::before CSS
        #   draws a plain "RR" text so the pill is readable even if the
        #   user's font doesn't include the superscript-R glyph.
        # v7.4.1 — strip a redundant literal "RR " (or "RR " inside parens)
        #   when it immediately precedes the ᴿᴿ glyph. Authors sometimes
        #   write "RR ᴿᴿ" or "(RR ᴿᴿ)" expecting it to read as labelled
        #   provenance, but the pill already carries an "RR" label so the
        #   prefix renders as a visible duplicate. This guard normalizes
        #   the source markdown before pill expansion. See
        #   `references/dossier-schema.md` § "RR provenance pill — DO NOT
        #   duplicate the label".
        text = re.sub(r'(?<![A-Za-z])RR (?=ᴿᴿ)', '', text)
        text = re.sub(r'(?<![A-Za-z])RR techstack (?=ᴿᴿ)', 'techstack ', text)
        text = re.sub(
            r'ᴿᴿ',
            '<span class="rr-pill" title="Sourced from RocketReach premium account (Tier-B, verified)"></span>',
            text,
        )

        # 6. Bold: **text**
        text = re.sub(r'\*\*([^\*]+)\*\*', r'<strong>\1</strong>', text)
        # 7. Italic: *text* (avoid conflicting with already-consumed bold)
        text = re.sub(r'(?<![\*])\*([^\*\n]+)\*(?![\*])', r'<em>\1</em>', text)
        # 8. Inline code: `text`
        text = re.sub(r'`([^`]+)`', r'<code class="md-code">\1</code>', text)
        return text

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Table detection: a line starting with | and containing another |
        if stripped.startswith('|') and stripped.count('|') >= 2:
            close_list()
            cells = [c.strip() for c in stripped.strip('|').split('|')]
            if not in_table:
                in_table = True
                table_rows = []
            table_rows.append(cells)
            i += 1
            continue
        else:
            if in_table:
                close_table()

        # Horizontal rule
        if stripped == '---' or stripped == '***':
            close_list()
            out.append('<hr class="md-hr">')
            i += 1
            continue

        # Blank line
        if not stripped:
            close_list()
            i += 1
            continue

        # Headings — v5.7: attach slug-based id for anchor linking
        m = re.match(r'^(#{1,4})\s+(.*)$', stripped)
        if m:
            close_list()
            level = len(m.group(1))
            # We bump all heading levels down by 1 because the tab itself has an h2
            tag = f'h{min(level + 1, 5)}'
            heading_text = m.group(2)
            slug = slugify(heading_text)
            # Disambiguate duplicate slugs
            if slug in heading_counter:
                heading_counter[slug] += 1
                slug = f'{slug}-{heading_counter[slug]}'
            else:
                heading_counter[slug] = 1
            out.append(
                f'<{tag} class="md-h{level}" id="{slug}">'
                f'<a class="md-anchor" href="#{slug}" aria-label="Link to this section" '
                f'title="Copy link to this section">#</a>'
                f'{inline_md(heading_text)}</{tag}>'
            )
            i += 1
            continue

        # Blockquote: lines starting with "> " become a styled callout
        if stripped.startswith('>'):
            close_list()
            bq_lines = []
            while i < len(lines) and lines[i].strip().startswith('>'):
                bq_lines.append(lines[i].strip().lstrip('>').strip())
                i += 1
            body = inline_md(' '.join(l for l in bq_lines if l))
            out.append(f'<blockquote class="md-blockquote"><p>{body}</p></blockquote>')
            continue

        # Bullet list — with key-value row detection
        m = re.match(r'^[\-\*]\s+(.*)$', stripped)
        if m:
            if in_list != 'ul':
                close_list()
                out.append('<ul class="md-list">')
                in_list = 'ul'
            item_text = m.group(1)
            # Key-value pattern: "**Label:** value..." → grid row with colored label
            kv = re.match(r'^\*\*([^:\*]{1,40}):\*\*\s+(.+)$', item_text)
            if kv:
                key = inline_md(kv.group(1).strip())
                val = inline_md(kv.group(2).strip())
                out.append(
                    f'<li class="md-li-kv"><span class="md-li-kv-key">{key}</span>'
                    f'<span class="md-li-kv-val">{val}</span></li>'
                )
            else:
                out.append(f'<li>{inline_md(item_text)}</li>')
            i += 1
            continue

        # Numbered list
        m = re.match(r'^\d+\.\s+(.*)$', stripped)
        if m:
            if in_list != 'ol':
                close_list()
                out.append('<ol class="md-list">')
                in_list = 'ol'
            out.append(f'<li>{inline_md(m.group(1))}</li>')
            i += 1
            continue

        # Plain paragraph — collect consecutive non-blank, non-special lines
        close_list()
        para_lines = [stripped]
        j = i + 1
        while j < len(lines):
            nxt = lines[j].strip()
            if (not nxt
                    or nxt.startswith('#')
                    or nxt.startswith('|')
                    or nxt.startswith('>')
                    or nxt == '---'
                    or re.match(r'^[\-\*]\s+', nxt)
                    or re.match(r'^\d+\.\s+', nxt)):
                break
            para_lines.append(nxt)
            j += 1
        joined = ' '.join(para_lines)

        # Callout detection — paragraph opens with a known labelled sentinel.
        # Maps the label to an accent kind so the CSS can colour-code it.
        # Labels are case-insensitive and trimmed.
        CALLOUT_KIND = {
            'why': 'why', 'why it shifts': 'why', 'why it could happen': 'why',
            'mitigation': 'mitigation', 'resolution': 'mitigation',
            'action': 'action', 'next step': 'action', 'next steps': 'action',
            'trigger': 'trigger', 'trigger to watch': 'trigger',
            'earliest signal': 'trigger', 'earliest signal to watch for': 'trigger',
            'watch for': 'watch', 'risk': 'watch',
            'note': 'note', 'key insight': 'note', 'insight': 'note',
        }
        co = re.match(r'^\*\*([^:\*]{1,80}):\*\*\s+(.+)$', joined)
        # Two-tier label resolution: exact match first, then first-alpha-word
        # fallback. The fallback lets verbose labels like "Why this is HOT now"
        # or "Mitigation for the multi-incumbent lock-in" still render as their
        # intended callout kind (`why` / `mitigation`) — the analyst writes
        # naturally without memorising the exact alias list. Strict labels
        # already in CALLOUT_KIND keep their existing behaviour.
        kind = None
        if co:
            label_lc = co.group(1).strip().lower()
            kind = CALLOUT_KIND.get(label_lc)
            if not kind:
                # First-word fallback: require the first word to be followed by
                # whitespace (not punctuation/hyphen) before the rest of the label.
                # This lets "Why this is HOT now" match `why` while keeping
                # "Risk-Adjusted Composite" out (it's a header line, not a Risk
                # callout — the hyphen would otherwise let "risk" match).
                first_word_m = re.match(r'^([a-z]+)\s', label_lc)
                if first_word_m:
                    kind = CALLOUT_KIND.get(first_word_m.group(1))
        if co and kind:
            label = co.group(1).strip()
            body = inline_md(co.group(2).strip())
            out.append(
                f'<div class="md-callout md-callout-{kind}">'
                f'<span class="md-callout-label">{label}</span>{body}</div>'
            )
        else:
            out.append(f'<p class="md-p">{inline_md(joined)}</p>')
        i = j

    close_list()
    close_table()
    return '\n'.join(out)


def generate_html_report(data, peer_scores=None):
    """Generate the full HTML report from structured JSON data."""
    scoring = data.get('scoring', {})
    lead = data.get('lead', {})
    company = data.get('company', {})
    tech = data.get('technology', {})
    budget = data.get('budget_analysis', {})
    meta = data.get('meta', {})
    signals = data.get('signals', {})
    compliance = data.get('compliance', [])
    org = data.get('org_intelligence', {})
    recs = data.get('recommendations', {})
    dq = data.get('data_quality', {})
    sources = data.get('sources', {})

    tier = scoring.get('tier', 'WARM')
    tc = TIER_CONFIG.get(tier, TIER_CONFIG['WARM'])
    conf = scoring.get('overall_confidence', 'MEDIUM')
    cc = CONF_CONFIG.get(conf, CONF_CONFIG['MEDIUM'])
    final_score = scoring.get('final_score', scoring.get('composite', 0))

    # Build dimension bars
    dims_html = ''
    for dim_key, dim_label, max_s in [('fit', 'Fit', 25), ('intent', 'Intent', 25), ('timing', 'Timing', 30), ('budget', 'Budget', 20)]:
        dim_data = scoring.get(dim_key, {})
        s = dim_data.get('score', 0) if isinstance(dim_data, dict) else 0
        c = dim_data.get('confidence', 'MEDIUM') if isinstance(dim_data, dict) else 'MEDIUM'
        dims_html += svg_dimension_bar(dim_label, s, max_s, DIM_COLORS[dim_key], c)

    # ICP match
    icp_match = scoring.get('icp_match', 'Unknown')
    icp_reason = scoring.get('icp_match_reason', '')
    icp_color = '#22c55e' if icp_match == 'Strong' else '#f59e0b' if icp_match == 'Moderate' else '#6b7280'

    # Tech pills
    tech_stack = tech.get('security_stack', [])
    tech_pills = ''.join(f'<span class="tech-pill">{escape_html(t)}</span>' for t in tech_stack) if tech_stack else '<span class="empty-inline">None detected</span>'
    competitors = tech.get('competitors_detected', [])
    comp_pills = ''.join(f'<span class="comp-pill">{escape_html(c)}</span>' for c in competitors) if competitors else '<span class="empty-inline">None detected</span>'

    # v7.1.3 — RocketReach-sourced firmographic fallbacks. The v7.1.2 baseline
    # pass writes `num_employees`, `revenue` (int), `industry_rr`, `description_rr`
    # into the company section but the pre-existing Tab 1 template keyed off the
    # legacy fields (`employees`, `revenue_estimate`, `industry`, `description`)
    # and silently ignored the RR keys. Here we resolve the display value by
    # checking the legacy slot first, falling back to the RR slot. The ᴿᴿ pill
    # only fires when we actually rendered the RR value — attributing it to a
    # Claude-sourced legacy number would lie about provenance. (The RR-specific
    # values are also surfaced separately in the RocketReach Firmographic
    # Enrichment section below so the rep can compare Claude-inferred vs.
    # RR-authoritative when they differ.)
    def _pick(legacy, rr):
        # Inputs may be bare strings, ints (employees/revenue), structured-value
        # dicts ({value, confidence, tier, ...} for industry/title), or None.
        # Unwrap with _extract_value so dict inputs render their `.value` instead
        # of leaking as a Python repr through escape_html(str(dict)).
        legacy_v = _extract_value(legacy)
        if legacy_v not in ('', 'Unknown'):
            return escape_html(legacy_v)   # Claude-sourced — no pill
        rr_v = _extract_value(rr)
        if rr_v not in ('', 'Unknown'):
            return escape_html(rr_v) + _RR_PILL_HTML
        return ''

    employees_display = _pick(
        company.get('employees'),
        company.get('num_employees'),
    ) or 'Unknown'
    revenue_display = _pick(
        company.get('revenue_estimate'),
        _format_rr_revenue(company.get('revenue')),
    ) or 'Unknown'
    industry_display = _pick(
        company.get('industry'),
        company.get('industry_rr'),
    ) or ''

    # Sources — v5.6: support both legacy flat strings AND new {url, tier} dicts
    TIER_BADGE = {
        'A': {'bg': 'rgba(34,197,94,0.15)', 'color': '#22c55e', 'label': 'A'},
        'B': {'bg': 'rgba(245,158,11,0.15)', 'color': '#f59e0b', 'label': 'B'},
        'C': {'bg': 'rgba(107,114,128,0.15)', 'color': '#9ca3af', 'label': 'C'},
    }
    def render_source_entry(entry):
        if isinstance(entry, dict):
            u = entry.get('url', '')
            tier = entry.get('tier', 'C')
            tb = TIER_BADGE.get(tier, TIER_BADGE['C'])
            tier_html = (f'<span class="src-tier" style="background:{tb["bg"]};color:{tb["color"]};'
                         f'display:inline-block;padding:1px 6px;border-radius:4px;font-size:10px;'
                         f'font-weight:700;margin-right:4px">{tb["label"]}</span>')
        else:
            u = str(entry)
            tier_html = ''
        # v6.1: Truncate display text with an explicit ellipsis when shortened.
        # Previously: u[:60] silently chopped the trailing path with no visual
        # cue, making fully-formed URLs look broken (e.g. ".../jobs/newprint"
        # instead of ".../jobs/newprint/4786486"). The href still carries the
        # full URL — only the link's visible text is shortened.
        u_disp = u if len(u) <= 60 else u[:57] + '…'
        return f'{tier_html}<a href="{escape_html(u)}" target="_blank">{escape_html(u_disp)}</a>'

    sources_html = ''
    for cat, urls in sources.items():
        if urls:
            sources_html += f'<div class="source-cat"><strong>{cat.title()}:</strong> '
            sources_html += ', '.join(render_source_entry(e) for e in urls)
            sources_html += '</div>'

    # Data quality
    assumptions_html = ''.join(f'<li>{escape_html(a)}</li>' for a in dq.get('assumptions', []))
    gaps_html = ''.join(f'<li>{escape_html(g)}</li>' for g in dq.get('gaps', []))

    # Complete Intelligence Dossier (verbatim markdown rendered to HTML)
    full_dossier_md = data.get('full_dossier_markdown', '')

    # v7.1.5 — Rewrite Tab 2 RESEARCH SOURCES from the structured `sources`
    # field into a bulleted-list format that matches the Best-dossier style.
    # The original markdown style (single dot-separated paragraph per
    # category) renders as a wall of inline links that's hard to scan; the
    # bulleted-list style auto-linkifies each URL on its own row with its
    # tier badge, matching the Tab 1 Source Quality donut's structure.
    # The structured `data['sources']` is the source of truth — counts will
    # always match the donut, and we don't have to parse possibly-stale
    # markdown.
    full_dossier_md = _rewrite_sources_section(full_dossier_md, data.get('sources') or {})

    # v5.5: Auto-correct stale version stamps in the dossier markdown so Tab 2
    # always matches the current analyst version, even if the markdown was
    # generated before a version bump.
    # v7.1.1 — Always normalize Tab 2's analyst tag to the current display
    # version, regardless of what meta.analyst / meta.version say in the
    # dossier JSON. This keeps any legacy `ELISS v6.1` / `ELISS v7.0.0` stamps
    # in older dossiers uniform with the header + footer on re-render.
    current_analyst = f'ELISS v{ELISS_DISPLAY_VERSION}'
    # v6.2.4 — Single regex instead of iterative string replace.
    # The previous iterative approach (walk a list of old versions, str.replace each)
    # silently doubled the version when the replacement contained a substring that
    # matched an earlier iteration: replacing "ELISS v6.1" with "ELISS v6.2.3"
    # produced "ELISS v6.2.3", then the NEXT iteration's "ELISS v6.2" matched the
    # "ELISS v6.2" inside "ELISS v6.2.3" and replaced with "ELISS v6.2.3", yielding
    # "ELISS v6.2.3.3". The regex matches any ELISS version stamp in one pass
    # and replaces the entire match — no iteration artifact possible.
    # Pattern: literal "ELISS v" + digits + zero or more ".digits" segments.
    full_dossier_md = re.sub(r'ELISS v\d+(?:\.\d+)+', current_analyst, full_dossier_md)
    full_dossier_html = render_dossier_markdown(full_dossier_md) if full_dossier_md else (
        '<div class="md-empty">'
        '<strong>Complete Intelligence Dossier not provided.</strong><br>'
        'The JSON dossier is missing the <code>full_dossier_markdown</code> field. '
        'ELISS v5.1+ populates this automatically — re-run the analyst step to include it.'
        '</div>'
    )

    # v7.1.4 — Tab 2 gets a MARKDOWN-STYLED rendering of the same RR data
    # instead of the Tab-1 champagne infographic card. Tab 2 is a prose
    # surface (h2/h3, key-value bullets, md-tables, callouts); dropping a
    # card in with its own palette + chips looks like a UI transplant. The
    # dedicated Tab-2 builder emits the data through the same md-* classes
    # the rest of Tab 2 uses. Per v7.1.4 review, Industry Keywords / Founded /
    # HQ are excluded from the Tab-2 variant — prose readers don't need
    # that metadata here (it's already upstream in the Company Profile
    # markdown) and the keyword pills were visual noise in a text surface.
    #
    # Placement: the section is spliced in immediately AFTER the COMPANY
    # PROFILE section (i.e., right before the H2 that follows Company
    # Profile). If the markdown doesn't contain a Company Profile header —
    # legacy dossier, custom template, or the section was renamed — we fall
    # back to prepending so the data still appears somewhere visible.
    _rr_enrich_tab2 = build_rocketreach_enrichment_tab2(data, data_level_hint=full_dossier_html)
    if _rr_enrich_tab2:
        # Heading level varies by dossier. The v7.1.2 template uses `##`/h2
        # for sections, but some analyst outputs end up with `###`/h3 when the
        # dossier has a single top-level `#`/h2 title above. Detect the level
        # that COMPANY PROFILE uses and match the next heading at the same or
        # higher rank. The anchor `#` link the renderer injects into every
        # heading means the COMPANY PROFILE match has to look past an
        # optional inline <a class="md-anchor">...</a>.
        _cp_header_match = re.search(
            r'<h([234])\b[^>]*>\s*(?:<a\b[^<]*</a>)?\s*COMPANY\s+PROFILE',
            full_dossier_html, flags=re.IGNORECASE,
        )
        inserted = False
        if _cp_header_match:
            cp_level = int(_cp_header_match.group(1))
            cp_end = _cp_header_match.end()
            # Find the next heading at the same or higher rank (h1..cp_level)
            next_head = re.search(
                rf'<h[1-{cp_level}]\b',
                full_dossier_html[cp_end:],
            )
            if next_head:
                splice_at = cp_end + next_head.start()
                full_dossier_html = (
                    full_dossier_html[:splice_at]
                    + _rr_enrich_tab2
                    + full_dossier_html[splice_at:]
                )
                inserted = True
            else:
                full_dossier_html = full_dossier_html + _rr_enrich_tab2
                inserted = True
        if not inserted:
            full_dossier_html = _rr_enrich_tab2 + full_dossier_html

    # Peer benchmark (only rendered if we have peers)
    peer_html = ''
    if peer_scores:
        peer_html = f'''
  <div class="section">
    <div class="section-title">Pipeline Benchmark</div>
    {svg_peer_benchmark(final_score, peer_scores)}
    <div class="peer-note">Comparison based on {len(peer_scores)} previously scored leads in your pipeline.</div>
  </div>'''

    # ICP color conversion for CSS variable
    try:
        icp_rgb = ",".join(str(int(icp_color[i:i+2], 16)) for i in (1, 3, 5))
    except ValueError:
        icp_rgb = "107,114,128"

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ELISS Dossier — {escape_html(lead.get('name', 'Unknown'))} @ {escape_html(company.get('name', 'Unknown'))}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',system-ui,sans-serif;background:#080c14;color:#e2e8f0;line-height:1.6;min-height:100vh}}
.page{{max-width:980px;margin:0 auto;padding:32px 24px}}

/* Header */
.report-header{{background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);border:1px solid rgba(99,102,241,0.2);border-radius:20px;padding:36px 40px;margin-bottom:16px;position:relative;overflow:hidden}}
.report-header::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:{tc['gradient']}}}
.header-brand{{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}}
.brand-mark{{font-size:10px;text-transform:uppercase;letter-spacing:4px;color:#6366f1;font-weight:700}}
.header-date{{font-size:12px;color:#94a3b8}}
.lead-name{{font-size:30px;font-weight:800;letter-spacing:-0.5px;margin-bottom:4px}}
.lead-sub{{font-size:14px;color:#94a3b8}}

/* Verdict Banner — the 5-second read */
.verdict-banner{{display:flex;align-items:stretch;border-radius:16px;overflow:hidden;margin-bottom:24px;min-height:100px}}
.verdict-tier-pill{{min-width:120px;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:14px 18px;color:#fff;flex-shrink:0}}
.verdict-score{{font-size:36px;font-weight:900;line-height:1;letter-spacing:-1px}}
.verdict-tier{{font-size:11px;font-weight:700;letter-spacing:2px;margin-top:6px;opacity:0.95}}
.verdict-body{{flex:1;padding:18px 22px;min-width:0}}
.verdict-headline{{font-size:15px;font-weight:600;color:#e2e8f0;line-height:1.45;margin:0 0 8px 0;display:block}}
.verdict-insight{{font-size:13px;color:#94a3b8;line-height:1.55;margin:0 0 8px 0;display:block}}
.verdict-next{{font-size:12px;color:#818cf8;font-weight:600;line-height:1.5;margin:0;display:block}}

/* Score Hero with radar + gauge */
.score-hero{{background:#0f172a;border:1px solid #1e293b;border-radius:16px;padding:24px;margin-bottom:16px}}
.score-hero-top{{display:grid;grid-template-columns:auto auto 1fr;gap:20px;align-items:center;margin-bottom:16px}}
.score-visual{{text-align:center}}
.score-radar{{text-align:center;padding:0 4px}}
.score-radar-label{{font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:#94a3b8;margin-top:4px;font-weight:600}}
.score-meta{{display:flex;flex-direction:column;gap:10px;min-width:0}}
.score-dim-section{{border-top:1px solid rgba(255,255,255,0.06);padding-top:16px}}
/* Badge pills (tier, confidence, ICP) — unified sizing so they sit on a single
   baseline. Visual hierarchy comes from color weight + bold on the tier, not
   from different paddings. All three share height, border-radius, alignment. */
.tier-label,.conf-label,.icp-label{{display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:6px 14px;border-radius:999px;font-size:11.5px;font-weight:600;letter-spacing:0.5px;line-height:1;white-space:nowrap;height:28px;box-sizing:border-box;width:fit-content;vertical-align:middle}}
.tier-label{{background:{tc['bg']};color:{tc['color']};font-weight:700;letter-spacing:1.5px;font-size:12px}}
.conf-label{{background:{cc['bg']};color:{cc['color']}}}
.icp-label{{background:rgba({icp_rgb},0.12);color:{icp_color}}}
.icp-reason{{font-size:12px;color:#94a3b8;line-height:1.5}}
.dim-bars{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}
.dim-row{{display:flex;flex-direction:column;gap:4px}}
.dim-header{{display:flex;justify-content:space-between;align-items:baseline}}
.dim-name{{font-size:11px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:1px}}
.dim-score{{font-size:14px;font-weight:700}}
.dim-max{{font-size:11px;font-weight:400;color:#94a3b8}}
.dim-track{{height:6px;border-radius:3px;background:rgba(255,255,255,0.06);overflow:hidden}}
.dim-fill{{height:100%;border-radius:3px;transition:width 0.8s ease}}
.dim-conf{{font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;margin-top:2px}}
.neg-mods{{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}}
.neg-tag{{font-size:11px;padding:3px 10px;background:rgba(239,68,68,0.1);color:#ef4444;border-radius:12px;font-weight:500}}

/* Validation rules block */
.validation-list{{display:flex;flex-direction:column;gap:8px}}
.val-rule{{padding:10px 14px;background:rgba(255,255,255,0.02);border-radius:0 8px 8px 0;font-size:13px;display:flex;gap:12px;align-items:center}}
.val-tag{{font-size:10px;font-weight:700;letter-spacing:1px;padding:3px 8px;border-radius:6px;white-space:nowrap}}
.val-desc{{color:#94a3b8;font-size:13px}}
.validation-clean{{padding:12px 16px;background:rgba(34,197,94,0.06);border-left:3px solid #22c55e;border-radius:0 8px 8px 0;color:#86efac;font-size:13px;font-weight:500}}

/* Sections */
.section{{background:#0f172a;border:1px solid #1e293b;border-radius:16px;padding:24px 28px;margin-bottom:16px}}
.section-title{{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:#6366f1;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid #1e293b}}

/* Executive Brief */
.exec-brief{{font-size:15px;line-height:1.75;color:#cbd5e1;background:rgba(99,102,241,0.04);border-left:3px solid #6366f1;padding:14px 18px;border-radius:0 8px 8px 0}}

/* Profile fields */
.field-grid{{display:grid;grid-template-columns:1fr 1fr;gap:4px 20px}}
.field{{display:flex;gap:8px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.04);align-items:baseline}}
.field-label{{font-size:11px;font-weight:600;color:#94a3b8;min-width:100px;text-transform:uppercase;letter-spacing:0.5px;flex-shrink:0}}
.field-value{{font-size:13px;color:#e2e8f0}}
.field-tag{{font-size:9px;font-weight:600;padding:1px 6px;border-radius:4px;margin-left:4px;vertical-align:middle}}
.tag-confirmed{{background:rgba(34,197,94,0.12);color:#22c55e}}
.tag-estimated{{background:rgba(245,158,11,0.12);color:#f59e0b}}
.tag-inferred{{background:rgba(59,130,246,0.12);color:#3b82f6}}

/* Tech pills */
.tech-pill{{display:inline-block;font-size:11px;padding:3px 10px;background:rgba(99,102,241,0.1);color:#818cf8;border-radius:10px;margin:2px 4px 2px 0;font-weight:500}}
.comp-pill{{display:inline-block;font-size:11px;padding:3px 10px;background:rgba(239,68,68,0.1);color:#ef4444;border-radius:10px;margin:2px 4px 2px 0;font-weight:500}}
.empty-inline{{font-size:12px;color:#475569;font-style:italic}}

/* Intent donut */
.donut-wrap{{display:flex;gap:24px;align-items:center;justify-content:center;flex-wrap:wrap}}
.donut-legend{{display:flex;flex-direction:column;gap:6px;min-width:200px}}
.donut-row{{display:flex;gap:10px;align-items:center;font-size:12px}}
.donut-swatch{{width:10px;height:10px;border-radius:2px;flex-shrink:0}}
.donut-label{{flex:1;color:#cbd5e1}}
.donut-val{{font-weight:700;color:#22c55e}}

/* Compliance heatmap */
.heatmap{{display:flex;flex-direction:column;gap:10px}}
.heatmap-row{{display:grid;grid-template-columns:160px 110px 1fr 1fr;gap:10px;align-items:stretch;background:rgba(255,255,255,0.02);border-radius:10px;padding:12px}}
.heatmap-framework{{display:flex;flex-direction:column;gap:4px;justify-content:center}}
.heatmap-name{{font-size:15px;font-weight:700;color:#e2e8f0}}
.heatmap-urgency{{font-size:10px;color:#94a3b8;font-weight:500}}
.heatmap-pressure{{display:flex;align-items:center;justify-content:center;gap:6px;font-size:11px;font-weight:700;letter-spacing:0.5px;border-radius:8px;padding:4px 8px}}
.heatmap-dot{{width:8px;height:8px;border-radius:50%;display:inline-block}}
.heatmap-cell{{padding:8px 10px;background:rgba(255,255,255,0.02);border-radius:6px}}
.heatmap-cell-label{{font-size:9px;font-weight:700;letter-spacing:1px;color:#94a3b8;margin-bottom:2px}}
.heatmap-cell-text{{font-size:12px;color:#cbd5e1;line-height:1.4}}

/* Timeline */
.timeline-empty{{padding:20px;text-align:center;color:#475569;font-style:italic;font-size:13px}}

/* Waterfall */
.waterfall-empty{{padding:20px;text-align:center;color:#475569;font-style:italic;font-size:13px}}
.waterfall-warning{{padding:12px 16px;margin:0 0 12px 0;background:rgba(245,158,11,0.12);border-left:4px solid #f59e0b;border-radius:4px;color:#92400e;font-size:12px;line-height:1.5}}
.waterfall-warning code{{background:rgba(245,158,11,0.18);padding:1px 6px;border-radius:3px;font-size:11px;font-family:ui-monospace,Menlo,monospace}}

/* Signals list */
.signal-item{{padding:12px;border-radius:8px;margin-bottom:8px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.04)}}
.signal-positive{{border-left:3px solid #22c55e}}
.signal-negative{{border-left:3px solid #ef4444}}
.signal-main{{display:flex;gap:8px;align-items:center;margin-bottom:4px}}
.signal-badge{{font-size:11px;font-weight:700;padding:2px 8px;border-radius:8px}}
.signal-text{{font-size:13px;font-weight:500}}
.signal-meta{{font-size:11px;color:#94a3b8;display:flex;gap:12px}}
.signal-age{{color:#94a3b8}}
.conf-tag{{font-weight:600;font-size:10px;text-transform:uppercase}}
.net-assessment{{margin-top:12px;padding:12px;background:rgba(99,102,241,0.04);border-radius:8px;font-size:13px;color:#94a3b8}}
h3{{font-size:12px;font-weight:600;color:#94a3b8;margin:14px 0 8px;text-transform:uppercase;letter-spacing:0.5px}}

/* v5.6: Competitive Threat Matrix + Readiness */
.readiness-row{{display:flex;gap:16px;align-items:stretch;margin-bottom:16px}}
.readiness-badge{{flex:0 0 auto;padding:16px 20px;border-radius:12px;border:1px solid;text-align:center;min-width:120px;display:flex;flex-direction:column;justify-content:center}}
.readiness-num{{font-size:32px;font-weight:700;line-height:1}}
.readiness-denom{{font-size:16px;opacity:0.6;font-weight:500}}
.readiness-label{{font-size:11px;text-transform:uppercase;letter-spacing:0.5px;margin-top:4px;opacity:0.85}}
.readiness-basis{{flex:1;padding:14px 16px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.04);border-radius:10px}}
.readiness-basis-title{{font-size:11px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px}}
.readiness-basis-text{{font-size:13px;color:#cbd5e1;line-height:1.5}}
.likelihood-badge,.threat-badge{{display:inline-block;padding:3px 8px;border-radius:5px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.4px;white-space:nowrap}}
.threat-badge{{letter-spacing:0.3px}}
.comp-matrix-wrap{{margin-top:8px}}

/* v6.1 — Global .md-table base styling.
   Previously the comprehensive .md-table rules (width, header background,
   vertical-align:top, padding, zebra striping) were ALL scoped to
   `.dossier-verbatim .md-table` (Tab 2 only). The Tab-1 instances
   (.comp-matrix and .der-table) inherited NONE of those rules and
   rendered as naked HTML tables — no width:100%, no header bg, cells
   defaulting to vertical-align:middle. Result: headers and tall body
   cells (long basis text) didn't share a baseline, and the table didn't
   fill its wrapper. The dossier-verbatim selectors keep their higher
   specificity so the Tab 2 rules continue to win where they apply. */
.md-table-wrap{{overflow-x:auto;margin:8px 0 12px 0;border:1px solid #1e293b;border-radius:8px;-webkit-overflow-scrolling:touch}}
.md-table{{width:100%;border-collapse:separate;border-spacing:0;font-size:12.5px;margin:0}}
.md-table th{{background:#1e293b;color:#e2e8f0;font-weight:700;text-align:left;padding:10px 12px;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;border-bottom:1px solid #334155;vertical-align:top}}
.md-table td{{padding:10px 12px;color:#cbd5e1;border-bottom:1px solid #1e293b;vertical-align:top}}
.md-table tbody tr:nth-child(even) td{{background:rgba(99,102,241,0.04)}}
.md-table tbody tr:hover td{{background:rgba(99,102,241,0.10)}}
.md-table tr:last-child td{{border-bottom:none}}

/* Competitive Threat Matrix: explicit column-width hints with
   table-layout:fixed so the Competitor column can't blow out wide for
   one long competitor name (e.g. "Native Microsoft AD tooling (ADUC,
   ADAC, PowerShell)") and crush the rest of the row out of header
   alignment. White-space:nowrap removed for the same reason — long
   competitor names now wrap onto a second line within their column.

   v6.1.1: Threat column widened from 10% to 14% to fit "🔴 Critical"
   badge (which carries white-space:nowrap and needs ~86px). At 10%
   (~76px on a 760px page) the badge overflowed its cell and forced
   the .md-table-wrap to engage horizontal scroll. Also allowed the
   likelihood + threat badges to wrap inside their cells as a defense
   in depth so a future longer label can't re-break the layout. */
.comp-matrix{{table-layout:fixed}}
.comp-matrix th:nth-child(1),.comp-matrix td:nth-child(1){{width:17%}}
.comp-matrix th:nth-child(2),.comp-matrix td:nth-child(2){{width:11%}}
.comp-matrix th:nth-child(3),.comp-matrix td:nth-child(3){{width:30%}}
.comp-matrix th:nth-child(4),.comp-matrix td:nth-child(4){{width:28%}}
.comp-matrix th:nth-child(5),.comp-matrix td:nth-child(5){{width:14%}}
.comp-matrix td.ct-competitor{{font-size:12.5px;line-height:1.35;font-weight:600;word-break:normal;overflow-wrap:break-word}}
.comp-matrix td.ct-basis,.comp-matrix td.ct-angle{{font-size:12px;line-height:1.4}}
/* Allow badges to wrap inside the comp-matrix when a label is wider
   than its cell. Without this override, .likelihood-badge and
   .threat-badge inherit the global white-space:nowrap and silently
   overflow their <td>, forcing a horizontal scroller on the wrapper. */
.comp-matrix .likelihood-badge,.comp-matrix .threat-badge{{white-space:normal;text-align:center;max-width:100%;box-sizing:border-box}}

/* v5.6: Ghost Stakeholders */
.ghost-card{{margin-bottom:12px;padding:14px 16px;background:rgba(139,92,246,0.04);border:1px solid rgba(139,92,246,0.18);border-radius:10px;border-left:3px solid #8b5cf6}}
.ghost-card-header{{display:flex;gap:12px;align-items:center;margin-bottom:10px;flex-wrap:wrap}}
.ghost-icon{{font-size:20px}}
.ghost-role{{font-size:14px;font-weight:600;color:#e2e8f0}}
.ghost-meta{{display:flex;gap:8px;margin-left:auto;flex-wrap:wrap}}
.ghost-status,.ghost-arrival{{font-size:11px;padding:2px 8px;border-radius:5px;background:rgba(139,92,246,0.12);color:#c4b5fd;font-weight:500}}
.ghost-body{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.ghost-field-label{{font-size:10px;font-weight:600;color:#8b5cf6;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:3px}}
.ghost-field-text{{font-size:12px;color:#cbd5e1;line-height:1.45}}
.ghost-risk .ghost-field-label{{color:#f59e0b}}
.ghost-opp .ghost-field-label{{color:#22c55e}}
.ghost-action{{grid-column:1/-1;padding-top:8px;border-top:1px dashed rgba(139,92,246,0.18)}}
.ghost-action .ghost-field-label{{color:#22d3ee}}
.ghost-empty{{padding:16px;background:rgba(255,255,255,0.02);border:1px dashed rgba(255,255,255,0.1);border-radius:8px;font-size:13px;color:#94a3b8;line-height:1.5}}

/* v5.6: Deal Execution Risks + Risk-Adjusted Composite */
.risk-adjusted-strip{{display:flex;align-items:center;gap:14px;padding:12px 16px;background:rgba(245,158,11,0.05);border:1px solid rgba(245,158,11,0.2);border-radius:10px;margin-bottom:14px}}
.ras-cell{{display:flex;flex-direction:column;gap:2px}}
.ras-label{{font-size:10px;text-transform:uppercase;letter-spacing:0.5px;color:#94a3b8;font-weight:600}}
.ras-value{{font-size:24px;font-weight:700;color:#e2e8f0;line-height:1}}
.ras-denom{{font-size:14px;opacity:0.5;font-weight:500}}
.ras-arrow{{font-size:16px;font-weight:700;opacity:0.85}}
.ras-adj .ras-value{{color:#f59e0b}}
.der-wrap{{margin-top:4px}}
.der-weight{{width:60px;text-align:center}}
.der-weight-badge{{font-family:'SF Mono','Consolas',monospace;font-size:13px;font-weight:700}}
.der-table td.der-evidence,.der-table td.der-mitigation{{font-size:12px;line-height:1.4}}

/* v5.6: Pre-Mortem */
.pm-item{{display:flex;gap:12px;margin-bottom:12px;padding:12px 14px;background:rgba(239,68,68,0.04);border:1px solid rgba(239,68,68,0.15);border-radius:10px;border-left:3px solid #ef4444}}
.pm-num{{flex:0 0 28px;height:28px;width:28px;border-radius:50%;background:rgba(239,68,68,0.18);color:#ef4444;font-weight:700;font-size:13px;display:flex;align-items:center;justify-content:center}}
.pm-body{{flex:1}}
.pm-scenario{{font-size:13px;font-weight:600;color:#e2e8f0;margin-bottom:4px;line-height:1.4}}
.pm-why{{font-size:12px;color:#94a3b8;line-height:1.45;margin-bottom:6px;font-style:italic}}
.pm-detail{{font-size:12px;color:#cbd5e1;line-height:1.4;margin-top:3px}}
.pm-label{{font-size:10px;font-weight:600;color:#f59e0b;text-transform:uppercase;letter-spacing:0.4px;margin-right:4px}}
.pm-signal .pm-label{{color:#22d3ee}}

/* v5.6: Rep Readiness Checklist */
.rr-list{{list-style:none;padding:0;margin:0}}
.rr-item{{display:flex;gap:10px;padding:10px 12px;margin-bottom:6px;background:rgba(34,197,94,0.04);border:1px solid rgba(34,197,94,0.15);border-radius:8px;align-items:flex-start}}
.rr-box{{flex:0 0 auto;font-size:16px;color:#22c55e;line-height:1.3}}
.rr-text{{flex:1;font-size:13px;color:#cbd5e1;line-height:1.45}}

/* Tables */
table{{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0}}
th{{background:#1e293b;padding:10px 12px;text-align:left;font-weight:600;color:#e2e8f0;font-size:11px;text-transform:uppercase;letter-spacing:0.5px}}
td{{padding:10px 12px;border-bottom:1px solid #1e293b;color:#94a3b8}}
.role-label{{font-weight:600;color:#e2e8f0}}
.risk-note{{color:#ef4444;font-size:11px}}
.strategy-note{{margin-top:12px;padding:12px;background:rgba(99,102,241,0.04);border-radius:8px;font-size:13px;color:#94a3b8}}

/* Recommendations */
.action-banner{{padding:14px 20px;border-radius:10px;margin-bottom:14px;font-weight:700;font-size:14px;letter-spacing:1px}}
.step-item{{display:flex;gap:12px;align-items:flex-start;padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:13px;color:#cbd5e1}}
.step-num{{width:24px;height:24px;border-radius:50%;background:#6366f1;color:#fff;font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0}}
.talking-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:16px 0}}
.talk-col h4{{font-size:12px;font-weight:700;color:#6366f1;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}}
.talk-col ul{{list-style:none;padding:0}}
.talk-col li{{padding:6px 0;font-size:13px;color:#94a3b8;border-bottom:1px solid rgba(255,255,255,0.04)}}
.talk-col li::before{{content:"→ ";color:#6366f1;font-weight:600}}
.objection-item{{padding:12px;margin:8px 0;background:rgba(255,255,255,0.02);border-radius:8px;border:1px solid rgba(255,255,255,0.04)}}
.obj-q{{font-size:13px;font-weight:600;color:#f59e0b;margin-bottom:4px}}
.obj-a{{font-size:13px;color:#94a3b8}}
.outreach-box{{padding:12px;margin-top:12px;background:rgba(99,102,241,0.04);border-radius:8px;font-size:13px;color:#94a3b8}}
.outreach-hook{{margin-top:4px;color:#818cf8}}

/* v7.2 — Recommended Outreach (email sequence cards) */
.outreach-intro{{font-size:13px;color:#94a3b8;margin:0 0 14px 0;line-height:1.55}}
.outreach-intro em{{color:#cbd5e1;font-style:italic}}
.outreach-card{{padding:18px 20px;margin:14px 0;background:rgba(15,23,42,0.55);border:1px solid rgba(99,102,241,0.18);border-radius:14px;page-break-inside:avoid;break-inside:avoid}}
.outreach-card-head{{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px;flex-wrap:wrap}}
.outreach-meta{{display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
.slot-pill{{font-size:10px;font-weight:700;letter-spacing:1.2px;padding:4px 9px;border-radius:6px;background:#6366f1;color:#fff;text-transform:uppercase}}
.voice-badge{{font-size:10px;font-weight:700;letter-spacing:1.2px;padding:4px 9px;border-radius:6px;border:1px solid;text-transform:uppercase}}
.template-name{{font-size:13px;font-weight:600;color:#e2e8f0}}
.copy-btn{{font-family:inherit;font-size:11px;font-weight:600;letter-spacing:0.6px;padding:6px 13px;border-radius:6px;background:rgba(99,102,241,0.18);color:#a5b4fc;border:1px solid rgba(99,102,241,0.35);cursor:pointer;text-transform:uppercase;transition:all 0.15s ease}}
.copy-btn:hover{{background:rgba(99,102,241,0.32);color:#fff}}
.copy-btn.copied{{background:rgba(34,197,94,0.18);color:#86efac;border-color:rgba(34,197,94,0.4)}}
.trig-row{{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 10px 0}}
.trig-chip{{font-size:10px;font-weight:600;padding:3px 8px;border-radius:10px;background:rgba(245,158,11,0.12);color:#fbbf24;border:1px solid rgba(245,158,11,0.25);letter-spacing:0.4px;text-transform:uppercase}}
.outreach-subject{{font-size:14px;color:#e2e8f0;font-weight:600;margin:8px 0 10px 0;padding:8px 12px;background:rgba(30,41,59,0.55);border-radius:6px;border-left:3px solid #6366f1}}
.subj-label{{display:inline-block;font-size:9px;font-weight:700;letter-spacing:1.4px;color:#818cf8;margin-right:8px;text-transform:uppercase}}
.outreach-body{{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:13px;line-height:1.65;color:#cbd5e1;white-space:pre-wrap;background:rgba(2,6,23,0.4);padding:14px 16px;border-radius:8px;margin:0 0 12px 0;border:1px solid rgba(99,102,241,0.08)}}
.outreach-rationale{{padding:10px 12px;background:rgba(99,102,241,0.05);border-radius:6px;border-left:2px solid rgba(99,102,241,0.4)}}
/* v7.4 — Demo Playbook (persona-anchored AD360+Log360 scripts) */
.demo-head{{padding:14px 16px;margin:6px 0 14px 0;background:rgba(15,23,42,0.55);border:1px solid rgba(99,102,241,0.18);border-radius:12px;display:flex;flex-direction:column;gap:10px}}
.demo-persona,.demo-hook{{display:flex;flex-direction:column;gap:4px}}
.demo-label{{font-size:9px;font-weight:700;letter-spacing:1.4px;color:#818cf8;text-transform:uppercase}}
.demo-persona-text{{font-size:13px;color:#e2e8f0;font-weight:600}}
.demo-hook-text{{font-size:13px;color:#cbd5e1;line-height:1.6;font-style:italic}}
.demo-product{{padding:16px 18px;margin:14px 0;border-radius:12px;page-break-inside:avoid;break-inside:avoid}}
.demo-product-head{{font-size:14px;font-weight:700;letter-spacing:0.8px;text-transform:uppercase;margin-bottom:10px}}
.demo-section-title{{font-size:10px;font-weight:700;letter-spacing:1.4px;color:#94a3b8;text-transform:uppercase;margin:14px 0 8px 0}}
.demo-moment{{padding:11px 13px;margin:8px 0;background:rgba(2,6,23,0.4);border:1px solid rgba(99,102,241,0.10);border-radius:8px}}
.demo-moment-num{{display:inline-block;font-size:9px;font-weight:700;letter-spacing:1.2px;padding:3px 8px;border-radius:5px;text-transform:uppercase;margin-bottom:6px}}
.demo-moment-title{{font-size:13px;color:#e2e8f0;font-weight:600;margin-bottom:6px}}
.demo-moment-why{{font-size:12px;color:#cbd5e1;line-height:1.55;margin-bottom:6px}}
.demo-moment-why strong{{color:#818cf8;font-weight:600}}
.demo-moment-script{{font-size:12px;color:#94a3b8;line-height:1.6;font-style:italic;padding:8px 10px;background:rgba(99,102,241,0.05);border-radius:6px;border-left:2px solid rgba(99,102,241,0.30)}}
.demo-qs{{list-style:none;padding:0;margin:0}}
.demo-qs li{{font-size:12px;color:#cbd5e1;padding:5px 0 5px 18px;line-height:1.55;position:relative}}
.demo-qs li::before{{content:"?";color:#818cf8;font-weight:700;position:absolute;left:0;top:5px}}
.demo-obj{{padding:9px 11px;margin:6px 0;background:rgba(2,6,23,0.35);border-radius:6px;border-left:2px solid rgba(245,158,11,0.45)}}
.demo-obj-q{{font-size:12px;color:#fbbf24;font-weight:500;line-height:1.5;margin-bottom:4px}}
.demo-obj-a{{font-size:12px;color:#cbd5e1;line-height:1.55}}
.demo-cta{{display:flex;align-items:flex-start;gap:10px;margin-top:14px;padding:10px 12px;background:rgba(99,102,241,0.07);border-radius:8px;border-left:3px solid #6366f1}}
.demo-cta-label{{flex:0 0 auto;font-size:10px;font-weight:700;letter-spacing:1.2px;color:#818cf8;text-transform:uppercase;padding-top:1px}}
.demo-cta-text{{font-size:12.5px;color:#e2e8f0;line-height:1.55;font-weight:500}}
.rationale-label{{font-size:10px;font-weight:700;letter-spacing:1.2px;color:#818cf8;margin-bottom:4px;text-transform:uppercase}}
.rationale-text{{font-size:12px;color:#94a3b8;line-height:1.55}}

/* Sources */
.source-cat{{font-size:12px;color:#94a3b8;margin:4px 0}}
.source-cat a{{color:#6366f1;text-decoration:none}}
.source-cat a:hover{{text-decoration:underline}}

/* Data Quality */
.dq-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.dq-list{{list-style:none;padding:0}}
.dq-list li{{font-size:12px;color:#94a3b8;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04)}}
.dq-list li::before{{content:"• ";color:#94a3b8}}
.empty{{font-size:13px;color:#475569;font-style:italic}}

/* Peer benchmark */
.peer-note{{font-size:11px;color:#94a3b8;font-style:italic;margin-top:8px}}

/* Footer */
.report-footer{{text-align:center;padding:28px;margin-top:16px;font-size:11px;color:#334155;border-top:1px solid #1e293b}}
.report-footer strong{{color:#475569}}

/* Two-column layout for profile */
.profile-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}

/* ============================================================
   MOBILE RESPONSIVE — all rules cascade so smaller wins.
   Two breakpoints:
     - tablet (≤900px): collapse multi-column grids, shrink padding
     - phone  (≤600px): aggressive font/padding shrink, stack everything
   The page already has <meta viewport=device-width> so we honour
   the device's CSS pixel width directly.

   CRITICAL: Only <html> gets overflow-x:hidden. Setting overflow-x on
   <body> makes body its own scroll container (spec: if one axis is
   clipped, the other computes to auto), which silently breaks
   position:sticky on descendants like .tab-nav. We still prevent
   horizontal page overflow because <html> is the root scroller.
   ============================================================ */
html{{overflow-x:hidden;max-width:100%}}
body{{max-width:100%}}
*{{min-width:0}}  /* prevents flex/grid children from forcing parent overflow */
img,svg,table,pre,code{{max-width:100%}}

@media (max-width: 900px) {{
  .page{{padding:18px 14px;max-width:100%}}
  .report-header{{padding:24px 22px;border-radius:16px}}
  .lead-name{{font-size:24px}}
  .lead-sub{{font-size:13px;word-break:break-word}}

  /* Tab nav — keep horizontal but allow buttons to shrink */
  .tab-nav{{padding:5px;border-radius:12px;top:8px}}
  .tab-btn{{padding:10px 12px;font-size:11.5px;letter-spacing:0.3px}}

  /* Score hero stacks: gauge, then radar, then meta */
  .score-hero{{padding:18px 16px;border-radius:14px}}
  .score-hero-top{{grid-template-columns:1fr;gap:14px;text-align:center}}
  .score-meta{{align-items:center}}
  .score-meta > div{{justify-content:center}}

  /* Dimension bars: 4 cols → 2 cols */
  .dim-bars{{grid-template-columns:repeat(2, minmax(0,1fr));gap:12px}}

  /* All other 1fr 1fr grids → single column */
  .dq-grid,.profile-grid,.talking-grid,.field-grid{{grid-template-columns:1fr;gap:14px}}

  /* Section padding tightens */
  .section{{padding:18px 18px;border-radius:14px}}
  .section-title{{font-size:11px;letter-spacing:1.5px}}

  /* Heatmap row: 4 cols → stack */
  .heatmap-row{{grid-template-columns:1fr;gap:6px;padding:14px}}

  /* Tables in dossier tab: smaller font; the .md-table-wrap already has
     overflow-x:auto so tables scroll horizontally on narrow screens.
     IMPORTANT: do NOT use word-break:break-word on table cells — it
     character-breaks single words like "DIMENSION" → "DI / ME / NSI / ON". */
  .dossier-verbatim{{padding:22px 18px;font-size:13px;line-height:1.7;border-radius:14px}}
  .dossier-verbatim .md-h1{{font-size:20px}}
  .dossier-verbatim .md-h2{{font-size:13px;letter-spacing:1.6px;margin:26px 0 11px 0}}
  .dossier-verbatim .md-h3{{font-size:13px;padding-left:9px}}
  .dossier-verbatim .md-h4{{font-size:10.5px}}
  .dossier-verbatim .md-callout{{font-size:12px;padding:9px 12px 10px}}
  .dossier-verbatim .md-callout-label{{font-size:9.5px}}
  .dossier-verbatim .md-li-kv{{grid-template-columns:minmax(100px,max-content) 1fr;gap:8px 12px}}
  .dossier-verbatim .md-li-kv-key{{font-size:11px}}
  .dossier-verbatim .md-table-wrap{{margin:10px 0 14px;-webkit-overflow-scrolling:touch}}
  .dossier-verbatim .md-table{{font-size:11.5px;min-width:480px}}
  .dossier-verbatim .md-table th,.dossier-verbatim .md-table td{{padding:8px 9px}}

  /* Signal timeline: native viewBox (760x160) is too wide-and-short for phones.
     Wrap in horizontal scroll with min-width so dots/labels stay readable. */
  .signal-timeline-wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
  .signal-timeline-wrap svg{{min-width:560px}}

  /* Verdict banner: tier pill above body */
  .verdict-banner{{flex-direction:column;min-height:0}}
  .verdict-tier-pill{{flex-direction:row;justify-content:center;gap:14px;min-width:0;width:100%;padding:14px 18px}}
  .verdict-score{{font-size:30px}}
  .verdict-tier{{font-size:10.5px;margin-top:0}}
  .verdict-body{{padding:16px 18px}}
  .verdict-headline{{font-size:14px}}
  .verdict-insight{{font-size:12.5px}}
  .verdict-next{{font-size:11.5px}}

  /* Generic tables (NOT inside .md-table-wrap, which already handles its own scroll)
     become horizontally scrollable as a last resort */
  table:not(.md-table){{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch}}

  /* Long URLs in sources should wrap, never push the page wider */
  a{{word-break:break-word;overflow-wrap:anywhere}}
  .source-cat{{word-break:break-word}}
}}

@media (max-width: 600px) {{
  .page{{padding:14px 10px}}
  .report-header{{padding:20px 18px}}
  .lead-name{{font-size:21px;letter-spacing:-0.3px}}
  .lead-sub{{font-size:12px}}
  .header-brand{{flex-direction:column;align-items:flex-start;gap:6px;margin-bottom:14px}}

  /* Tab nav: shorter labels would be ideal, but force fit instead */
  .tab-btn{{padding:9px 8px;font-size:10.5px;letter-spacing:0.2px;text-transform:none}}

  /* Score hero ultra-compact */
  .score-hero{{padding:16px 14px}}
  .score-hero-top{{gap:10px}}
  .score-radar-label{{font-size:9px;letter-spacing:1px}}

  /* Dimension bars: stay at 2 columns; on extra-narrow, single column */
  .dim-bars{{gap:10px}}
  .dim-name{{font-size:10px;letter-spacing:0.5px}}
  .dim-score{{font-size:13px}}

  .section{{padding:16px 14px;border-radius:12px;margin-bottom:12px}}
  .section-title{{font-size:10.5px;margin-bottom:12px;padding-bottom:8px}}

  /* Verdict banner: single-line pill */
  .verdict-tier-pill{{padding:12px 16px}}
  .verdict-score{{font-size:26px}}
  .verdict-body{{padding:14px 16px}}
  .verdict-headline{{font-size:13.5px;line-height:1.4}}
  .verdict-insight{{font-size:12px;line-height:1.5}}
  .verdict-next{{font-size:11px}}

  /* Dossier tab: smaller everything */
  .dossier-verbatim{{padding:18px 14px;font-size:12px;line-height:1.65}}
  .dossier-verbatim .md-h1{{font-size:17px}}
  .dossier-verbatim .md-h2{{font-size:11.5px;letter-spacing:1.4px;margin:22px 0 9px 0}}
  .dossier-verbatim .md-h3{{font-size:12.5px;padding-left:8px}}
  .dossier-verbatim .md-h4{{font-size:10px}}
  .dossier-verbatim .md-list{{padding-left:2px}}
  .dossier-verbatim .md-list li{{padding-left:16px}}
  .dossier-verbatim .md-callout{{font-size:11.5px;padding:8px 11px 9px}}
  .dossier-verbatim .md-callout-label{{font-size:9px}}
  .dossier-verbatim .md-li-kv{{grid-template-columns:1fr;gap:2px 0;padding:5px 10px}}
  .dossier-verbatim .md-li-kv-key{{font-size:10.5px}}
  .dossier-verbatim .md-table{{font-size:10.5px}}
  .dossier-verbatim .md-table th{{padding:7px 7px;font-size:9.5px}}
  .dossier-verbatim .md-table td{{padding:7px 7px}}

  /* Pills shrink together — keep all three on the same baseline at phone sizes */
  .tier-label,.conf-label,.icp-label{{font-size:10.5px;padding:5px 11px;height:26px;letter-spacing:0.3px}}
  .tier-label{{font-size:11px;letter-spacing:1px}}

  /* Footer */
  .report-footer{{font-size:10.5px;padding:14px 0}}
}}

/* Extra-narrow guard (320px iPhone SE 1st gen, etc.) */
@media (max-width: 360px) {{
  .page{{padding:12px 8px}}
  .lead-name{{font-size:19px}}
  .dim-bars{{grid-template-columns:1fr}}
  .tab-btn{{padding:8px 6px;font-size:10px}}
  .verdict-score{{font-size:24px}}
}}

/* PRINT / PDF — light theme remap */
@media print{{
  body{{background:#fff;color:#1f2937;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  .page{{padding:20px;max-width:100%}}
  .report-header{{background:#f8fafc;border:1px solid #cbd5e1;page-break-inside:avoid}}
  .report-header .lead-name{{color:#0f172a}}
  .report-header .lead-sub{{color:#475569}}
  .verdict-banner{{page-break-inside:avoid;border-width:1px!important}}
  .verdict-headline{{color:#1f2937}}
  .verdict-insight{{color:#475569}}
  .verdict-next{{color:#4f46e5}}
  .score-hero,.section{{background:#fff;border:1px solid #e5e7eb;page-break-inside:avoid}}
  .section-title{{color:#4338ca;border-bottom-color:#e5e7eb}}
  .lead-name,.signal-text,.field-value,.heatmap-name{{color:#0f172a}}
  .lead-sub,.field-label,.signal-meta,.dim-name,.heatmap-urgency,.heatmap-cell-label{{color:#6b7280}}
  .dim-track{{background:#e5e7eb}}
  .exec-brief{{background:#eef2ff;color:#1f2937}}
  .step-item{{color:#1f2937}}
  .talk-col li{{color:#374151}}
  .net-assessment,.strategy-note,.outreach-box,.obj-a,.peer-note{{color:#4b5563}}
  .heatmap-row,.signal-item,.objection-item{{background:#f9fafb;border-color:#e5e7eb}}
  /* v7.2 — Recommended Outreach light theme */
  .outreach-card{{background:#fff;border-color:#e5e7eb}}
  .outreach-intro{{color:#4b5563}}
  .outreach-intro em{{color:#1f2937}}
  .template-name{{color:#1f2937}}
  .outreach-subject{{background:#f1f5f9;color:#0f172a;border-left-color:#6366f1}}
  .outreach-body{{background:#f9fafb;color:#1f2937;border-color:#e5e7eb}}
  .outreach-rationale{{background:#eef2ff;border-left-color:#6366f1}}
  .rationale-text{{color:#475569}}
  .copy-btn{{background:#eef2ff;color:#4338ca;border-color:#c7d2fe}}
  /* v7.4 — Demo Playbook light theme */
  .demo-head{{background:#fff;border-color:#e5e7eb}}
  .demo-persona-text{{color:#0f172a}}
  .demo-hook-text{{color:#374151}}
  .demo-section-title{{color:#475569}}
  .demo-moment{{background:#f9fafb;border-color:#e5e7eb}}
  .demo-moment-title{{color:#0f172a}}
  .demo-moment-why{{color:#374151}}
  .demo-moment-script{{background:#eef2ff;color:#475569}}
  .demo-qs li{{color:#374151}}
  .demo-obj{{background:#fffbeb;border-left-color:rgba(245,158,11,0.55)}}
  .demo-obj-q{{color:#b45309}}
  .demo-obj-a{{color:#374151}}
  .demo-cta{{background:#eef2ff}}
  .demo-cta-text{{color:#0f172a}}
  .heatmap-cell,.heatmap-cell-text{{background:#fff;color:#374151}}
  th{{background:#f1f5f9;color:#0f172a}}
  td{{color:#4b5563;border-bottom-color:#e5e7eb}}
  .validation-clean{{background:#f0fdf4;color:#166534}}
  .val-rule{{background:#f9fafb}}
  .val-desc{{color:#4b5563}}
  /* v5.6 light-theme overrides */
  .readiness-basis{{background:#f9fafb;border-color:#e5e7eb}}
  .readiness-basis-text,.ghost-field-text,.der-table td.der-evidence,.der-table td.der-mitigation,.pm-detail,.rr-text{{color:#374151}}
  .ghost-card{{background:#f5f3ff;border-color:#e9d5ff}}
  .ghost-role{{color:#1f2937}}
  .ghost-status,.ghost-arrival{{background:#ede9fe;color:#6d28d9}}
  .ghost-empty{{background:#f9fafb;border-color:#e5e7eb;color:#4b5563}}
  .risk-adjusted-strip{{background:#fffbeb;border-color:#fde68a}}
  .ras-value{{color:#1f2937}}
  .pm-item{{background:#fef2f2;border-color:#fecaca}}
  .pm-scenario{{color:#1f2937}}
  .pm-why{{color:#6b7280}}
  .rr-item{{background:#f0fdf4;border-color:#bbf7d0}}
  .report-footer{{color:#9ca3af;border-top-color:#e5e7eb}}
  .dq-list li{{color:#4b5563}}
  .donut-label{{color:#374151}}
  .score-radar-label{{color:#6b7280}}
  /* SVG text color remaps for print — slate greys become darker for readability */
  svg text[fill="#64748b"]{{fill:#6b7280}}
  svg text[fill="#94a3b8"]{{fill:#6b7280}}
  svg text[fill="#94a3b8"]{{fill:#4b5563}}
  svg text[fill="#cbd5e1"]{{fill:#1f2937}}
  svg text[fill="#e2e8f0"]{{fill:#0f172a}}
  svg text[fill="#fff"]{{fill:#1f2937}}
  /* Radar/gauge background rings: slate-800 -> light-grey */
  svg circle[stroke="#cbd5e1"]{{stroke:#e5e7eb}}
  svg polygon[stroke="#cbd5e1"]{{stroke:#e5e7eb}}
  svg line[stroke="#cbd5e1"]{{stroke:#e5e7eb}}
  svg line[stroke="#94a3b8"]{{stroke:#d1d5db}}
  /* Dot centers: dark bg -> light bg */
  svg circle[stroke="#0f172a"]{{stroke:#fff}}
  /* DMU hub center circle */
  svg circle[fill="#0f172a"]{{fill:#f9fafb}}
  /* Section breaks */
  .section{{page-break-inside:avoid}}
  .score-hero{{page-break-after:auto}}
  h3{{color:#4b5563}}
}}

/* ============================================================
   Tab Navigation (Executive Summary | Complete Intelligence Dossier)
   ============================================================ */
.tab-nav{{display:flex;gap:4px;background:#0f172a;border:1px solid #1e293b;border-radius:14px;padding:6px;margin-bottom:16px;position:sticky;top:16px;z-index:50;backdrop-filter:blur(8px)}}
.tab-btn{{flex:1;padding:12px 18px;background:transparent;border:none;color:#94a3b8;font-family:inherit;font-size:13px;font-weight:600;letter-spacing:0.5px;border-radius:10px;cursor:pointer;transition:all 0.2s ease;text-transform:uppercase}}
.tab-btn:hover{{color:#e2e8f0;background:rgba(99,102,241,0.08)}}
.tab-btn.active{{background:{tc['gradient']};color:#fff;box-shadow:0 2px 8px rgba(0,0,0,0.2)}}
.tab-panel{{display:none;animation:fadeIn 0.25s ease}}
.tab-panel.active{{display:block}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(4px)}}to{{opacity:1;transform:translateY(0)}}}}

/* ============================================================
   Complete Intelligence Dossier — markdown rendering (v7.0.1)
   Typography scale deliberately mirrors Tab 1:
     - Body 13.5px (Tab 1 card-copy ~13px; exec-brief 15px)
     - h2 14px uppercase letter-spaced indigo (matches .section-title scale)
     - h3 13.5px — paragraph-level sub-sections
     - h4 11px uppercase — minor dividers
   Visual variety comes from callouts, key-value rows, custom bullets,
   and accent-coded strong/em — not from font-size bloat.
   ============================================================ */
.dossier-verbatim{{background:#0f172a;border:1px solid #1e293b;border-radius:16px;padding:32px 36px;font-size:13.5px;line-height:1.7;color:#cbd5e1}}
.dossier-verbatim .md-h1{{font-size:22px;font-weight:800;letter-spacing:-0.3px;color:#f1f5f9;margin:0 0 10px 0;padding-bottom:14px;border-bottom:2px solid #4338ca;scroll-margin-top:80px}}
.dossier-verbatim .md-h2{{font-size:14px;font-weight:700;letter-spacing:1.8px;text-transform:uppercase;color:#818cf8;margin:30px 0 12px 0;padding-bottom:8px;position:relative;scroll-margin-top:80px}}
.dossier-verbatim .md-h2::after{{content:'';position:absolute;left:0;right:0;bottom:0;height:2px;background:linear-gradient(90deg,#6366f1 0%,#8b5cf6 40%,rgba(99,102,241,0.08) 100%);border-radius:2px}}
.dossier-verbatim .md-h3{{font-size:13.5px;font-weight:700;color:#e2e8f0;margin:18px 0 6px 0;padding-left:10px;border-left:3px solid #6366f1;scroll-margin-top:80px}}
.dossier-verbatim .md-h4{{font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;margin:14px 0 6px 0;scroll-margin-top:80px}}
.dossier-verbatim .md-p{{margin:0 0 10px 0;color:#cbd5e1}}

/* Lists — custom colored triangle bullets replace drab default disc */
.dossier-verbatim .md-list{{margin:4px 0 14px 0;padding-left:4px;list-style:none}}
.dossier-verbatim .md-list li{{margin:5px 0;color:#cbd5e1;padding-left:18px;position:relative}}
.dossier-verbatim .md-list>li::before{{content:'▸';position:absolute;left:2px;top:-1px;color:#818cf8;font-weight:700;font-size:11px;line-height:inherit}}
.dossier-verbatim ol.md-list{{counter-reset:md-olc}}
.dossier-verbatim ol.md-list>li{{counter-increment:md-olc}}
.dossier-verbatim ol.md-list>li::before{{content:counter(md-olc) '.';color:#a5b4fc;font-weight:700;font-size:11.5px;font-family:'SF Mono',Consolas,monospace;left:0}}
.dossier-verbatim .md-list .md-list{{margin:4px 0 6px 0}}
.dossier-verbatim .md-list .md-list>li::before{{content:'·';color:#64748b;font-size:14px;top:-4px}}

/* Key–value bullets: "- **Label:** value" rows render as a 2-col grid */
.dossier-verbatim .md-li-kv{{display:grid;grid-template-columns:minmax(120px,max-content) 1fr;gap:10px 14px;align-items:baseline;padding:3px 10px 3px 14px;margin:2px 0;background:rgba(99,102,241,0.04);border-left:2px solid rgba(129,140,248,0.35);border-radius:0 5px 5px 0}}
.dossier-verbatim .md-li-kv::before{{display:none}}
.dossier-verbatim .md-li-kv-key{{color:#a5b4fc;font-weight:700;font-size:11.5px;text-transform:uppercase;letter-spacing:0.7px;white-space:nowrap}}
.dossier-verbatim .md-li-kv-val{{color:#e2e8f0;font-weight:500}}

/* Callout boxes — paragraphs opening with **Label:** get accent framing */
.dossier-verbatim .md-callout{{margin:10px 0;padding:10px 14px 11px;border-radius:0 8px 8px 0;background:rgba(99,102,241,0.06);border-left:3px solid #6366f1;color:#e2e8f0;font-size:12.5px;line-height:1.6}}
.dossier-verbatim .md-callout-label{{display:inline-block;font-size:10px;font-weight:800;letter-spacing:1.3px;text-transform:uppercase;padding:1px 8px;border-radius:4px;margin-right:8px;vertical-align:1px;background:rgba(99,102,241,0.18);color:#a5b4fc}}
.dossier-verbatim .md-callout-why{{background:rgba(139,92,246,0.07);border-left-color:#8b5cf6}}
.dossier-verbatim .md-callout-why .md-callout-label{{background:rgba(139,92,246,0.22);color:#c4b5fd}}
.dossier-verbatim .md-callout-mitigation{{background:rgba(34,197,94,0.06);border-left-color:#22c55e}}
.dossier-verbatim .md-callout-mitigation .md-callout-label{{background:rgba(34,197,94,0.18);color:#4ade80}}
.dossier-verbatim .md-callout-action{{background:rgba(59,130,246,0.06);border-left-color:#3b82f6}}
.dossier-verbatim .md-callout-action .md-callout-label{{background:rgba(59,130,246,0.2);color:#93c5fd}}
.dossier-verbatim .md-callout-trigger{{background:rgba(245,158,11,0.06);border-left-color:#f59e0b}}
.dossier-verbatim .md-callout-trigger .md-callout-label{{background:rgba(245,158,11,0.2);color:#fbbf24}}
.dossier-verbatim .md-callout-watch{{background:rgba(239,68,68,0.06);border-left-color:#ef4444}}
.dossier-verbatim .md-callout-watch .md-callout-label{{background:rgba(239,68,68,0.2);color:#fca5a5}}
.dossier-verbatim .md-callout-note{{background:rgba(6,182,212,0.06);border-left-color:#06b6d4}}
.dossier-verbatim .md-callout-note .md-callout-label{{background:rgba(6,182,212,0.2);color:#67e8f9}}

/* Blockquotes — italic callout for analyst voice */
.dossier-verbatim .md-blockquote{{margin:12px 0;padding:8px 14px 8px 16px;border-left:3px solid #475569;background:rgba(148,163,184,0.04);color:#cbd5e1;font-style:italic;border-radius:0 6px 6px 0}}
.dossier-verbatim .md-blockquote p{{margin:0}}

/* Inline emphasis — strong / em get subtle accent */
.dossier-verbatim strong{{color:#f8fafc;font-weight:700}}
.dossier-verbatim em{{color:#c7d2fe;font-style:italic}}
.dossier-verbatim code,.dossier-verbatim .md-code{{background:rgba(99,102,241,0.12);color:#a5b4fc;padding:2px 6px;border-radius:4px;font-size:12px;font-family:'SF Mono',Consolas,monospace}}
.dossier-verbatim .md-hr{{border:0;height:1px;background:linear-gradient(90deg,transparent 0%,#334155 30%,#334155 70%,transparent 100%);margin:22px 0}}
.dossier-verbatim .md-table-wrap{{overflow-x:auto;margin:12px 0 16px 0;border:1px solid #1e293b;border-radius:8px;max-height:none}}
.dossier-verbatim .md-table{{width:100%;border-collapse:separate;border-spacing:0;font-size:12.5px;margin:0}}
.dossier-verbatim .md-table th{{background:#1e293b;color:#e2e8f0;font-weight:700;text-align:left;padding:10px 12px;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;border-bottom:1px solid #334155;position:sticky;top:0;z-index:1}}
.dossier-verbatim .md-table td{{padding:10px 12px;color:#cbd5e1;border-bottom:1px solid #1e293b;vertical-align:top;transition:background 0.15s}}
.dossier-verbatim .md-table tbody tr:nth-child(even) td{{background:rgba(99,102,241,0.04)}}
.dossier-verbatim .md-table tbody tr:hover td{{background:rgba(99,102,241,0.10)}}
.dossier-verbatim .md-table tr:last-child td{{border-bottom:none}}
.dossier-verbatim .md-empty{{color:#94a3b8;padding:20px;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.3);border-radius:8px}}

/* v5.7 — Anchor-link affordance on headings */
.dossier-verbatim .md-anchor{{color:#475569;text-decoration:none;margin-right:8px;opacity:0;transition:opacity 0.15s;font-weight:400}}
.dossier-verbatim .md-h1:hover .md-anchor,
.dossier-verbatim .md-h2:hover .md-anchor,
.dossier-verbatim .md-h3:hover .md-anchor,
.dossier-verbatim .md-h4:hover .md-anchor{{opacity:1}}
.dossier-verbatim .md-anchor:hover{{color:#818cf8}}

/* v5.7 — Auto-linked URLs in prose */
.dossier-verbatim .md-link{{color:#a5b4fc;text-decoration:none;border-bottom:1px dotted rgba(165,180,252,0.4);transition:all 0.15s;word-break:break-word}}
.dossier-verbatim .md-link:hover{{color:#c7d2fe;border-bottom-color:#c7d2fe;border-bottom-style:solid}}
.dossier-verbatim .md-link-icon{{font-size:0.85em;margin-left:2px;opacity:0.6;vertical-align:super;line-height:0}}

/* v5.7 — Confidence/status pills in dossier prose: [CONFIRMED] [ESTIMATED] [INFERRED] */
.dossier-verbatim .md-pill{{display:inline-block;padding:1px 7px;border-radius:10px;font-size:9.5px;font-weight:700;letter-spacing:0.5px;margin:0 2px;vertical-align:baseline;line-height:1.5;white-space:nowrap}}
.dossier-verbatim .md-pill-confirmed{{background:rgba(34,197,94,0.15);color:#22c55e;border:1px solid rgba(34,197,94,0.35)}}
.dossier-verbatim .md-pill-estimated{{background:rgba(245,158,11,0.15);color:#f59e0b;border:1px solid rgba(245,158,11,0.35)}}
.dossier-verbatim .md-pill-inferred{{background:rgba(107,114,128,0.18);color:#9ca3af;border:1px solid rgba(107,114,128,0.35)}}

/* v5.7 — Source tier badges in dossier prose: [A] [B] [C] */
.dossier-verbatim .md-tier{{display:inline-block;width:16px;height:16px;line-height:16px;text-align:center;border-radius:4px;font-size:9.5px;font-weight:800;margin:0 1px;vertical-align:baseline;cursor:help}}
.dossier-verbatim .md-tier-a{{background:rgba(34,197,94,0.18);color:#22c55e;border:1px solid rgba(34,197,94,0.4)}}
.dossier-verbatim .md-tier-b{{background:rgba(245,158,11,0.18);color:#f59e0b;border:1px solid rgba(245,158,11,0.4)}}
.dossier-verbatim .md-tier-c{{background:rgba(156,163,175,0.2);color:#9ca3af;border:1px solid rgba(156,163,175,0.4)}}

/* v7.1 — RocketReach provenance pill (Rule 7). Any value followed by ᴿᴿ in
   the markdown — or any Tab-1 card value marked via _rr_mark() — renders as
   an inline orange badge so the reader sees at a glance which claims came
   from the RocketReach premium account vs. free OSINT / inference. */
.rr-pill{{display:inline-block;margin-left:4px;padding:0 6px;min-width:20px;height:15px;line-height:14px;text-align:center;border-radius:4px;font-size:9px;font-weight:800;letter-spacing:0.6px;vertical-align:super;background:linear-gradient(135deg,#ff6b35 0%,#ff9e58 100%);color:#fff;border:1px solid rgba(255,107,53,0.55);box-shadow:0 1px 2px rgba(255,107,53,0.25);cursor:help;text-transform:none;user-select:none}}
.rr-pill::before{{content:'RR';letter-spacing:0.4px}}
.rr-pill-baseline{{vertical-align:baseline;height:17px;line-height:16px}}
.dossier-verbatim .rr-pill{{vertical-align:super}}

/* v5.7 — Evidence-URL chips (used in exec summary: signals, deal exec risks, competitive matrix, pre-mortem) */
.evidence-chips{{display:inline-flex;gap:3px;margin-left:5px;vertical-align:baseline}}
.evidence-chip{{display:inline-block;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:700;text-decoration:none;background:rgba(99,102,241,0.15);color:#a5b4fc;border:1px solid rgba(99,102,241,0.3);transition:all 0.15s;letter-spacing:0.3px;line-height:1.4}}
.evidence-chip:hover{{background:rgba(99,102,241,0.28);color:#c7d2fe;border-color:#818cf8;transform:translateY(-1px)}}

/* v5.7 — Source Quality Donut */
.source-quality-wrap{{display:grid;grid-template-columns:auto 1fr;gap:24px;align-items:center;padding:18px 4px}}
.source-quality-chart{{flex-shrink:0}}
.source-quality-side{{min-width:0}}
.sq-legend{{display:flex;flex-direction:column;gap:10px;margin-bottom:12px}}
.sq-legend-row{{display:grid;grid-template-columns:14px 1fr auto;gap:10px;align-items:center;font-size:12px;color:#cbd5e1}}
.sq-swatch{{width:12px;height:12px;border-radius:3px;display:inline-block}}
.sq-legend-label{{font-weight:500}}
.sq-legend-count{{font-weight:700;color:#f1f5f9}}
.sq-legend-pct{{font-weight:500;color:#94a3b8;font-size:11px}}
.sq-caption{{font-size:12px;color:#94a3b8;line-height:1.55;padding:10px 12px;background:rgba(99,102,241,0.06);border-left:3px solid #6366f1;border-radius:0 6px 6px 0}}
.source-donut-empty,.dmu-map-empty{{padding:18px;text-align:center}}

/* v5.7 — DMU + Ghost Stakeholder Map */
.dmu-map-wrap{{padding:10px 0;overflow-x:auto}}
.dmu-map-wrap svg text.dmu-name{{fill:#e2e8f0;font-weight:600}}
.dmu-map-wrap svg text.dmu-title{{fill:#94a3b8}}
.dmu-map-wrap svg text.dmu-edge-label{{fill:#94a3b8}}
.dmu-legend{{display:flex;flex-wrap:wrap;gap:14px 20px;margin-top:14px;padding:12px 14px;background:rgba(99,102,241,0.04);border:1px solid rgba(99,102,241,0.15);border-radius:8px}}
.dmu-legend-item{{display:flex;align-items:center;gap:6px;font-size:11px;color:#cbd5e1}}
.dmu-swatch{{width:12px;height:12px;border-radius:50%;display:inline-block;flex-shrink:0}}

/* v6.0 — Signal Timeline category legend */
.tl-legend{{display:flex;flex-wrap:wrap;gap:10px 14px;margin-top:10px;padding:10px 12px;background:rgba(99,102,241,0.04);border:1px solid rgba(99,102,241,0.15);border-radius:8px}}
.tl-legend-item{{display:inline-flex;align-items:center;gap:5px;font-size:10.5px;color:#cbd5e1;white-space:nowrap}}
.tl-legend-dot{{width:9px;height:9px;border-radius:50%;display:inline-block;flex-shrink:0}}
.tl-legend-label{{font-weight:500}}

/* ========================================================================
   v6.2 — WAVE 1 INFOGRAPHICS
   Visual styling for: Score Attribution Bar, Scenario Cards,
   Web Tech Fingerprint, First-Call Decision Tree.
   Each section is opt-in (only renders if its source data is in the JSON),
   and the styling is additive — no existing chart or table is affected.
   ======================================================================== */

/* Subtle differentiator: infographic sections get a faint indigo glow on
   the top border so the eye knows "this is a visual, not a table". */
.infographic-section{{position:relative;overflow:hidden}}
.infographic-section::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,#6366f1 30%,#8b5cf6 70%,transparent);opacity:0.6;border-radius:14px 14px 0 0;pointer-events:none}}

/* ---- Score Attribution Bar ------------------------------------------- */
.attr-wrap{{padding:8px 0 4px}}
.attr-bar-shell{{position:relative;height:54px;margin-bottom:18px}}
.attr-bar{{display:flex;width:100%;height:100%;border-radius:10px;overflow:hidden;background:rgba(255,255,255,0.04);box-shadow:inset 0 0 0 1px rgba(255,255,255,0.06)}}
.attr-seg{{display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:13px;letter-spacing:0.3px;transition:filter 0.15s;border-right:1px solid rgba(15,23,42,0.4);position:relative}}
.attr-seg:last-child{{border-right:0}}
.attr-seg:hover{{filter:brightness(1.15)}}
.attr-seg-label{{text-shadow:0 1px 2px rgba(0,0,0,0.4);white-space:nowrap;overflow:hidden}}
.attr-cap-line{{position:absolute;top:-6px;bottom:-6px;width:2px;background:#fbbf24;box-shadow:0 0 6px rgba(251,191,36,0.6)}}
.attr-cap-flag{{position:absolute;top:-22px;left:50%;transform:translateX(-50%);background:#fbbf24;color:#0f172a;font-size:9.5px;font-weight:800;letter-spacing:0.8px;padding:2px 8px;border-radius:4px;white-space:nowrap}}
.attr-caption{{font-size:12px;color:#cbd5e1;line-height:1.55;padding:10px 14px;background:rgba(99,102,241,0.06);border-left:3px solid #6366f1;border-radius:0 6px 6px 0;margin-bottom:14px}}
.attr-caption-note{{display:block;margin-top:4px;font-size:11px;color:#94a3b8;font-style:italic}}
.attr-legend{{display:grid;gap:6px;margin-top:6px}}
.attr-leg-row{{display:grid;grid-template-columns:14px auto auto 1fr;gap:10px;align-items:baseline;font-size:12px;padding:6px 10px;border-radius:6px;background:rgba(255,255,255,0.02);transition:background 0.15s}}
.attr-leg-row:hover{{background:rgba(99,102,241,0.06)}}
.attr-leg-dot{{width:10px;height:10px;border-radius:50%;display:inline-block}}
.attr-leg-cat{{color:#e2e8f0;font-weight:600}}
.attr-leg-pts{{color:#f1f5f9;font-weight:700;font-family:'SF Mono',Consolas,monospace;font-size:11.5px;background:rgba(99,102,241,0.18);padding:1px 7px;border-radius:4px}}
.attr-leg-evidence{{color:#94a3b8;font-style:italic;line-height:1.45;font-size:11.5px}}

/* ---- Scenario Cards -------------------------------------------------- */
.sc-intro{{font-size:13px;color:#94a3b8;line-height:1.55;margin-bottom:14px}}
.sc-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}
.sc-card{{display:flex;flex-direction:column;background:#0f172a;border:1px solid;border-radius:12px;overflow:hidden;transition:transform 0.18s,box-shadow 0.18s}}
.sc-card:hover{{transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,0.25)}}
.sc-card-head{{padding:14px 16px 16px;border-bottom:1px solid rgba(255,255,255,0.05)}}
.sc-delta-pill{{display:inline-block;padding:3px 10px;border-radius:999px;font-size:11px;font-weight:800;letter-spacing:0.6px;margin-bottom:10px}}
.sc-score-shift{{display:flex;align-items:baseline;gap:8px;margin-bottom:6px}}
.sc-score-old{{font-size:18px;font-weight:600;color:#64748b;text-decoration:line-through;text-decoration-thickness:1px;text-decoration-color:rgba(100,116,139,0.6)}}
.sc-score-arrow{{font-size:20px;font-weight:700}}
.sc-score-new{{font-size:32px;font-weight:800;letter-spacing:-0.6px;line-height:1}}
.sc-score-suffix{{font-size:13px;font-weight:500;color:#94a3b8}}
.sc-tier-row{{display:flex;align-items:center;gap:6px;font-size:10.5px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase}}
.sc-tier-old{{color:#64748b}}
.sc-tier-arrow{{color:#94a3b8;font-size:11px}}
.sc-tier-new{{font-weight:800}}
.sc-tier-stable{{color:#94a3b8}}
.sc-card-body{{padding:14px 16px 16px;flex:1;display:flex;flex-direction:column;gap:12px}}
.sc-label{{font-size:13.5px;font-weight:700;color:#e2e8f0;line-height:1.4}}
.sc-block-title{{font-size:9.5px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:#94a3b8;margin-bottom:5px}}
.sc-block-text{{font-size:12px;color:#cbd5e1;line-height:1.55}}
.sc-trigger{{padding:10px 12px;background:rgba(255,255,255,0.02);border-left:3px solid;border-radius:0 6px 6px 0;margin-top:auto}}

/* ---- Web Tech Fingerprint ------------------------------------------- */
.wf-intro{{font-size:13px;color:#94a3b8;line-height:1.55;margin-bottom:14px}}
.wf-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
.wf-cat{{background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:14px;display:flex;flex-direction:column;gap:10px;min-height:90px}}
.wf-cat-empty{{opacity:0.55;border-style:dashed;border-top:3px solid rgba(148,163,184,0.3)}}
.wf-cat-head{{display:flex;align-items:center;gap:8px}}
.wf-cat-icon{{font-size:16px;line-height:1}}
.wf-cat-title{{font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#e2e8f0;flex:1}}
.wf-cat-count{{font-size:11px;font-weight:700;color:#a5b4fc;background:rgba(99,102,241,0.18);padding:2px 8px;border-radius:999px}}
.wf-cat-body{{display:flex;flex-wrap:wrap;gap:6px}}
.wf-cat-empty-text{{font-size:11px;color:#64748b;font-style:italic}}
.wf-badge{{display:inline-flex;align-items:center;gap:6px;padding:5px 10px;background:rgba(99,102,241,0.06);border:1px solid;border-radius:6px;font-size:11.5px;color:#e2e8f0;cursor:help;transition:background 0.15s,transform 0.12s}}
.wf-badge:hover{{background:rgba(99,102,241,0.14);transform:translateY(-1px)}}
.wf-conf-dot{{width:7px;height:7px;border-radius:50%;display:inline-block;flex-shrink:0}}
.wf-name{{font-weight:600;letter-spacing:0.2px}}
.wf-ver{{color:#94a3b8;font-size:10.5px;font-family:'SF Mono',Consolas,monospace}}
.wf-legend{{display:flex;flex-wrap:wrap;gap:14px;align-items:center;margin-top:14px;padding:10px 14px;background:rgba(99,102,241,0.04);border:1px solid rgba(99,102,241,0.15);border-radius:8px;font-size:11px}}
.wf-legend-item{{display:inline-flex;align-items:center;gap:5px;color:#cbd5e1}}
.wf-legend-hint{{margin-left:auto;color:#94a3b8;font-style:italic;font-size:10.5px}}

/* ---- RocketReach Firmographic Enrichment (v7.1.3 → redesigned v7.1.4) --
   Palette: champagne / aged-bronze (#92722a primary, #c8a45a accent,
   #e9c988 / #f3dfa9 light tones). Intentionally unused elsewhere in the
   dossier so this section reads as "authoritative premium-API data" at a
   glance without fighting the existing indigo primary, red/amber/blue
   tier colors, green HIGH-confidence, or the orange ᴿᴿ inline pill.
   Real-estate: headcount + trajectory pack side-by-side in a 2-col
   `.rr-enrich-pair` grid; tech chips tighten to 40 items; code strip
   drops to a 3-col row. Net vertical saving vs. v7.1.3: ~160–200px. */
.rr-enrich-section{{position:relative;background:linear-gradient(180deg,#0f1420 0%,#0b0f18 100%);border:1px solid rgba(200,164,90,0.22);padding:18px 20px}}
.rr-enrich-section::before{{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:linear-gradient(180deg,#c8a45a 0%,#e9c988 100%);border-radius:2px 0 0 2px}}
.rr-enrich-title{{color:#f3dfa9;letter-spacing:0.5px;font-size:13px;text-transform:uppercase;font-weight:700;margin-bottom:14px}}
.rr-enrich-header{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px 18px;padding:11px 14px;background:rgba(200,164,90,0.05);border:1px solid rgba(200,164,90,0.15);border-radius:6px;margin-bottom:12px}}
.rr-header-link{{display:inline-flex;align-items:center;gap:5px;color:#e9c988;text-decoration:none;font-weight:600;font-size:12px;letter-spacing:0.3px}}
.rr-header-link:hover{{color:#f3dfa9}}
.rr-header-link-label{{text-transform:uppercase;letter-spacing:0.9px;font-size:10.5px}}
.rr-header-link-arrow{{font-size:13px;line-height:1}}
.rr-header-meta{{display:flex;flex-direction:column;gap:1px;min-width:0}}
.rr-header-meta-label{{font-size:9px;font-weight:700;letter-spacing:1.1px;text-transform:uppercase;color:#94a3b8}}
.rr-header-meta-value{{font-size:12px;color:#e2e8f0;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.rr-enrich-codes{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:10px;margin-bottom:12px}}
.rr-subblock{{display:flex;flex-direction:column;gap:5px;padding:8px 11px;background:rgba(200,164,90,0.03);border:1px solid rgba(200,164,90,0.10);border-radius:5px}}
.rr-subblock-label{{font-size:9px;font-weight:700;letter-spacing:1.1px;text-transform:uppercase;color:#94a3b8}}
.rr-subblock-value{{display:flex;flex-wrap:wrap;gap:3px;font-size:11.5px;color:#cbd5e1}}
.rr-kw-pill{{display:inline-block;padding:1.5px 7px;background:rgba(200,164,90,0.08);color:#e9c988;border:1px solid rgba(200,164,90,0.25);border-radius:10px;font-size:10.5px;font-weight:500}}
.rr-codes{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;letter-spacing:0.3px;color:#cbd5e1}}
.rr-enrich-pair{{display:grid;grid-template-columns:1.3fr 1fr;gap:12px;margin-bottom:0}}
@media (max-width:720px){{.rr-enrich-pair{{grid-template-columns:1fr}}}}
.rr-enrich-block{{margin-bottom:12px;padding:11px 13px;background:rgba(200,164,90,0.03);border:1px solid rgba(200,164,90,0.10);border-radius:6px}}
.rr-enrich-pair .rr-enrich-block{{margin-bottom:0}}
.rr-enrich-block:last-child{{margin-bottom:0}}
.rr-enrich-block-head{{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin-bottom:10px;padding-bottom:7px;border-bottom:1px solid rgba(200,164,90,0.15)}}
.rr-enrich-block-title{{font-size:10.5px;font-weight:700;letter-spacing:1.1px;text-transform:uppercase;color:#f3dfa9}}
.rr-enrich-block-count{{font-size:10px;color:#94a3b8;font-weight:500}}
.rr-tech-grid{{display:flex;flex-wrap:wrap;gap:4px}}
.rr-tech-chip{{display:inline-block;padding:2px 8px;background:rgba(200,164,90,0.06);color:#d6cda8;border:1px solid rgba(200,164,90,0.18);border-radius:3px;font-size:10.5px;font-weight:500;line-height:1.5}}
.rr-tech-more{{display:inline-block;padding:2px 8px;color:#94a3b8;font-style:italic;font-size:10.5px}}
.rr-dept-grid{{display:grid;gap:5px}}
.rr-dept-row{{display:grid;grid-template-columns:110px 1fr 32px;align-items:center;gap:10px}}
.rr-dept-label{{font-size:11.5px;color:#cbd5e1;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.rr-dept-bar-track{{height:7px;background:rgba(200,164,90,0.08);border-radius:999px;overflow:hidden}}
.rr-dept-bar-fill{{height:100%;background:linear-gradient(90deg,#c8a45a 0%,#e9c988 100%);border-radius:999px;transition:width 0.3s ease}}
.rr-dept-value{{font-size:11.5px;font-weight:700;color:#f3dfa9;text-align:right;font-variant-numeric:tabular-nums}}
.rr-trend-grid{{display:grid;gap:5px}}
.rr-trend-row{{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:6px 10px;background:rgba(200,164,90,0.04);border:1px solid rgba(200,164,90,0.12);border-radius:5px}}
.rr-trend-dept{{font-size:11.5px;color:#cbd5e1;font-weight:500}}
.rr-trend-delta{{font-size:12px;font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:0.3px}}
.rr-trend-up{{color:#34d399}}
.rr-trend-down{{color:#f87171}}
/* Tab 2 variant removed in v7.1.4 post-review — Tab 2 no longer injects the
   .rr-enrich-section card; it uses the markdown-styled builder
   (build_rocketreach_enrichment_tab2) that emits native .md-h2/.md-h3/.md-li-kv/
   .md-table elements instead. Keeping the 30-line `.dossier-verbatim .rr-enrich-*`
   override block was dead weight. */

/* Tab 2 — side-by-side pair for Department Headcount + Workforce Trajectory.
   Each cell holds a sub-head + md-table; on wide viewports they pack into a
   2-column grid so the RR section doesn't waste vertical real estate; below
   720px they stack back to a single column for readability. Negative
   margin-top on the second cell's h4 cancels the default md-h3 top-margin
   so both headings align. */
.dossier-verbatim .rr-tab2-pair{{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start;margin:10px 0 14px 0}}
.dossier-verbatim .rr-tab2-pair-cell{{min-width:0}}
.dossier-verbatim .rr-tab2-pair-cell > .md-h3:first-child{{margin-top:0}}
.dossier-verbatim .rr-tab2-pair .md-table{{min-width:0}}
@media (max-width:720px){{.dossier-verbatim .rr-tab2-pair{{grid-template-columns:1fr}}}}

/* ---- Decision Tree Flowchart ---------------------------------------- */
.dt-wrap{{padding:4px 0}}
.dt-trigger{{display:flex;align-items:center;gap:14px;padding:14px 18px;background:linear-gradient(135deg,rgba(99,102,241,0.18),rgba(139,92,246,0.10));border:1px solid rgba(99,102,241,0.4);border-radius:12px;margin-bottom:10px}}
.dt-trigger-icon{{flex:0 0 38px;height:38px;width:38px;border-radius:50%;background:#6366f1;color:#fff;display:flex;align-items:center;justify-content:center;font-size:14px;box-shadow:0 0 0 4px rgba(99,102,241,0.18)}}
.dt-trigger-body{{flex:1}}
.dt-trigger-label{{font-size:9.5px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#a5b4fc;margin-bottom:3px}}
.dt-trigger-text{{font-size:14.5px;font-weight:700;color:#f1f5f9;line-height:1.35}}
.dt-intro{{font-size:13px;color:#94a3b8;line-height:1.55;margin:14px 4px 18px;padding-left:14px;border-left:2px solid rgba(99,102,241,0.3);font-style:italic}}
.dt-branches{{display:flex;flex-direction:column;gap:14px;position:relative}}
.dt-branches::before{{content:'';position:absolute;left:18px;top:-4px;bottom:0;width:2px;background:linear-gradient(180deg,rgba(99,102,241,0.4),transparent);pointer-events:none}}
.dt-row{{display:grid;grid-template-columns:38px 1fr;gap:14px;position:relative}}
.dt-row-num{{height:38px;width:38px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:800;flex-shrink:0;align-self:start;z-index:1;box-shadow:0 0 0 3px #0f172a}}
.dt-row-body{{display:flex;flex-direction:column;gap:8px;padding:6px 0}}
.dt-cond{{display:flex;align-items:flex-start;gap:10px;padding:10px 14px;background:rgba(255,255,255,0.02);border-left:3px solid;border-radius:0 8px 8px 0}}
.dt-tag{{display:inline-block;font-size:9.5px;font-weight:800;letter-spacing:1.2px;padding:3px 8px;border-radius:4px;flex-shrink:0;line-height:1.3;margin-top:1px}}
.dt-tag-action{{box-shadow:0 1px 3px rgba(0,0,0,0.2)}}
.dt-cond-text{{font-size:12.5px;color:#e2e8f0;line-height:1.5;font-weight:500}}
.dt-arrow{{font-size:18px;font-weight:700;text-align:center;line-height:1;margin:-4px 0 -4px 0;opacity:0.7}}
.dt-action{{display:flex;align-items:flex-start;gap:10px;padding:12px 14px;background:rgba(99,102,241,0.05);border:1px solid;border-radius:8px}}
.dt-action-text{{font-size:12.5px;color:#f1f5f9;line-height:1.5;font-weight:500}}
.dt-outcome{{display:flex;align-items:flex-start;gap:8px;padding:8px 14px;font-size:11.5px;color:#94a3b8;line-height:1.5;font-style:italic}}
.dt-outcome-icon{{font-size:14px;flex-shrink:0;line-height:1.3}}
.dt-outcome-text{{flex:1}}

/* Responsive: scenario cards and fingerprint grid stack on narrower screens */
@media (max-width: 900px) {{
  .sc-grid{{grid-template-columns:repeat(2,1fr)}}
  .wf-grid{{grid-template-columns:repeat(2,1fr)}}
}}
@media (max-width: 600px) {{
  .sc-grid{{grid-template-columns:1fr}}
  .wf-grid{{grid-template-columns:1fr}}
  .sc-score-new{{font-size:28px}}
  .dt-trigger{{padding:12px 14px}}
  .dt-trigger-text{{font-size:13px}}
  .dt-row{{grid-template-columns:32px 1fr;gap:10px}}
  .dt-row-num{{height:32px;width:32px;font-size:13px}}
  .dt-branches::before{{left:15px}}
}}

/* PRINT: infographics print cleanly on light theme */
@media print {{
  .infographic-section::before{{display:none}}
  .attr-bar-shell{{height:48px}}
  .attr-bar{{background:#f1f5f9;box-shadow:inset 0 0 0 1px #e5e7eb}}
  .attr-seg{{border-right-color:rgba(255,255,255,0.4)}}
  .attr-cap-flag{{background:#d97706;color:#fff}}
  .attr-caption{{background:#f8fafc !important;color:#374151 !important;border-left-color:#6366f1 !important}}
  .attr-caption-note{{color:#6b7280 !important}}
  .attr-leg-row{{background:#f8fafc !important}}
  .attr-leg-cat{{color:#1f2937 !important}}
  .attr-leg-pts{{background:#eef2ff !important;color:#4338ca !important}}
  .attr-leg-evidence{{color:#6b7280 !important}}
  .sc-card{{background:#fff !important;border-color:#e5e7eb !important;page-break-inside:avoid;box-shadow:none !important}}
  .sc-card-head{{background:#fafafa !important}}
  .sc-score-old{{color:#9ca3af !important}}
  .sc-score-suffix{{color:#6b7280 !important}}
  .sc-label{{color:#0f172a !important}}
  .sc-block-title{{color:#6b7280 !important}}
  .sc-block-text{{color:#374151 !important}}
  .sc-trigger{{background:#f8fafc !important}}
  .wf-cat{{background:#fff !important;border-color:#e5e7eb !important;page-break-inside:avoid}}
  .wf-cat-title{{color:#0f172a !important}}
  .wf-cat-count{{background:#eef2ff !important;color:#4338ca !important}}
  .wf-badge{{background:#f8fafc !important;color:#1f2937 !important}}
  .wf-ver{{color:#6b7280 !important}}
  .wf-legend{{background:#f8fafc !important;color:#374151 !important;border-color:#e5e7eb !important}}
  .wf-legend-item{{color:#374151 !important}}
  .wf-legend-hint{{color:#6b7280 !important}}
  .dt-trigger{{background:#eef2ff !important;border-color:#a5b4fc !important;page-break-inside:avoid}}
  .dt-trigger-text{{color:#0f172a !important}}
  .dt-trigger-label{{color:#4338ca !important}}
  .dt-intro{{color:#4b5563 !important;border-left-color:#a5b4fc !important}}
  .dt-row{{page-break-inside:avoid}}
  .dt-cond{{background:#fafafa !important}}
  .dt-cond-text{{color:#1f2937 !important}}
  .dt-action{{background:#fff !important}}
  .dt-action-text{{color:#0f172a !important}}
  .dt-outcome{{color:#6b7280 !important}}
  .dt-branches::before{{background:linear-gradient(180deg,#cbd5e1,transparent) !important}}
  .dt-row-num{{box-shadow:0 0 0 3px #fff !important}}
}}

/* PRINT: both tabs visible, stacked, with page break between */
@media print {{
  .tab-nav{{display:none !important}}
  .tab-panel{{display:block !important;animation:none}}
  #tab-dossier{{page-break-before:always}}
  #tab-dossier .dossier-verbatim{{background:#fff;border:1px solid #e5e7eb;color:#1f2937;padding:24px 28px}}
  #tab-dossier .md-h1{{color:#0f172a;border-bottom-color:#4338ca}}
  #tab-dossier .md-h2{{color:#4338ca;border-bottom-color:#e5e7eb}}
  #tab-dossier .md-h3{{color:#1f2937}}
  #tab-dossier .md-h4{{color:#6b7280}}
  #tab-dossier .md-p,#tab-dossier .md-list li{{color:#374151}}
  #tab-dossier strong{{color:#0f172a}}
  #tab-dossier em{{color:#4338ca}}
  #tab-dossier code,#tab-dossier .md-code{{background:#eef2ff;color:#4338ca}}
  #tab-dossier .md-hr{{border-top-color:#e5e7eb}}
  #tab-dossier .md-table-wrap{{border-color:#e5e7eb}}
  #tab-dossier .md-table th{{background:#f1f5f9;color:#0f172a;border-bottom-color:#cbd5e1;position:static}}
  #tab-dossier .md-table td{{color:#4b5563;border-bottom-color:#e5e7eb}}
  #tab-dossier .md-table tbody tr:nth-child(even) td{{background:#fafafa}}
  #tab-dossier .md-table tbody tr:hover td{{background:#fafafa}}
  #tab-dossier .md-table,#tab-dossier .dossier-verbatim{{page-break-inside:auto}}
  #tab-dossier .md-table tr,#tab-dossier .md-h2,#tab-dossier .md-h3{{page-break-inside:avoid}}

  /* v5.7 — Pills, tier badges, auto-links in print */
  #tab-dossier .md-anchor{{display:none}}
  #tab-dossier .md-link{{color:#4338ca;border-bottom-color:#4338ca}}
  #tab-dossier .md-pill-confirmed{{background:#d1fae5;color:#047857;border-color:#059669}}
  #tab-dossier .md-pill-estimated{{background:#fef3c7;color:#b45309;border-color:#d97706}}
  #tab-dossier .md-pill-inferred{{background:#f3f4f6;color:#4b5563;border-color:#9ca3af}}
  #tab-dossier .md-tier-a{{background:#d1fae5;color:#047857;border-color:#059669}}
  #tab-dossier .md-tier-b{{background:#fef3c7;color:#b45309;border-color:#d97706}}
  #tab-dossier .md-tier-c{{background:#f3f4f6;color:#4b5563;border-color:#9ca3af}}

  /* v5.7 — Evidence chips in print (summary tab) */
  .evidence-chip{{background:#eef2ff !important;color:#4338ca !important;border-color:#a5b4fc !important}}

  /* v5.7 — Source Quality Donut + DMU Map — force print colors */
  .sq-caption{{background:#f8fafc !important;color:#475569 !important;border-left-color:#6366f1 !important}}
  .sq-legend-label{{color:#374151 !important}}
  .sq-legend-count{{color:#0f172a !important}}
  .sq-legend-pct{{color:#6b7280 !important}}
  .dmu-legend{{background:#f8fafc !important;border-color:#e5e7eb !important;page-break-inside:avoid}}
  .dmu-legend-item{{color:#374151 !important}}
  .dmu-map-wrap svg text.dmu-name{{fill:#1f2937 !important}}
  .dmu-map-wrap svg text.dmu-title{{fill:#6b7280 !important}}
  .dmu-map-wrap svg text.dmu-edge-label{{fill:#6b7280 !important}}

  /* v6.0 — Signal Timeline legend in print */
  .tl-legend{{background:#f8fafc !important;border-color:#e5e7eb !important;page-break-inside:avoid}}
  .tl-legend-item{{color:#374151 !important}}
  .tl-legend-label{{color:#374151 !important}}
  .signal-timeline-wrap{{page-break-inside:avoid}}

  .source-quality-wrap{{page-break-inside:avoid}}
  .dmu-map-wrap{{page-break-inside:avoid}}
}}
@page{{size:A4;margin:1.5cm}}
</style>
</head>
<body>
<div class="page">

  <!-- Header -->
  <div class="report-header">
    <div class="header-brand">
      <div class="brand-mark">ELISS Intelligence Dossier v{ELISS_DISPLAY_VERSION}</div>
      <div class="header-date">{escape_html(meta.get('generated', datetime.now().strftime('%Y-%m-%d')))} &bull; ManageEngine</div>
    </div>
    <div class="lead-name">{escape_html(_extract_value(lead.get('name'), 'Unknown Lead'))}</div>
    <div class="lead-sub">{escape_html(_clean_lead_title(_extract_value(lead.get('title'), '')))} at {escape_html(_extract_value(company.get('name'), 'Unknown'))} &bull; {escape_html(_extract_value(lead.get('email'), ''))}</div>
  </div>

  <!-- Tab Navigation (v7.0.2 — full aria-controls wiring for screen readers) -->
  <main id="eliss-main">
  <div class="tab-nav" role="tablist" aria-label="Dossier views">
    <button class="tab-btn active" data-tab="summary" role="tab" id="tab-ctrl-summary" aria-selected="true" aria-controls="tab-summary" tabindex="0">Executive Summary</button>
    <button class="tab-btn" data-tab="dossier" role="tab" id="tab-ctrl-dossier" aria-selected="false" aria-controls="tab-dossier" tabindex="-1">Complete Intelligence Dossier</button>
  </div>

  <!-- ======================================================== -->
  <!-- TAB 1: Executive Summary (visualizations + key sections)  -->
  <!-- ======================================================== -->
  <div class="tab-panel active" id="tab-summary" role="tabpanel" aria-labelledby="tab-ctrl-summary">

  <!-- 5-Second Verdict Banner -->
  {build_verdict_banner(data)}

  <!-- Score Hero: Gauge + Radar + Bars -->
  <div class="score-hero">
    <div class="score-hero-top">
      <div class="score-visual">
        {svg_score_gauge(final_score, 100, 160, tier)}
        <div class="score-radar-label">COMPOSITE</div>
      </div>
      <div class="score-radar">
        {svg_radar_chart(scoring, 260)}
        <div class="score-radar-label">4-DIMENSION PROFILE</div>
      </div>
      <div class="score-meta">
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
          <span class="tier-label">{tier}</span>
          <span class="conf-label">{conf} Confidence</span>
          <span class="icp-label">ICP: {escape_html(icp_match)}</span>
        </div>
        {f'<div class="icp-reason">{escape_html(icp_reason)}</div>' if icp_reason else ''}
      </div>
    </div>
    <div class="score-dim-section">
      <div class="dim-bars">{dims_html}</div>
    </div>
  </div>

  <!-- Executive Brief -->
  <div class="section">
    <div class="section-title">Executive Brief</div>
    <div class="exec-brief">{escape_html(_resolve_executive_brief(data))}</div>
  </div>

  <!-- Validation Rules -->
  <div class="section">
    <div class="section-title">Score Validation</div>
    {build_validation_visual(scoring)}
  </div>

  <!-- v6.2 INFOGRAPHIC: Score Attribution — where the Intent score came from -->
  {(lambda html: f'<div class="section infographic-section"><div class="section-title">Score Attribution — Where the Intent Points Came From</div>{html}</div>' if html else '')(build_score_attribution_bar(scoring))}

  <!-- v6.2 INFOGRAPHIC: Scenario Cards — what-if score modulators -->
  {(lambda html: f'<div class="section infographic-section"><div class="section-title">What-If Scenarios</div><div class="sc-intro">Three signals from the next call that materially shift this score. Each card shows the score delta, the underlying logic, and the precise trigger phrase to listen for.</div>{html}</div>' if html else '')(build_scenario_cards(scoring))}

  <!-- v5.6: Deal Execution Risks + Risk-Adjusted Composite -->
  <div class="section">
    <div class="section-title">Deal Execution Risks</div>
    {build_deal_execution_risks_html(scoring)}
  </div>

  <!-- Intent Donut -->
  <div class="section">
    <div class="section-title">Intent Signal Breakdown</div>
    {svg_intent_donut(scoring.get('intent', {}), 200)}
  </div>

  <!-- Signal Timeline -->
  <div class="section">
    <div class="section-title">Buying Signals Timeline</div>
    {svg_signal_timeline(signals)}
  </div>

  <!-- Person + Company -->
  <div class="profile-grid">
    <div class="section">
      <div class="section-title">Person Profile</div>
      <div class="field"><span class="field-label">Name</span><span class="field-value">{escape_html(_extract_value(lead.get('name'), ''))}{_rr_pill(lead.get('_rocketreach_name'))}</span></div>
      <div class="field"><span class="field-label">Title</span><span class="field-value">{escape_html(_clean_lead_title(_extract_value(lead.get('title'), '')))}{_rr_pill(lead.get('_rocketreach_title'))}</span></div>
      <div class="field"><span class="field-label">Seniority</span><span class="field-value">{escape_html(_extract_value(lead.get('seniority'), ''))}</span></div>
      <div class="field"><span class="field-label">Authority</span><span class="field-value">{escape_html(_extract_value(lead.get('authority'), ''))}</span></div>
      <div class="field"><span class="field-label">Tenure</span><span class="field-value">{escape_html(_extract_value(lead.get('tenure'), 'Unknown'))}</span></div>
      {build_rr_person_extras(lead)}
    </div>
    <div class="section">
      <div class="section-title">Company Profile</div>
      <div class="field"><span class="field-label">Company</span><span class="field-value">{escape_html(_extract_value(company.get('name'), ''))}</span></div>
      <div class="field"><span class="field-label">Industry</span><span class="field-value">{industry_display}{(' — ' + escape_html(_extract_value(company.get('sub_industry')))) if _extract_value(company.get('sub_industry')) else ''}</span></div>
      <div class="field"><span class="field-label">Employees</span><span class="field-value">{employees_display}<span class="field-tag tag-{str(company.get('employees_confidence', 'estimated')).lower()}">{escape_html(str(company.get('employees_confidence', 'ESTIMATED')))}</span></span></div>
      <div class="field"><span class="field-label">Revenue</span><span class="field-value">{revenue_display}<span class="field-tag tag-estimated">EST</span></span></div>
      <div class="field"><span class="field-label">HQ</span><span class="field-value">{escape_html(_extract_value(company.get('hq'), ''))}</span></div>
      <div class="field"><span class="field-label">Ownership</span><span class="field-value">{escape_html(_extract_value(company.get('ownership'), ''))}</span></div>
    </div>
  </div>

  <!-- Technology & Security -->
  <div class="section">
    <div class="section-title">Technology & Security Posture</div>
    <div class="field-grid">
      <div class="field"><span class="field-label">AD/Identity</span><span class="field-value">{escape_html(_extract_value(tech.get('ad_environment'), 'Unknown'))}</span></div>
      <div class="field"><span class="field-label">Cloud</span><span class="field-value">{escape_html(_extract_value(tech.get('cloud_posture'), 'Unknown'))}</span></div>
      <div class="field"><span class="field-label">Maturity</span><span class="field-value">{escape_html(_extract_value(tech.get('digital_maturity'), 'Unknown'))}</span></div>
    </div>
    <div style="margin-top:12px">
      <div class="field"><span class="field-label">Security Stack</span><span class="field-value">{tech_pills}</span></div>
      <div class="field"><span class="field-label">Competitors</span><span class="field-value">{comp_pills}</span></div>
    </div>
    {"<div class='strategy-note'><strong>Displacement Angle:</strong> " + escape_html(_extract_value(tech.get('displacement_angle'))) + "</div>" if _extract_value(tech.get('displacement_angle')) else ""}
  </div>

  <!-- v6.2 INFOGRAPHIC: Web Tech Fingerprint — categorized stack badges -->
  {(lambda html: f'<div class="section infographic-section"><div class="section-title">Web Property Tech Fingerprint</div><div class="wf-intro">Beyond DNS-confirmed identity stack — what their web property reveals about technology buying patterns. Each badge represents a vendor relationship with budget, contract, and potential adjacent spend.</div>{html}</div>' if html else '')(build_web_fingerprint(tech))}

  <!-- v7.1.3 INFOGRAPHIC: RocketReach Firmographic Enrichment -->
  {(lambda html: f'<div class="section rr-enrich-section"><div class="section-title rr-enrich-title">RocketReach Firmographic Enrichment</div>{html}</div>' if html else '')(build_rocketreach_enrichment(data))}

  <!-- IT Budget — text + waterfall chart -->
  <div class="section">
    <div class="section-title">IT Budget & Purchasing Power</div>
    <div class="field-grid">
      <div class="field"><span class="field-label">IT Spend</span><span class="field-value">{escape_html(_extract_value(budget.get('estimated_it_spend'), 'Unknown'))}<span class="field-tag tag-estimated">EST</span></span></div>
      <div class="field"><span class="field-label">Security Budget</span><span class="field-value">{escape_html(_extract_value(budget.get('security_budget'), 'Unknown'))}<span class="field-tag tag-estimated">EST</span></span></div>
      <div class="field"><span class="field-label">Affordability</span><span class="field-value">{escape_html(_extract_value(budget.get('affordability'), 'Unknown'))}</span></div>
      <div class="field"><span class="field-label">Budget Trend</span><span class="field-value">{escape_html(_extract_value(budget.get('budget_trend'), 'Unknown'))}</span></div>
      <div class="field"><span class="field-label">Deal Authority</span><span class="field-value">{escape_html(_extract_value(budget.get('deal_authority'), 'Unknown'))}</span></div>
      <div class="field"><span class="field-label">Deal Cycle</span><span class="field-value">{escape_html(_extract_value(budget.get('deal_cycle_months'), 'Unknown'))} months</span></div>
    </div>
    {"<div class='strategy-note' style='margin-top:12px'><strong>Basis:</strong> " + escape_html(budget.get('calculation_basis', '')) + "</div>" if budget.get('calculation_basis') else ""}
    <div style="margin-top:16px">
      {svg_budget_waterfall(budget, company=company)}
    </div>
  </div>

  <!-- DMU Org Chart -->
  <div class="section">
    <div class="section-title">Decision-Making Unit</div>
    {svg_dmu_orgchart(org)}
    {f'<div class="strategy-note" style="margin-top:12px"><strong>Multi-Thread Strategy:</strong> {escape_html(org.get("multi_thread_strategy", ""))}</div>' if org.get('multi_thread_strategy') else ''}
  </div>

  <!-- v5.7: DMU + Ghost Stakeholder Map -->
  <div class="section">
    <div class="section-title">Decision-Making Unit &amp; Ghost Stakeholder Map</div>
    {svg_dmu_ghost_map(org, lead=lead)}
  </div>

  <!-- Compliance Heatmap -->
  <div class="section">
    <div class="section-title">Compliance Pressure Map</div>
    {build_compliance_heatmap(compliance)}
  </div>

  <!-- v5.6: Competitive Threat Matrix -->
  <div class="section">
    <div class="section-title">Competitive Threat Matrix</div>
    {build_competitive_matrix_html(tech)}
  </div>

  <!-- v7.4 INFOGRAPHIC: Demo Playbook — persona-anchored AD360+Log360 scripts -->
  {(lambda html: f'<div class="section infographic-section"><div class="section-title">Demo Playbook</div>{html}</div>' if html else '')(build_demo_playbook_html(data.get('demo_playbook', {})))}

  <!-- Signals List -->
  <div class="section">
    <div class="section-title">Signal Detail</div>
    {build_signals_html(signals)}
  </div>

  <!-- Recommendations -->
  <div class="section">
    <div class="section-title">Strategic Recommendations</div>
    {build_recommendations_html(recs, tier)}
  </div>

  <!-- v6.2 INFOGRAPHIC: First-Call Decision Tree — branch-by-signal playbook -->
  {(lambda html: f'<div class="section infographic-section"><div class="section-title">First-Call Decision Tree</div>{html}</div>' if html else '')(build_decision_tree(recs))}

  <!-- v7.2: Recommended Outreach — dossier-driven follow-up email sequence -->
  <div class="section">
    <div class="section-title">Recommended Outreach — Follow-Up Email Sequence</div>
    {build_recommended_outreach_html(data.get('recommended_outreach', []))}
  </div>

  <!-- v5.6: Ghost Stakeholders -->
  <div class="section">
    <div class="section-title">Ghost Stakeholders — Open Roles in Hiring Pipeline</div>
    {build_ghost_stakeholders_html(org)}
  </div>

  {peer_html}

  <!-- v5.7: Source Quality Donut + Sources list -->
  <div class="section">
    <div class="section-title">Research Sources &amp; Quality Breakdown</div>
    {svg_source_quality_donut(sources)}
    <div style="margin-top:16px;padding-top:16px;border-top:1px solid rgba(99,102,241,0.15)">
      {sources_html if sources_html else '<p class="empty">Sources listed in conversational dossier</p>'}
    </div>
  </div>

  <!-- Data Quality -->
  <div class="section">
    <div class="section-title">Data Quality & Confidence</div>
    <div style="display:flex;gap:8px;margin-bottom:12px">
      <span class="conf-label">{escape_html(dq.get('overall_confidence', 'MEDIUM'))} Overall Confidence</span>
    </div>
    <div class="dq-grid">
      <div><h3>Key Assumptions</h3><ul class="dq-list">{assumptions_html if assumptions_html else '<li>None noted</li>'}</ul></div>
      <div><h3>Data Gaps</h3><ul class="dq-list">{gaps_html if gaps_html else '<li>None noted</li>'}</ul></div>
    </div>
  </div>

  <!-- v5.6: Pre-Mortem -->
  <div class="section">
    <div class="section-title">Pre-Mortem — Why We Might Lose This Deal</div>
    {build_pre_mortem_html(data.get('pre_mortem', []))}
  </div>

  <!-- v5.6: Rep Readiness Checklist -->
  <div class="section">
    <div class="section-title">Rep Readiness Checklist</div>
    {build_rep_readiness_html(data.get('rep_readiness_checklist', []))}
  </div>

  </div><!-- /tab-summary -->

  <!-- ======================================================== -->
  <!-- TAB 2: Complete Intelligence Dossier (verbatim dossier)   -->
  <!-- ======================================================== -->
  <div class="tab-panel" id="tab-dossier" role="tabpanel" aria-labelledby="tab-ctrl-dossier">
    <div class="dossier-verbatim">
      {full_dossier_html}
    </div>
  </div><!-- /tab-dossier -->
  </main><!-- /eliss-main -->

  <!-- Footer -->
  <div class="report-footer">
    <strong>ELISS v{ELISS_DISPLAY_VERSION}</strong> — Enterprise Lead Intelligence & Scoring System<br>
    ManageEngine AD360 & Log360 Sales Intelligence &bull; {escape_html(meta.get('generated', datetime.now().strftime('%Y-%m-%d')))} &bull; Confidential
  </div>
</div>

<script>
(function() {{
  var btns = document.querySelectorAll('.tab-btn');
  var panels = document.querySelectorAll('.tab-panel');
  btns.forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      var target = btn.getAttribute('data-tab');
      btns.forEach(function(b) {{
        var active = b.getAttribute('data-tab') === target;
        b.classList.toggle('active', active);
        b.setAttribute('aria-selected', active ? 'true' : 'false');
      }});
      panels.forEach(function(p) {{
        p.classList.toggle('active', p.id === 'tab-' + target);
      }});
      window.scrollTo({{top: 0, behavior: 'smooth'}});
    }});
  }});

  // v7.2 — Recommended Outreach: copy-to-clipboard handler.
  // Email payload is JSON-encoded into data-copy-payload (subject + body) so
  // newlines and quotes survive HTML round-tripping. We parse the JSON, write
  // it to the clipboard, and flash the button green for 1.4s. Fallback path
  // uses a transient textarea + execCommand for older browsers / file:// URLs
  // where navigator.clipboard isn't permitted.
  document.querySelectorAll('.copy-btn').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      var raw = btn.getAttribute('data-copy-payload') || '""';
      var text = '';
      try {{ text = JSON.parse(raw); }} catch (e) {{ text = raw; }}
      var done = function() {{
        var orig = btn.textContent;
        btn.classList.add('copied');
        btn.textContent = 'Copied';
        setTimeout(function() {{
          btn.classList.remove('copied');
          btn.textContent = orig;
        }}, 1400);
      }};
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        navigator.clipboard.writeText(text).then(done, function() {{
          // fallthrough to legacy path
          legacyCopy(text, done);
        }});
      }} else {{
        legacyCopy(text, done);
      }}
    }});
  }});
  function legacyCopy(text, cb) {{
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'absolute';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try {{ document.execCommand('copy'); cb(); }} catch (e) {{}}
    document.body.removeChild(ta);
  }}
}})();
</script>
</body>
</html>'''
    return html


# =============================================================================
#  PDF GENERATION + MAIN
# =============================================================================

def generate_pdf_from_html(html_content, output_path):
    """Generate PDF from HTML."""
    try:
        from weasyprint import HTML as WP
        WP(string=html_content).write_pdf(str(output_path))
        return True
    except ImportError:
        pass
    except Exception:
        pass
    try:
        import pdfkit
        pdfkit.from_string(html_content, str(output_path), options={'quiet': ''})
        return True
    except (ImportError, Exception):
        pass
    return False


def fallback_from_markdown(md_content):
    """If given a .md file instead of .json, build a minimal JSON structure from it."""
    data = {
        'meta': {'version': '6.1', 'generated': datetime.now().strftime('%Y-%m-%d')},
        'lead': {'name': 'Unknown', 'email': '', 'title': ''},
        'company': {'name': 'Unknown'},
        'scoring': {'final_score': 0, 'tier': 'COLD', 'overall_confidence': 'LOW',
                    'fit': {'score': 0}, 'intent': {'score': 0}, 'timing': {'score': 0}, 'budget': {'score': 0}},
        'executive_brief': '',
        'signals': {}, 'compliance': [], 'org_intelligence': {},
        'budget_analysis': {}, 'technology': {},
        'recommendations': {}, 'sources': {}, 'data_quality': {},
    }
    m = re.search(r'\*\*Lead:\*\*\s*([^|]+)', md_content)
    if m: data['lead']['name'] = m.group(1).strip()
    m = re.search(r'\*\*Company:\*\*\s*([^|]+)', md_content)
    if m: data['company']['name'] = m.group(1).strip()
    m = re.search(r'\*\*Email:\*\*\s*(\S+)', md_content)
    if m: data['lead']['email'] = m.group(1).strip()
    m = re.search(r'\*\*Final Score:\*\*\s*(\d+)/100', md_content)
    if m: data['scoring']['final_score'] = int(m.group(1))
    m = re.search(r'\*\*Tier:\*\*\s*(HOT|WARM|COOL|COLD)', md_content)
    if m: data['scoring']['tier'] = m.group(1)
    m = re.search(r'\*\*Confidence:\*\*\s*(HIGH|MEDIUM|LOW)', md_content)
    if m: data['scoring']['overall_confidence'] = m.group(1)
    data['executive_brief'] = md_content[:500] + '...'
    return data


def _try_enrich_with_rocketreach(data):
    """
    v6.1+: Optional RocketReach enrichment of Layer 5 DMU records.

    Called by main() between JSON load and render. Reads the RR_API_KEY
    environment variable; returns data unchanged (and silently) when the
    variable is unset. Any RocketReach error — network failure, 401, 429,
    cap exceeded, module missing — degrades gracefully to "use whatever is
    already in the JSON" without aborting report generation.

    Enrichment rules (conservative — respects analyst-curated data):
      * Never overwrites existing non-empty fields on a DMU record
      * Fills missing linkedin_url, verified_emails, verified_phones,
        and a separate `rocketreach_verified_title` (so the analyst's
        original `title` is preserved for comparison)
      * Marks the record with `rocketreach_enriched: true` and
        `rocketreach_source_tier: "B"` (per ELISS source-tier rules —
        never Tier-A, never exceeds HIGH-confidence cap without a Tier-A
        corroborator)
      * Adds one entry per call to `data_quality.sources_actually_checked[]`
        with `access_method: "rocketreach_api"`

    Budget: capped by the RocketReachClient defaults — max 1 company lookup
    and 5 person lookups per dossier. A typical DMU (Economic Buyer,
    Champion, Technical Evaluator, Primary Contact, optional Blocker) fits
    exactly under the person cap.

    Idempotent on re-runs: a DMU record already marked `rocketreach_enriched`
    is skipped.

    Returns the (potentially mutated) `data` dict. Does not raise on failure.
    """
    import os as _os
    if not _os.environ.get('RR_API_KEY', '').strip():
        # No key → silent no-op. Don't spam stderr.
        return data

    # Lazy import so the generator doesn't hard-depend on the RR client module
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from rocketreach_client import (  # type: ignore
            RocketReachClient,
            RocketReachAuthError,
            RocketReachCapExceeded,
            RocketReachError,
            RocketReachNotFound,
            RocketReachRateLimited,
        )
    except ImportError as e:
        print(f"[eliss] RR_API_KEY is set but rocketreach_client unavailable "
              f"({e}); falling back to free OSINT.", file=sys.stderr)
        return data

    try:
        client = RocketReachClient()
    except RocketReachAuthError as e:
        print(f"[eliss] RocketReach auth failed ({e}); falling back to free OSINT.",
              file=sys.stderr)
        return data
    except Exception as e:  # defensive: module-version mismatch, etc.
        print(f"[eliss] RocketReach init failed ({e}); falling back to free OSINT.",
              file=sys.stderr)
        return data

    org = data.setdefault('org_intelligence', {})
    lead = data.get('lead', {}) or {}
    dq = data.setdefault('data_quality', {})
    checked = dq.setdefault('sources_actually_checked', [])

    # Derive prospect company + domain for context
    def _company_from(*dicts):
        for d in dicts:
            v = (d or {}).get('company') or (d or {}).get('employer') or ''
            if v: return v
        return ''

    company_name = (_company_from(lead)
                    or _company_from(org.get('champion'), org.get('economic_buyer'))
                    or (data.get('company') or {}).get('name', ''))
    email = (lead.get('email') or '').strip()
    company_domain = email.split('@', 1)[1].lower() if '@' in email else ''

    # --- 1. Company lookup (at most 1) -------------------------------------
    # Skip if firmographics already has a rocketreach-sourced entry (idempotent).
    firm = data.setdefault('firmographics', {})
    already_enriched_co = firm.get('_rocketreach_enriched', False)
    if (company_domain or company_name) and not already_enriched_co:
        try:
            co = client.lookup_company(
                domain=(company_domain or None),
                name=(company_name or None),
            )
            if co:
                for k_rr, k_eliss in [
                    ('employees', 'employee_count'),
                    ('industry', 'industry'),
                    ('description', 'description'),
                    ('headquarters', 'hq_location'),
                ]:
                    v = co.get(k_rr)
                    if v and not firm.get(k_eliss):
                        firm[k_eliss] = v
                        firm[f'_{k_eliss}_source'] = 'rocketreach'
                firm['_rocketreach_enriched'] = True
                checked.append({
                    'source': f'RocketReach API — company lookup '
                              f'({company_domain or company_name})',
                    'access_method': 'rocketreach_api', 'layer': 1,
                    'yielded_signal': True,
                })
            else:
                checked.append({
                    'source': f'RocketReach API — company lookup '
                              f'({company_domain or company_name})',
                    'access_method': 'rocketreach_api', 'layer': 1,
                    'yielded_signal': False,
                })
        except (RocketReachCapExceeded, RocketReachNotFound):
            pass  # caps hit or no match; not fatal
        except (RocketReachRateLimited, RocketReachError) as e:
            print(f"[eliss] RR company lookup failed: {type(e).__name__}",
                  file=sys.stderr)
            # Log the failed attempt so the Research Coverage panel shows it
            # was tried (transparency philosophy — don't silently skip).
            checked.append({
                'source': f'RocketReach API — company lookup '
                          f'({company_domain or company_name}) [failed]',
                'access_method': 'rocketreach_api', 'layer': 1,
                'yielded_signal': False,
            })

    # --- 2. Person lookups — up to 5 DMU members ---------------------------
    dmu_queue = [
        ('economic_buyer', org.get('economic_buyer', {}) or {}),
        ('champion', org.get('champion', {}) or {}),
        ('technical_evaluator', org.get('technical_evaluator', {}) or {}),
        ('blocker', org.get('blocker', {}) or {}),
    ]
    # Include primary contact from `lead` if they aren't already a mapped DMU role
    lead_name = (lead.get('name') or '').strip()
    if lead_name:
        already = any(
            (m.get('name') or '').strip().lower() == lead_name.lower()
            for _, m in dmu_queue
        )
        if not already:
            dmu_queue.append(('_primary_contact', {
                'name': lead_name,
                'title': lead.get('title', ''),
                'linkedin_url': lead.get('linkedin_url', ''),
                'email': email,
            }))

    for role_key, member in dmu_queue:
        name = (member.get('name') or '').strip()
        if not name or name.lower() in ('unknown', '—', '-', 'n/a', 'tbd'):
            continue
        if member.get('rocketreach_enriched'):
            continue  # idempotency — don't re-bill the API on re-runs

        linkedin = (member.get('linkedin_url') or '').strip()
        employer = (member.get('company') or company_name or '').strip()
        member_email = (member.get('email') or '').strip()
        # Need at least one strong identifier to avoid wasting credits
        if not (linkedin or member_email or (name and employer)):
            continue

        try:
            rr = client.lookup_person(
                name=name,
                current_employer=(employer or None),
                linkedin_url=(linkedin or None),
                email=(member_email or None),
            )
            yielded = False
            if rr:
                # Fill MISSING fields only — preserve analyst-curated values
                if not member.get('linkedin_url') and rr.get('linkedin_url'):
                    member['linkedin_url'] = rr['linkedin_url']; yielded = True
                if not member.get('rocketreach_verified_title') and rr.get('current_title'):
                    member['rocketreach_verified_title'] = rr['current_title']; yielded = True
                if not member.get('verified_emails') and rr.get('emails'):
                    emails = [e.get('email') for e in rr['emails'] if isinstance(e, dict) and e.get('email')]
                    if emails:
                        member['verified_emails'] = emails; yielded = True
                if not member.get('verified_phones') and rr.get('phones'):
                    phones = [p.get('number') for p in rr['phones'] if isinstance(p, dict) and p.get('number')]
                    if phones:
                        member['verified_phones'] = phones; yielded = True
                member['rocketreach_enriched'] = True
                member['rocketreach_source_tier'] = 'B'
                # Write back to org (except for the synthesized primary_contact)
                if role_key != '_primary_contact':
                    org[role_key] = member
            checked.append({
                'source': f'RocketReach API — person lookup ({name})',
                'access_method': 'rocketreach_api', 'layer': 5,
                'yielded_signal': yielded,
            })
        except RocketReachCapExceeded:
            print("[eliss] RocketReach person-lookup cap reached; remaining DMU "
                  "members will use free OSINT only.", file=sys.stderr)
            break
        except RocketReachRateLimited:
            print("[eliss] RocketReach rate-limited (429); degrading to free OSINT "
                  "for remaining lookups.", file=sys.stderr)
            break
        except RocketReachNotFound:
            checked.append({
                'source': f'RocketReach API — person lookup ({name})',
                'access_method': 'rocketreach_api', 'layer': 5,
                'yielded_signal': False,
            })
        except RocketReachError as e:
            # Typically: 403 (sandbox allowlist), 500, network. Warn once.
            print(f"[eliss] RR person lookup failed for {name}: {type(e).__name__}",
                  file=sys.stderr)
            # Log the failed attempt for transparency (Research Coverage panel)
            checked.append({
                'source': f'RocketReach API — person lookup ({name}) [failed]',
                'access_method': 'rocketreach_api', 'layer': 5,
                'yielded_signal': False,
            })
            # If the error is a 403 host-not-allowlisted, further calls will
            # also fail — break out to save time.
            if '403' in str(e) or 'allowlist' in str(e).lower():
                print("[eliss] RocketReach host not in network allowlist — "
                      "this likely means you're running inside Claude.ai's "
                      "sandbox rather than Claude Code. See SKILL.md for the "
                      "Claude Code install path to enable RocketReach.",
                      file=sys.stderr)
                break

    # Log the final budget usage so reps can see credit consumption
    summary = client.budget_summary()
    if summary.get('total_credits_consumed', 0) > 0:
        print(f"[eliss] RocketReach credits consumed this run: "
              f"{summary['total_credits_consumed']} "
              f"(person:{summary['person_lookups_used']}, "
              f"company:{summary['company_lookups_used']})",
              file=sys.stderr)

    return data


def _reconfigure_stdio_utf8():
    """On Windows consoles (cp1252 default), Unicode bullets in depth-lint
    stderr output render as '?' / mojibake. Force UTF-8 on stdout+stderr so
    the depth-lint bullets + arrows come through cleanly across platforms.
    """
    for stream_name in ('stdout', 'stderr'):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, 'reconfigure', None)
        if reconfigure is not None:
            try:
                reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass  # stream type doesn't support reconfigure — accept defaults


# Top-level keys every dossier JSON must contain (SKILL.md 'CRITICAL' callouts
# + references/dossier-template.md). Used by --validate-only.
_REQUIRED_TOP_KEYS = frozenset({
    'meta', 'lead', 'company', 'technology', 'scoring', 'budget_analysis',
    'compliance', 'org_intelligence', 'signals', 'recommendations',
    'executive_brief', 'pre_mortem', 'rep_readiness_checklist',
    'full_dossier_markdown', 'sources', 'data_quality',
})
_REQUIRED_BUDGET_KEYS = frozenset({
    'estimated_deal_size', 'deal_size_basis', 'iam_iga_budget', 'siem_budget',
})


def validate_dossier(data):
    """Return a list of schema violations. Empty list == valid.

    v7.1.5+ adds shape validation for the structured fields that the renderer
    later dereferences with .get() / .items(). Without these guards a malformed
    JSON (e.g. ``pre_mortem: "TBD"`` instead of a list of dicts) passes
    ``--validate-only`` cleanly and then crashes the HTML renderer with an
    AttributeError. Each shape mismatch becomes one error line so the operator
    can fix all of them in one round-trip rather than peeling the onion.
    """
    errors = []
    missing_top = _REQUIRED_TOP_KEYS - set(data.keys())
    if missing_top:
        errors.append(f'Missing required top-level keys: {sorted(missing_top)}')

    ba = data.get('budget_analysis', {})
    missing_budget = _REQUIRED_BUDGET_KEYS - set(ba.keys())
    if missing_budget:
        errors.append(
            f'budget_analysis missing required fields: {sorted(missing_budget)}. '
            f'(The generator defaults estimated_deal_size to $40K when absent, '
            f'producing misleading waterfall visuals — see SKILL.md CRITICAL v5.2+.)'
        )

    md = data.get('full_dossier_markdown', '')
    if not isinstance(md, str) or len(md) < 500:
        errors.append(
            'full_dossier_markdown is empty or <500 chars — Tab 2 of the report '
            'will render an empty-state placeholder. See SKILL.md CRITICAL v5.1+.'
        )

    scoring = data.get('scoring', {})
    score = scoring.get('final_score', scoring.get('composite')) if isinstance(scoring, dict) else None
    tier = scoring.get('tier') if isinstance(scoring, dict) else None
    # v7.1.5 — Tier comparison normalizes case + whitespace so 'hot', ' Hot ',
    # 'HOT' all collapse to the same canonical token before checking against
    # the score-derived expected value.
    tier_norm = tier.strip().upper() if isinstance(tier, str) else tier
    if isinstance(score, (int, float)) and tier_norm:
        expected = 'HOT' if score >= 75 else 'WARM' if score >= 50 else 'COOL' if score >= 30 else 'COLD'
        if tier_norm != expected:
            errors.append(f'tier "{tier}" does not match composite score {score} (expected {expected})')
    elif tier is not None and not isinstance(score, (int, float)) and score is not None:
        # v7.1.5 — Surface the type error rather than silently skipping the
        # consistency check. Stringified scores ("90") are a common mistake
        # when the dossier JSON is hand-edited; the renderer downstream then
        # treats the score as missing and the tier-vs-score guarantee is lost.
        errors.append(
            f'scoring.final_score (or .composite) is type {type(score).__name__} '
            f'(expected int/float); tier consistency cannot be checked'
        )

    # v7.1.5 — SHAPE VALIDATION
    # Each entry below documents (json_path, expected_python_type,
    # element_type_if_list). Mismatches cause AttributeError downstream when
    # the renderer calls .get() / .items() / iterates expecting a specific
    # type. The checks tolerate field-absence (those are caught by the
    # missing-top-keys check above); they only fire when the field is present
    # but the wrong type.
    def _shape_check(path, expected_type, element_type=None):
        """Walk dot-separated path; if leaf exists, assert isinstance(expected_type)."""
        keys = path.split('.')
        node = data
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return  # absent — covered elsewhere
            node = node[k]
        if not isinstance(node, expected_type):
            errors.append(
                f'{path} must be {expected_type.__name__}, got {type(node).__name__}'
            )
            return
        if element_type and isinstance(node, list):
            for i, el in enumerate(node):
                if not isinstance(el, element_type):
                    errors.append(
                        f'{path}[{i}] must be {element_type.__name__}, '
                        f'got {type(el).__name__}'
                    )
                    break  # one example is enough — don't spam errors

    # Top-level lists of dicts
    _shape_check('pre_mortem', list, dict)
    _shape_check('compliance', list, dict)
    _shape_check('rep_readiness_checklist', list, str)

    # Top-level dicts
    _shape_check('recommendations', dict)
    _shape_check('org_intelligence', dict)
    _shape_check('sources', dict)
    _shape_check('data_quality', dict)

    # Nested signals lists
    _shape_check('signals', dict)
    _shape_check('signals.positive', list, dict)
    _shape_check('signals.negative', list, dict)

    # Nested DMU dicts (renderer dereferences each with .get('name')/.get('title'))
    for slot in ('economic_buyer', 'champion', 'technical_evaluator', 'blocker'):
        _shape_check(f'org_intelligence.{slot}', dict)
    _shape_check('org_intelligence.future_stakeholders', list, dict)
    _shape_check('org_intelligence.additional_stakeholders', list, dict)

    # Scoring sub-dicts (renderer reads .breakdown / .signals / .score / .max)
    _shape_check('scoring', dict)
    for dim in ('fit', 'intent', 'timing', 'budget'):
        _shape_check(f'scoring.{dim}', dict)
    _shape_check('scoring.deal_execution_risks', list, dict)
    _shape_check('scoring.scenarios', list, dict)

    # Technology sub-fields the RR Firmographic Enrichment renderer uses
    _shape_check('technology', dict)
    _shape_check('technology.competitive_threat_matrix', list, dict)
    _shape_check('technology.renewal_intelligence', list, dict)
    _shape_check('technology.web_fingerprint', dict)

    # v7.2 — Recommended Outreach (optional, but if present must be a list of dicts)
    _shape_check('recommended_outreach', list, dict)

    # v7.4 — Demo Playbook (optional; if present, top-level is dict with ad360/log360 sub-dicts)
    _shape_check('demo_playbook', dict)
    _shape_check('demo_playbook.ad360', dict)
    _shape_check('demo_playbook.log360', dict)
    _shape_check('demo_playbook.ad360.value_moments', list, dict)
    _shape_check('demo_playbook.log360.value_moments', list, dict)
    _shape_check('demo_playbook.ad360.discovery_questions', list, str)
    _shape_check('demo_playbook.log360.discovery_questions', list, str)
    _shape_check('demo_playbook.ad360.top_objections', list, dict)
    _shape_check('demo_playbook.log360.top_objections', list, dict)

    return errors


def main():
    _reconfigure_stdio_utf8()
    parser = argparse.ArgumentParser(description=f'ELISS Report Generator v{ELISS_VERSION}')
    parser.add_argument('input_file', help='JSON dossier file (or .md fallback)')
    parser.add_argument('--output-dir', '-o', default='.', help='Output directory')
    parser.add_argument('--format', '-f', choices=['html', 'pdf', 'both'], default='both')
    parser.add_argument('--log', '-l', default=None, help='Path to leads_log.json for peer benchmarking')
    parser.add_argument(
        '--validate-only', action='store_true',
        help='Schema-check the JSON and exit; do not render HTML/PDF. Exit 0 on pass, non-zero on fail (v6.2.5+)'
    )
    parser.add_argument(
        '--no-enrich', action='store_true',
        help='Skip RocketReach enrichment even if RR_API_KEY is set (v6.1+)'
    )
    parser.add_argument(
        '--save-enriched', action='store_true',
        help='Also write the post-enrichment JSON to <base>.enriched.json alongside '
             'the HTML/PDF output so downstream consumers can read the new fields (v6.1+)'
    )
    parser.add_argument(
        '--cleanup-input-json', action='store_true',
        help='After successful HTML/PDF generation, delete the input JSON file. '
             'Use this when the JSON lives in a temp dir and is not a deliverable. '
             'Guarantees zero JSON leakage into the user workspace (v7.1.5+).'
    )
    args = parser.parse_args()

    input_path = Path(args.input_file)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    # v7.1.5 — utf-8-sig (not utf-8) so a UTF-8 BOM at the file head doesn't
    # crash json.loads(). PowerShell's `Out-File -Encoding utf8` writes BOM by
    # default, which was a recurring footgun for operators piping dossier JSON
    # through Windows shells.
    content = input_path.read_text(encoding='utf-8-sig')

    if input_path.suffix == '.json':
        data = json.loads(content)
    else:
        data = fallback_from_markdown(content)

    if args.validate_only:
        errors = validate_dossier(data)
        if errors:
            print(f'[validate] {input_path.name}: {len(errors)} issue(s)', file=sys.stderr)
            for e in errors:
                print(f'  - {e}', file=sys.stderr)
            sys.exit(2)
        print(f'[validate] {input_path.name}: OK')
        sys.exit(0)

    output_dir.mkdir(parents=True, exist_ok=True)

    # v6.1: Optional RocketReach DMU enrichment. Silent no-op when RR_API_KEY
    # unset or when --no-enrich is passed. Any failure degrades gracefully.
    if not args.no_enrich:
        data = _try_enrich_with_rocketreach(data)

    # Load peer scores if log provided
    peer_scores = load_peer_scores(args.log) if args.log else []
    # Exclude self from peer set (match by email or name)
    if peer_scores and args.log:
        try:
            log_data = json.loads(Path(args.log).read_text(encoding='utf-8'))
            leads = log_data if isinstance(log_data, list) else log_data.get('leads', [])
            self_email = data.get('lead', {}).get('email', '').lower()
            self_name = data.get('lead', {}).get('name', '').lower()
            peer_scores = [
                int(l.get('score', 0)) for l in leads
                if isinstance(l.get('score'), (int, float))
                and l.get('email', '').lower() != self_email
                and l.get('name', '').lower() != self_name
            ]
        except (json.JSONDecodeError, OSError):
            pass

    company_slug = re.sub(r'[^a-zA-Z0-9]', '_', data.get('company', {}).get('name', 'Unknown'))
    name_parts = data.get('lead', {}).get('name', 'Unknown').split()
    last_name = name_parts[-1] if name_parts else 'Unknown'
    date_str = data.get('meta', {}).get('generated', datetime.now().strftime('%Y-%m-%d'))
    base = f"ELISS_{company_slug}_{last_name}_{date_str}"

    html_content = generate_html_report(data, peer_scores=peer_scores)
    results = []

    if args.format in ('html', 'both'):
        p = output_dir / f"{base}.html"
        p.write_text(html_content, encoding='utf-8')
        print(f"  HTML: {p}")
        results.append(str(p))

    if args.format in ('pdf', 'both'):
        pdf_path = output_dir / f"{base}.pdf"
        if generate_pdf_from_html(html_content, pdf_path):
            print(f"  PDF: {pdf_path}")
            results.append(str(pdf_path))
        else:
            fallback = output_dir / f"{base}_print.html"
            fallback.write_text(html_content, encoding='utf-8')
            print(f"  PDF library not available. Printable HTML saved: {fallback}")
            print(f"  Open in browser → Ctrl+P → Save as PDF")
            results.append(str(fallback))

    # v6.1: If --save-enriched and the generator mutated `data` (RocketReach
    # added fields, sources_actually_checked entries, etc.), persist the
    # post-enrichment JSON so downstream consumers can read the new fields.
    if args.save_enriched:
        enriched_path = output_dir / f"{base}.enriched.json"
        enriched_path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                                 encoding='utf-8')
        print(f"  Enriched JSON: {enriched_path}")
        results.append(str(enriched_path))

    # v7.1.5 — Optional cleanup of the source JSON (used by /eliss when the
    # JSON was written to a temp dir and is not a user deliverable). Only
    # cleans up after at least one HTML/PDF artifact was successfully written.
    if args.cleanup_input_json and results and input_path.suffix == '.json':
        try:
            input_path.unlink()
            print(f"  Cleaned up input JSON: {input_path}")
        except OSError as e:
            # Non-fatal — the report has already been written.
            print(f"  Warning: could not delete {input_path}: {e}", file=sys.stderr)

    print(json.dumps({"files": results}))

    # ---------------------------------------------------------------------
    # v6.1.1 — RESEARCH-DEPTH QUALITY LINT
    # Surfaces thin research that validates under the schema but produces
    # weaker dossiers than the lead's tier deserves. Three rendered
    # symptoms — under-counted Source Quality Donut, sparse Buying Signals
    # Timeline, missing DMU members — all share this root cause. Warnings
    # go to stderr so they don't break --json downstream consumers.
    # ---------------------------------------------------------------------
    try:
        _emit_research_depth_warnings(data)
    except Exception as e:  # pragma: no cover — lint must never break a run
        print(f"[depth-lint] internal error: {e}", file=sys.stderr)
    try:
        _emit_narrative_density_warnings(data)
    except Exception as e:  # pragma: no cover — lint must never break a run
        print(f"[depth-lint] narrative-density internal error: {e}", file=sys.stderr)


# Narrative-density floors — eliss-light edition (halved vs /eliss because the
# light edition runs single-RR-pass + 6 targeted searches, not the 4-subagent
# fan-out, so honest output is ~half the citation density).
_NARRATIVE_FLOORS = {
    'HOT':  {'md-link': 10, 'md-tier': 20, 'md-pill': 3, 'md-callout': 3, 'md-blockquote': 1},
    'WARM': {'md-link':  5, 'md-tier': 10, 'md-pill': 1, 'md-callout': 1, 'md-blockquote': 0},
    'COOL': {'md-link':  2, 'md-tier':  5, 'md-pill': 0, 'md-callout': 0, 'md-blockquote': 0},
    'COLD': {'md-link':  0, 'md-tier':  0, 'md-pill': 0, 'md-callout': 0, 'md-blockquote': 0},
}

_CALLOUT_KEYWORD_SET = frozenset({
    'why', 'mitigation', 'resolution', 'action', 'next', 'trigger',
    'earliest', 'watch', 'risk', 'note', 'key', 'insight',
})


def _count_narrative_density(md):
    if not md or not isinstance(md, str):
        return {'md-link': 0, 'md-tier': 0, 'md-pill': 0, 'md-callout': 0, 'md-blockquote': 0}
    md_link = len(re.findall(r'https?://[^\s)\]\[<>"\'`]+', md))
    md_tier = len(re.findall(r'\s\[[ABC]\]', md))
    md_pill = len(re.findall(r'\[(CONFIRMED|ESTIMATED|INFERRED)\]', md))
    md_callout = 0
    for m in re.finditer(r'(?m)^\*\*([^:\*]{1,80}):\*\*', md):
        label_lc = m.group(1).strip().lower()
        first_word_m = re.match(r'^([a-z]+)', label_lc)
        if first_word_m and first_word_m.group(1) in _CALLOUT_KEYWORD_SET:
            md_callout += 1
    md_blockquote = len(re.findall(r'(?m)^>\s', md))
    return {'md-link': md_link, 'md-tier': md_tier, 'md-pill': md_pill,
            'md-callout': md_callout, 'md-blockquote': md_blockquote}


def _emit_narrative_density_warnings(data):
    """Soft-warn when full_dossier_markdown narrative density falls below the
    tier-keyed floor (halved vs /eliss for the light edition)."""
    scoring = data.get('scoring', {}) or {}
    tier = (scoring.get('tier') or '').upper().strip()
    floor = _NARRATIVE_FLOORS.get(tier)
    if not floor:
        return
    md = data.get('full_dossier_markdown') or ''
    if not md.strip():
        return
    counts = _count_narrative_density(md)
    breaches = [(n, counts[n], floor[n]) for n in
                ('md-link', 'md-tier', 'md-pill', 'md-callout', 'md-blockquote')
                if counts[n] < floor[n]]
    if not breaches:
        return
    print("", file=sys.stderr)
    print(f"[depth-lint] {tier} lead has thin Tab 2 narrative density (light-edition floor):",
          file=sys.stderr)
    hints = {
        'md-link': "add inline `https://...` URL citations after each claim",
        'md-tier': "append `[A]` / `[B]` / `[C]` source-tier markers",
        'md-pill': "label data figures with `[CONFIRMED]` / `[ESTIMATED]` / `[INFERRED]`",
        'md-callout': "use `**Why:** …` / `**Mitigation:** …` paragraph openers",
        'md-blockquote': "open key sections with `> thesis` blockquotes",
    }
    for name, got, want in breaches:
        print(f"  • {name}={got} < {tier} floor of {want} ({hints[name]})", file=sys.stderr)


def _emit_research_depth_warnings(data):
    """Print warnings if the dossier's research depth falls below the
    minimum expected for its scoring tier.

    Tier floors (see SKILL.md → "Research Depth Minimums"):
        HOT  — ≥20 sources, ≥10 signals, ≥3 named DMU roles
        WARM — ≥12 sources,  ≥6 signals, ≥2 named DMU roles
        COOL —  ≥8 sources,  ≥4 signals, ≥1 named DMU role
        COLD —  ≥4 sources,  ≥2 signals
    """
    scoring = data.get('scoring', {}) or {}
    tier = (scoring.get('tier') or '').upper().strip()
    floors = {
        'HOT':  {'sources': 20, 'signals': 10, 'named_dmu': 3},
        'WARM': {'sources': 12, 'signals':  6, 'named_dmu': 2},
        'COOL': {'sources':  8, 'signals':  4, 'named_dmu': 1},
        'COLD': {'sources':  4, 'signals':  2, 'named_dmu': 0},
    }
    floor = floors.get(tier)
    if not floor:
        return  # Unknown tier → skip lint silently

    # Count sources (flat sources object — what the donut counts)
    sources = data.get('sources', {}) or {}
    src_count = 0
    for _, urls in sources.items():
        if isinstance(urls, list):
            src_count += len(urls)

    # Count signals (positive + negative)
    signals = data.get('signals', {}) or {}
    sig_count = (
        len(signals.get('positive') or []) +
        len(signals.get('negative') or [])
    )

    # Count NAMED DMU roles (exclude vacant / unidentified placeholders)
    org = data.get('org_intelligence', {}) or {}
    placeholder_words = ('vacant', 'unknown', 'unidentified', 'tbd', 'open req', 'n/a')
    def is_named(role_obj):
        if not isinstance(role_obj, dict):
            return False
        n = (role_obj.get('name') or '').strip().lower()
        if not n:
            return False
        return not any(w in n for w in placeholder_words)
    named_dmu = sum(1 for r in (
        org.get('economic_buyer'),
        org.get('champion'),
        org.get('technical_evaluator'),
        org.get('blocker'),
    ) if is_named(r))
    # v6.2.1 — count named entries in additional_stakeholders[] toward the floor
    named_dmu += sum(1 for r in (org.get('additional_stakeholders') or []) if is_named(r))

    warnings = []
    if src_count < floor['sources']:
        warnings.append(
            f"sources flat-count={src_count} < {tier} floor of {floor['sources']} "
            f"(this is what the Source Quality Donut counts; "
            f"add every hit URL to sources.{{person,company,technology,financial,compliance}}, "
            f"not just the headline ones)"
        )
    if sig_count < floor['signals']:
        warnings.append(
            f"signals.positive+negative={sig_count} < {tier} floor of {floor['signals']} "
            f"(thin Buying Signals Timeline; revisit Layer 4b procurement-cycle queries "
            f"and Layer 7 personal/conference signals before finalizing)"
        )
    if named_dmu < floor['named_dmu']:
        warnings.append(
            f"named DMU roles={named_dmu} < {tier} floor of {floor['named_dmu']} "
            f"(vacant/unidentified placeholders DON'T count — they belong in "
            f"org_intelligence.future_stakeholders[]; the primary DMU slots "
            f"need real named people: research the contact's manager, the CISO, "
            f"the procurement lead)"
        )

    # v7.1.6 — CONTACT-VERIFY LINT
    # When the inbound lead has an email but no LinkedIn URL AND no
    # LinkedIn-direct search appears in sources_actually_checked[], the
    # analyst likely defaulted the contact to Influencer/Unknown without
    # actually trying to find them. This regressed contact-role accuracy
    # in the Remington Hospitality / Dylan Horner dossier (v7.1.5),
    # which shipped with the contact in an "unknown" slot because the
    # canonical `site:linkedin.com/in/` query was never executed. Fires
    # for ALL tiers — the cost of a missed contact verification is
    # tier-independent.
    lead = data.get('lead', {}) or {}
    has_email = bool(lead.get('email'))
    has_linkedin = bool(lead.get('linkedin') or lead.get('linkedin_url'))
    if has_email and not has_linkedin:
        sources_checked = (data.get('data_quality') or {}).get('sources_actually_checked') or []
        linkedin_direct_logged = any(
            re.search(r'linkedin\.com/in/|linkedin\s+profile|linkedin\s+direct',
                      str(entry.get('source') or ''),
                      re.IGNORECASE)
            and entry.get('yielded_signal')
            for entry in sources_checked
            if isinstance(entry, dict)
        )
        if not linkedin_direct_logged:
            contact_name = lead.get('name', '<contact>')
            warnings.append(
                f"lead.linkedin is unset and no LinkedIn-direct search appears "
                f"in sources_actually_checked[] (recommended canonical query: "
                f"`site:linkedin.com/in/ \"{contact_name}\" \"<company>\"`). "
                f"The contact's role drives Fit/title scoring — verify before "
                f"finalizing. (See SKILL.md Mandatory Free-OSINT Checklist "
                f"item #9 — three-query block.)"
            )

    if warnings:
        print("", file=sys.stderr)
        print(f"[depth-lint] {tier} lead has thin research:", file=sys.stderr)
        for w in warnings:
            print(f"  • {w}", file=sys.stderr)
        print(f"[depth-lint] (See SKILL.md 'Research Depth Minimums' — "
              f"a HOT score on thin research erodes rep trust.)", file=sys.stderr)

    # v6.2: Nudge analysts toward the optional Wave-1 infographic fields.
    # Informational only — these fields are NOT required, the report just
    # surfaces a richer visual playbook when they're populated.
    missing_optional = []
    if not (scoring.get('scenarios') or []):
        missing_optional.append(
            "scoring.scenarios[] — unlocks 'What-If Scenarios' cards "
            "(2-4 score modulators tied to first-call signals)"
        )
    technology = data.get('technology', {}) or {}
    if not (technology.get('web_fingerprint') or {}):
        missing_optional.append(
            "technology.web_fingerprint{} — unlocks 'Web Property Tech "
            "Fingerprint' badge grid (frontend/analytics/chat/cdn/cms/"
            "email_marketing categories from web_fetch + DNS analysis)"
        )
    recs = data.get('recommendations', {}) or {}
    if not (recs.get('decision_tree') or {}):
        missing_optional.append(
            "recommendations.decision_tree{} — unlocks 'First-Call "
            "Decision Tree' flowchart (4-5 branches of what-rep-does-IF-"
            "prospect-says-X)"
        )
    if not (data.get('recommended_outreach') or []):
        missing_optional.append(
            "recommended_outreach[] — unlocks 'Recommended Outreach' "
            "follow-up email cards (3 dossier-driven emails in "
            "Technical/Consultative/Executive enterprise voices). See "
            "references/outreach-playbook.md for the template library "
            "and selection rules. (v7.2+)"
        )
    if not (data.get('demo_playbook') or {}):
        missing_optional.append(
            "demo_playbook{} — unlocks 'Demo Playbook' card with "
            "persona-anchored AD360 + Log360 scripts (opening hook, "
            "3 value moments per product, discovery questions, top "
            "objections, CTA). See references/dossier-schema.md "
            "demo_playbook section. (v7.4+)"
        )
    if missing_optional and tier in ('HOT', 'WARM'):
        # Only nudge for tiers worth the extra effort; COOL/COLD leads
        # don't justify the analyst time to populate these.
        print("", file=sys.stderr)
        print(f"[depth-lint] {tier} lead missing optional v6.2 infographics:",
              file=sys.stderr)
        for m in missing_optional:
            print(f"  • {m}", file=sys.stderr)
        print(f"[depth-lint] (See SKILL.md 'Wave 1 Infographics' — "
              f"high-value visual additions for HOT/WARM leads.)",
              file=sys.stderr)


if __name__ == '__main__':
    main()
