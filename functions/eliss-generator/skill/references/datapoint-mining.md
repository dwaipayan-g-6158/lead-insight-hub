# Datapoint Mining Checklist (v7.4) — squeeze the data you already paid for

Read this BEFORE constructing the dossier dict in Step 4. The Light edition's single-RR + 6-search budget is enough — but only if you mine the *underused* fields. New users typically cite ~30% of what RR + preflight already returned. This checklist closes that gap with **zero new research tokens.**

The rule: every field below comes from data you already have in the conversation context. If you find yourself reaching for a new web search to populate one of these signals, stop — re-read the RR JSON or preflight JSON instead.

---

## A. RocketReach `named_contact` (the lead)

| Field | What to extract | Where it lands in the dossier |
|---|---|---|
| `emails[]` non-primary aliases | Multi-region aliases (e.g. `marcolisboa@aig.co.jp`) signal regional/global mandate | `signals.positive[]` ("APAC scope hint"); `lead.personalization_hooks[]`; `pre_mortem[]` (mandate-scope-mismatch scenario) |
| `emails[]` personal address | Grade-A hotmail/gmail still active = practical comms style | `lead.personalization_hooks[]` |
| `phones[].last_checked` | Stale (>2 yrs) = channel-risk note | `signals.negative[]` (channel risk, impact -1); `rep_readiness_checklist[]` |
| Full `job_history[]` | Geographic mobility pattern (US→UK→US-remote) and industry ladder | `lead.personalization_hooks[]` (multi-region comfort, distributed-team fit) |
| Career step-shape | IC→VP, Director→VP, Manager→Director = "establish-credibility mode" hire | `signals.positive[]` (leadership_change, +4); `recommendations.outreach.hook` |

## B. RocketReach `company` (the org)

| Field | What to extract | Where it lands |
|---|---|---|
| `departments` headcount dict | Privileged-account-heavy depts (Eng + Ops + Finance + Legal) → AD360 deal-sizing population, NOT total headcount | `budget_analysis.calculation_basis`; `budget_analysis.deal_size_basis` |
| `departments.C-Suite` | Tight exec layer (single-digit) → realistic to reach CISO via warm intro | `org_intelligence.economic_buyer.note`; `org_intelligence.multi_thread_strategy` |
| `departments.Legal` headcount | Sizeable legal bench (>500) → multi-jurisdiction privacy stakeholder | `org_intelligence.additional_stakeholders[]` ("General Counsel / Chief Privacy Officer") |
| `naics_codes[]` | Multiple primary NAICS = dual-classification regulatory surface (e.g. 5242 + 524 = both broker AND carrier) | `company.sub_industry`; `compliance[]` (state-level frameworks) |
| `techstack[]` length | >500 distinct techs vs ~150-200 typical = sprawl signal | `signals.positive[]` (tech_investment, +3); `technology.digital_maturity` |
| `techstack[]` mainframe entries | `IBM Z Series Mainframe`, `IBM Mainframe`, `RACF` → unique AD360 differentiator (RACF↔AD bridge) | `technology.ad_environment`; `recommendations.ad360_talking_points[]`; `competitive_threat_matrix[]` |
| `techstack[]` customer-IAM | Adobe Experience Manager + Salesforce + ServiceNow → customer/agent-facing identity surface | `technology.security_stack[]`; `recommendations.ad360_talking_points[]` |
| `techstack[]` AppSec | AppDynamics + AppScan + observability → mature SDLC posture | `technology.digital_maturity` |
| `techstack[]` multi-cloud IAM | AWS IAM + Azure + Google Cloud IAM concurrently = federation complexity AD360 simplifies | `technology.cloud_posture`; `signals.positive[]` |
| `techstack[]` IGA/IDP overlap | 3+ IAM/IGA tools = consolidation pressure | `signals.positive[]` (tech_investment, +5); existing pre_mortem |

## C. Preflight (deterministic)

| Field | What to extract | Where it lands |
|---|---|---|
| `microsoft_tenant.namespace_type = null` + `reason = endpoint_404_no_tenant` | NOT a clean Microsoft 365 tenant — on-prem Exchange or third-party email gateway → identity migration runway | `signals.positive[]` (tech_investment, +3, "on-prem/legacy email infra"); `technology.cloud_posture` |
| `microsoft_tenant.federation_suggests_on_prem_ad = true` | On-prem AD strongly inferred even if AD techstack entry absent | `technology.ad_environment`; `scoring.fit.tech` |
| `github.has_org = false` | Closed-source posture = traditional FinServ/regulated culture | `lead.personalization_hooks[]` (vendor-proof-of-trust matters); `rep_readiness_checklist[]` |
| `usaspending.has_federal_contracts` = true | Federal contractor = additional compliance frameworks (NIST 800-171, CMMC) | `compliance[]`; `signals.positive[]` |
| `ransomware.confirmed_ransomware_victim = true` | Hard slot-1 trigger for Breach/Incident Response email template | `signals.positive[]` (incident, +10); `recommended_outreach[].slot=1` |
| `sec.is_public_company = true` + filing CIK | SOX + cybersecurity Item 1C disclosure obligation | `compliance[]` (SOX row) |

## D. Web search results — extract beyond the headline

| Source | Underused signal | Where it lands |
|---|---|---|
| Linkedin contact verify | Contact's CONNECTIONS count (RR returns it) — 500+ vs <100 changes outreach style | `lead.personalization_hooks[]` |
| 10-K/proxy fetch | CISO/CSO name from Item 1C ("oversight of cybersecurity"), even if not the buying contact | `org_intelligence.economic_buyer` |
| Layoff/restructuring press | Specific cut figures + named program ("AIG Next", "Boeing Synergy") + protected functions | `signals.negative[]` (budget_pressure); `pre_mortem[]` (vendor freeze scenario) |
| Vendor case-study sites | Peer orgs in same vertical/size band already on AD360/Log360 | `recommended_outreach[].slot=2` (Peer Benchmark template) |
| Cyber-insurance content from prospect itself | If they SELL cyber insurance / publish threat intel, internal cyber posture is reputational | `signals.positive[]` (content_engagement); `recommendations.outreach.hook` |

---

## Surfacing rules

When you find one of these signals, surface it in BOTH:
1. The structured field (per the schema in `dossier-schema.md`), AND
2. The `full_dossier_markdown` Tab 2 prose — otherwise the renderer's depth-lint shows the floor pass but the dossier reads thin.

**Density target:** for a HOT/WARM lead, aim for **≥4 datapoints per major section** mined from the categories above. If you can't reach four in a section, document the gap in `data_quality.gaps[]` rather than padding with generics.

**Compliance-map breadth rule:** if the prospect has multi-region presence (RR alias domains in `.co.jp`, `.de`, `.uk`, etc.), add the corresponding regional privacy framework row (APPI, BDSG, UK-GDPR) — even if not in the original 6-search Gate C results.

**State-level framework rule (US):** for FinServ/Healthcare/Insurance prospects, always add the relevant state-level framework row in addition to federal:
- Insurance carriers → NAIC Insurance Data Security Model Law (adopted by 25+ states; mirrors NYDFS)
- Healthcare → state breach-notification regimes (e.g. TX HB 300, CA CMIA)
- FinServ NY-licensed → NYDFS Part 500 (always)

---

## What this checklist replaces

This is NOT a new research step. The data is already in the JSON files written by Gate A and Gate B. The cost of running this checklist is one extra read of those files plus the dossier build — zero RocketReach credits, zero web_search budget.

If the dossier you produce has fewer than 8 entries in `signals.positive[]`, fewer than 5 entries in `org_intelligence.additional_stakeholders[] + future_stakeholders[]`, or fewer than 4 rows in `compliance[]`, you have skipped this checklist. Run it.
