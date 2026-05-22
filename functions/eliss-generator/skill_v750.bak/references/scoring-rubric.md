# ELISS Light Scoring Rubric

Read this once at Step 3 before assigning per-dimension points. Composite = Fit(25) + Intent(25) + Timing(30) + Budget(20). Tiers: HOT ≥75, WARM 50–74, COOL 30–49, COLD <30.

## Dimension 1 — FIT (max 25)

Sum of: Company Size (8) + Industry Vertical (7) + Title/Seniority (6) + Tech Alignment (4).

| Component | Levels |
|---|---|
| **Size (8)** | 1K–5K emp = 8 (sweet spot); 200–999 or 5K–10K = 6; <200 or >10K = 3 |
| **Vertical (7)** | Gov / Healthcare / FinServ = 7; Education / Energy / Critical Infra = 5; Other regulated = 3; Unregulated = 1 |
| **Title (6)** | CISO / CIO = 6; IT Director / VP = 5; Sec/IAM Manager = 4; IC Engineer = 2 |
| **Tech (4)** | Confirmed AD = 4; AD inferred (MS-tenant) = 3; Hybrid = 2; Cloud-only / non-AD = 1 |

## Dimension 2 — INTENT (max 25)

Accumulate points; cap at 25.

| Signal | Points |
|---|---|
| Direct inquiry (form fill, demo request) | +15 |
| Active evaluation (RFP, POC underway) | +12 |
| Compliance need (mandatory framework gap) | +10 |
| Security incident in past 12mo | +10 |
| Confirmed AD pain (audit finding, breach attribution) | +8 |
| Security hiring surge (≥3 reqs in 90d) | +6 |
| Tech investment (cloud migration, identity refresh) | +5 |
| Content engagement | +3 |

**Triangulation rule:** if >15 pts come from a single category, multiply intent total × 0.80.

## Dimension 3 — TIMING (max 30)

| Trigger | Points |
|---|---|
| Active RFP / procurement open | 30 |
| Imminent need (<6mo renewal window OR post-breach <90d) | 24 |
| Strong (new CISO <90d, audit deadline, 6–12mo renewal) | 18 |
| Moderate (12–24mo renewal, hiring surge) | 12 |
| Weak signal | 6 |
| No data | 3 |

**Negative timing modifier:** incumbent renewed <12mo for 2+ consecutive years → flag `recently_renewed_lockout`, cap timing at 6.

### Tenure-milestone TIMING bonus (v7.5)

The decision-window curve for new IT/security leaders is empirically peaked between months 12–18: that's when first-major-tooling-decisions ship. Auto-detect from RR `named_contact.job_history[0].start_date` (or any verified champion's start date) and apply the **highest matching tier** below — does not stack with other Timing rows; pick whichever scores more.

| Tenure (champion role) | Points | Why |
|---|---:|---|
| <90d (just-arrived) | 18 | Honeymoon-budget window; same as "new CISO <90d" already in main table |
| 90d–6mo | 14 | Diagnosing-the-stack phase; receptive but not yet deciding |
| **6mo–12mo** | 12 | Eval-active phase — RFI cadence begins |
| **12mo–18mo** | **15** | **Decision window peak — first major tooling decision ships here** |
| 18mo–24mo | 10 | Window closing; vendor short-list usually locked |
| 24mo+ | 0 | Settled; no bonus (other timing signals still apply) |

**Discipline:** the tenure bonus replaces, not adds to, a generic "Strong" or "Moderate" Timing row when both would otherwise apply. Cite the RR start_date in the scoring rationale so the +15 doesn't read as hand-wavy.

## Dimension 4 — BUDGET (max 20)

Sum of: Authority (8) + Capacity (7) + Procurement Speed (5).

| Component | Levels |
|---|---|
| **Authority (8)** | CISO / CIO = 8; IT Director / VP = 6; Manager = 4; IC = 1 |
| **Capacity (7)** | RR-confirmed revenue or strong public filing = 7; headcount benchmark = 5; weak/no signal = 2 |
| **Procurement (5)** | Cooperative contract vehicle (GSA, NASPO) = 5; standard RFP = 3; unknown = 1 |

### Budget math (Light Edition)

1. **Revenue**: Use `RR revenue` if available. Else: `headcount × $200K` (gov/edu) or `headcount × $300K` (FinServ/Healthcare).
2. **IT spend** = 8% of revenue.
3. **Security budget** = 15% of IT spend.
4. **IAM sub-budget** = 12% of security; **SIEM sub-budget** = 15% of security.
5. **Deal sizing**: headcount × $1–2/user/month × 12. Bundle (AD360+Log360) = $2/user; single product = $1/user. Floor $20K, ceiling $800K.

## Composite & Modifiers

After summing the four dimensions:

**Structural negative modifiers** (each subtracts from composite):

| Modifier | Adjustment |
|---|---|
| Competitor purchased <6mo | −25 |
| Layoffs / RIF announced | −20 |
| Budget freeze | −20 |
| `recently_renewed_lockout` | −18 |
| Champion left <90d | −15 |
| Low local autonomy (centralized procurement) | −12 |
| M&A uncertainty | −10 |

**Deal Execution Risks** (do NOT stack with structural modifiers — list separately under `deal_execution_risks[]`, each −2 to −5, sum into `risk_adjusted_composite`).

## Recommended Action Mapping

| Tier | Action |
|---|---|
| HOT (≥75) | PURSUE NOW — outreach within 5 business days |
| WARM (50–74) | NURTURE — 30/60/90 cadence |
| COOL (30–49) | MONITOR — quarterly check-in |
| COLD (<30) | DEPRIORITIZE |
