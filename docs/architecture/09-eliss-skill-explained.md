# 09 — The `/eliss` Skill, Explained

This document is a bridge. It explains what the upstream `/eliss` Claude skill does at a conceptual level, and then maps each part of that skill to the Catalyst implementation in this project.

> **Reference document — not source-of-truth.** The actual skill lives at `C:\Users\dGiri\.claude\skills\eliss\` and is versioned independently. When the skill changes, this doc may lag. Always cross-check against `SKILL.md`, `CHANGELOG.md`, and the `references/` files in the skill directory.

## What `/eliss` is

`/eliss` is a Claude-Code skill that turns a single prospect identifier (name + email, LinkedIn URL, or company URL) into a scored intelligence dossier for ManageEngine AD360 and Log360 sellers. It does this through a structured 7-layer OSINT protocol plus a parallel-dispatch subagent pattern.

The output is a 2-tab HTML report:
- **Tab 1 — Executive Summary.** 5-second verdict: score gauge, 4-dimension radar, intent donut, compliance heatmap, signal timeline, budget waterfall, DMU org-chart, demo playbook, 3 recommended outreach emails.
- **Tab 2 — Complete Intelligence Dossier.** Full conversational narrative rendered from `full_dossier_markdown` — every claim with a tier badge (`[A]`/`[B]`/`[C]`), every URL auto-linked, callouts (`**Why:**`, `**Action:**`, `**Risk:**`) styled as colored boxes, every table as zebra-striped.

## The 7 layers

The skill organizes research into seven layers, each with a defined scope:

| Layer | Topic | Typical sources |
| --- | --- | --- |
| 1 | Identity & company foundation | LinkedIn, company website, Glassdoor |
| 2 | Technology & security posture | BuiltWith, GitHub, security hires, SIEM/IAM stack |
| 3 | Compliance & regulatory | HHS OCR, state AG, SEC, NYDFS, FedRAMP |
| 4 | Financial intelligence | 10-K, earnings calls, FY data, USAspending |
| 4b | Procurement-cycle intelligence | RFP/RFI, audit findings, grant awards, M&A |
| 5 | Organizational intelligence | DMU map, ghost stakeholders, local autonomy |
| 6 | Competitive & displacement | Incumbent detection, renewal windows, displacement angles |
| 7 | Behavioral & social | Conference talks, articles, GitHub activity, personalization hooks |

Layers aren't strictly sequential — they're a labeling convention. Each finding lands in the dossier under the layer that produced it, and each finding carries a tier badge (`A`/`B`/`C`) for source quality.

## The 4-subagent dispatch (heavy path)

When the skill is invoked in a context that supports the Claude `Agent` tool (Claude Code, Claude.ai, Cursor), and the prospect is suspected HOT or WARM after Layer 1, the skill dispatches **four parallel subagents** with one message:

- **A — Tech & Security Posture** (Layer 2): AD environment, security stack, cloud posture, competitive threat matrix. ~25 web_search budget.
- **B — Compliance + Financial + Procurement** (Layers 3, 4, 4b): regulatory frameworks, budget estimation, procurement signals. ~30 budget.
- **C — Org + Competitive Intelligence** (Layers 5, 6): DMU mapping, ghost stakeholders, displacement angles. ~25 budget.
- **D — Behavioral & Personalization** (Layer 7): conference talks, articles, hooks. ~15 budget.

The parent then consolidates: merges subagent fragments into the dossier, reconciles cross-layer observations (e.g., breach + new CISO + budget freeze → all interact), computes scores, and writes `full_dossier_markdown` as a single unified narrative.

**Total budget:** ~100-110 web_search calls per HOT dossier vs ~10-20 in single-session (light) mode.

## The 4-dimension scoring engine

Every dossier scores Fit, Intent, Timing, Budget independently. Composite is the sum.

| Dimension | Max | What it measures |
| --- | --- | --- |
| **Fit** | 25 | Company Size (8) + Industry Vertical (7) + Title/Seniority (6) + Tech Alignment (4) |
| **Intent** | 25 | Signal accumulation: direct inquiry, active evaluation, compliance need, security incident, AD pain, security hiring, tech investment, content engagement. Triangulation rule: >15 points from a single category → ×0.80 |
| **Timing** | 30 | Active procurement (30) > Imminent need (24) > Strong trigger (18) > Moderate (12) > Weak (6) > No data (3). Renewal windows override: <6 months → 24-30; recently renewed <12 months → 6 + lockout modifier |
| **Budget** | 20 | Budget Authority (8) + Budget Capacity (7) + Procurement Speed (5) |

**Tier thresholds:**
- HOT: 75-100
- WARM: 50-74
- COOL: 30-49
- COLD: 0-29

**Validation caps:** Stale data >90 days caps at 74. LOW confidence caps at 74. Decay multiplier × 0.95^weeks_since_signal.

**Structural negative modifiers (disqualifiers):**
- Competitor purchased (-25), Layoffs (-20), Budget freeze (-20), Recently renewed (-18), Champion left (-15), Bad ME experience (-15), Low local autonomy (-12), M&A uncertainty (-10), Regulatory block (-10).

**Deal execution risks (softer friction, -2 to -5 each):**
- Champion new to role (-3), Small deal (-2), Shrinking budget (-3), Likely unconfirmed incumbent (-5), Procurement friction (-3), Multi-dept sign-off (-3).

The rendered Tab 1 shows both `final_score` (raw) and `risk_adjusted_composite` (raw minus sum of risks). **Tier is determined by raw score**, not risk-adjusted.

## What the Catalyst port re-implements

The `/eliss` skill is designed to run in Claude Code with the `Agent` tool. The Catalyst port doesn't have that — Catalyst is a serverless platform, not an LLM agent runtime. So each piece of the skill maps to a server-side equivalent.

### Preflight script

- **Skill:** `scripts/preflight.py` invoked from the user's terminal via `python scripts/preflight.py <domain>`. Standalone Python; reads `--lead-email`, `--industry`, etc. from argv.
- **Catalyst port:** Identical `preflight.py` vendored at `functions/eliss-generator/skill/scripts/preflight.py`. Called from the generator's `_run_pipeline()` at the `preflight` stage via `preflight.run_preflight(...)` — imported as a module, not subprocessed.

The preflight script itself is unchanged; only the invocation path differs.

### RocketReach client

- **Skill:** `scripts/rocketreach_client.py` is the Python library; subagents call its methods.
- **Catalyst port:** Same file, vendored alongside preflight. The generator's `_run_pipeline()` instantiates `RocketReachClient()` and calls `run_baseline_enrichment(...)` directly.

### Parallel subagent dispatch

- **Skill:** Uses Claude's `Agent` tool. Parent agent emits four `Agent` tool calls in one message; each gets its own context window and `web_search` budget; parent reads each Task's final message back and consolidates.
- **Catalyst port:** The same logical fan-out, but implemented in Python with `asyncio.gather` over four `anthropic.AsyncAnthropic` API calls. Each call carries one specialist system prompt (Tech / Compliance / Org / Behavioral) and the same `web_search` tool. The parent consolidation is a fifth no-tools Anthropic call. Code lives in `functions/eliss-heavy-generator/lib/fanout.py`.

The behavioral target is identical: four specialists work in parallel, each spending ~25-30 web_search calls; the parent merges their fragments. The only difference is the substrate (`Agent` tool vs `asyncio.gather + Anthropic.AsyncMessages`).

### Report generator

- **Skill:** `scripts/generate_report.py` produces HTML, PDF (via WeasyPrint), or both. The skill always invokes with `--format html` by default and runs depth-lint on the rendered output (per memory rule `feedback_eliss_html_only_auto_export`).
- **Catalyst port:** Same script, vendored. Invoked as a subprocess (not imported) because the script's `main()` ends in `sys.exit()` and reads `sys.argv` — awkward to monkey-patch from a long-running Job. The generator always runs `--format html --cleanup-input-json`.

The depth-lint warnings emit on the subprocess `stderr` and are parsed by `lib/depth_lint.py` to decide whether to trigger a synthesis retry (light) or mark the dossier `partial` (heavy).

### Scoring engine & JSON schema

- **Skill:** The scoring rules are *prompt-encoded* in `SKILL.md` STEP 3. Claude does the scoring during synthesis; the rules don't live in code, they live in instructions.
- **Catalyst port:** Identical. The synthesis prompt at `lib/skill_prompt.py` carries the same scoring instructions and produces the same JSON shape. There's no Python code in the port that scores leads — Claude does it via instruction-following.

The JSON schema contract (see `references/dossier-template.md` in the skill) is preserved verbatim. Tab 1 card contracts including the `_extract_value()` dict-unwrap pattern apply unchanged. The `compliance` row reads both `ad360_fit` and `ad360_angle` (legacy alias). Per memory rule `project_eliss_tab1_dict_unwrap`.

### Render-time verification gates

- **Skill:** After every render, the depth-lint output is parsed for `[depth-lint]` warnings. HOT-tier dossiers with any blocking warning are regenerated. CSS-class audit and empty-state literal scan are run on the HTML. Per memory rule `feedback_eliss_render_verification_gate`.
- **Catalyst port:** `lib/depth_lint.py` runs the same checks server-side, after `generate_report.py` returns. Light retries synthesis once on blocking hits; Heavy marks the dossier `partial` instead (no retry — token budget already invested). Either way, the rep sees the dossier; the only difference is how confidently the system surfaces it.

## What the Catalyst port simplifies or defers

Not everything in the skill ports cleanly. The following are simplified or deferred:

| Skill feature | Catalyst port |
| --- | --- |
| `--industry` flag for OTX sector pulse search | Currently not exposed via the intake form; could be derived from RR firmographics in a future release. |
| Multi-format export (HTML + PDF) | HTML-only. PDF requires WeasyPrint + headless Chrome, which adds memory pressure to the Job Function. The Stratus-stored HTML can be PDF'd client-side if needed. |
| Local `leads_log.json` persistent registry | Replaced by the `leads` table — Catalyst is the registry. |
| Workspace cleanup (`--cleanup-input-json`) | Catalyst's tmpfs is per-execution, so cleanup is automatic. The flag is still passed for hygiene. |
| Skill-side LinkedIn-direct query item #29 | The OSINT preflight covers the same ground (probe_xposedornot uses the email; web_search inside synthesis finds the LinkedIn profile). The skill's stricter `--validate-only` check is not enforced at runtime; depth_lint handles the equivalent gate. |

## Where the upstream skill version stamp lives

Each generator carries a copy of:
- `skill/scripts/preflight.py` — has a `PREFLIGHT_VERSION = '7.4.2'` constant.
- `skill/scripts/rocketreach_client.py` — has `__version__ = "7.x.x"`.
- `skill/scripts/generate_report.py` — has an `ELISS_VERSION` constant.

These three should match the upstream skill's `VERSION` file. The Catalyst-port changelog tracks the skill version that's currently shipping in production — see [`changelog/ELISS-CHANGELOG.md`](../changelog/ELISS-CHANGELOG.md).

## When to update the port

Trigger to refresh the vendored skill scripts:

1. Upstream `/eliss` ships a new version (check `C:\Users\dGiri\.claude\skills\eliss\CHANGELOG.md`).
2. Read the changelog entry — does it apply to the Catalyst port? Most do; some (UI-only renderer changes) ship transparently via re-rendering.
3. Copy `scripts/{preflight,rocketreach_client,generate_report}.py` from the skill into BOTH `functions/eliss-generator/skill/scripts/` and `functions/eliss-heavy-generator/skill/scripts/`.
4. Bump the `eliss_version` constant in `lib/store_lead.py` (light + heavy) so `leads.eliss_version` reflects the new version.
5. Deploy with `--only functions:eliss-generator,functions:eliss-heavy-generator`.
6. Smoke-test by generating one dossier in dev. Inspect the Tab 1 footer for the version stamp.
7. Add a row to `ELISS-CHANGELOG.md` marking the version "ported."

## Cross-references

- The actual fan-out implementation → [05-eliss-heavy-generator.md](./05-eliss-heavy-generator.md)
- Tab 1 widget contracts (the dict-unwrap rule) → [02-frontend-vite-react.md](./02-frontend-vite-react.md) (LeadDetailPage section)
- Per-script env vars (RR, Anthropic, OTX) → [07-integrations.md](./07-integrations.md)
- The upstream skill version's running changelog → [`changelog/ELISS-CHANGELOG.md`](../changelog/ELISS-CHANGELOG.md)
