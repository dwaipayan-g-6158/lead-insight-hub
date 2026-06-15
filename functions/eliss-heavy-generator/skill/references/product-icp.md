# ManageEngine AD360 & Log360 — Product Intelligence & ICP

> **Version markers — scoring feeds that evolved over time:**
> - **v5.4+** — Budget sub-allocation rules added: IAM & IGA Sub-Budget = 12% of Security Budget (addressable for AD360), SIEM Sub-Budget = 15% of Security Budget (addressable for Log360). See `SKILL.md` "Budget Sub-Allocation Rules" for the cross-check mechanics.
> - **v5.5+** — Dimension weights reweighted. Intent max 35 → **25**; Timing max 20 → **30**. The 10-point shift reflects that renewal-window triggers and trigger events (new CISO, breach, audit finding, M&A) are stronger predictors of closed-won than soft intent signals (content engagement, hiring patterns). Also added renewal-window triggers (<6mo → Imminent 24, 6–12mo → Strong 18, 12–24mo → Moderate 12) and the `recently_renewed_lockout` negative modifier (−18) for incumbents just locked in for 2+ years.
> - **v5.5+** — Local Autonomy classification (HIGH / MEDIUM / LOW) for subsidiaries and regional offices. LOW fires a `low_local_autonomy` (−12) structural negative modifier.
> - **v5.6+** — Deal Execution Risks (−2 to −5 each) feed a second `risk_adjusted_composite` displayed alongside the raw composite. Tier is still determined by raw score; the adjusted number directs mitigation energy. Execution risks are separate from the structural negative modifiers above.
> - **v5.6+** — Competitive Threat Matrix: "None detected" is no longer an acceptable full competitive picture. Every dossier infers probabilistic competitive presence (Likely / Possible / Unlikely) with explicit basis when direct evidence is missing. Includes a Competitive Readiness Score (1–10) and a Ghost Stakeholders list for open roles that will own the evaluation once filled.
> - **v6.0+** — Layer 4b Procurement Cycle Intelligence (16-category signal taxonomy: fiscal-year boundaries, contract expirations, RFP/RFI, budget amendments, cyber grants, audit findings with deadlines, etc.).
> - **v6.1+** — Mandatory Free-OSINT Checklist (29 zero-cost checks required every lead) + `data_quality.sources_actually_checked[]` coverage logging + optional RocketReach enrichment (opt-in via `RR_API_KEY`).
> - **v6.1.1+** — Tier-keyed research-depth floors: HOT ≥20 sources / ≥10 signals / ≥3 named DMU; WARM ≥12/≥6/≥2; COOL ≥8/≥4/≥1. Shipping a HOT score on thin research auto-fires a depth-lint warning in `generate_report.py`.
> - **v6.2+** — Optional Wave 1 infographics: `scoring.scenarios[]`, `technology.web_fingerprint{}`, `recommendations.decision_tree{}`. Render when present; omitted if absent.
> - **v7.1+** — RocketReach premium expansion. All 8 API endpoints wired across Subagents A/B/C/D with per-endpoint session caps tuned for a premium account (1 account / 5 company_lookup / 10 company_search / 40 person_lookup / 30 person_search / 10 profile_company_lookup / 1 bulk_lookup batch of 100 / 20 check_status polls). Subagent C can now enumerate a target's entire executive DMU in one `person_search` + one `bulk_lookup` call, regex-match `job_history` for past roles at Splunk/Sentinel/QRadar to confirm incumbents (HIGH-confidence, not inferred), and auto-detect new-CISO signals via `job_change_signal`. Every RR-sourced value displays an inline orange `ᴿᴿ` pill in the rendered dossier (Rule 7, `dossier-template.md`). `meta.rocketreach_budget` JSON block reports per-endpoint call counts + per-pool credit consumption.
> - **v7.0+** — Research bottleneck removed via two composable mechanisms:
>   - **Preflight script** (`scripts/preflight.py`): 8-9 deterministic free public endpoints (DNS/MX + SPF/DMARC, crt.sh, Microsoft getuserrealm tenant resolution, Web Archive, SEC EDGAR, USAspending, ransomware.live, GitHub org, optional HIBP) run as offline Python before `/eliss` is invoked. Output JSON drops directly into `data_quality.sources_actually_checked[]`. Zero Claude tool cost.
>   - **Parallel subagent dispatch** (SKILL.md STEP 2 "Parallel Dispatch Pattern"): After Layer 1, four `Agent`-tool subagents (A: Tech, B: Compliance+Financial+Procurement, C: Org+Competitive, D: Behavioral) run concurrently, each with its own ~30-call budget. Effective budget per HOT dossier: ~100-110 web calls (vs. ~10-20 in v6.x).
>   Together these remove the "analyst runs 10 searches and either fakes the HOT score or silently downgrades" failure mode documented in v6.2.5.



## AD360 — Complete Feature Matrix

**Core Capabilities:**
- Active Directory management: bulk user operations, delegation, GPO management
- Microsoft 365 administration: Exchange, Teams, SharePoint, Azure AD/Entra ID
- Self-service password reset & account unlock (reduces helpdesk tickets 30-50%)
- Single sign-on (SSO) for cloud and on-premises applications
- Automated user lifecycle management: onboard → modify → offboard in minutes
- Real-time AD auditing: who changed what, when, and from where
- Compliance reporting: pre-built reports for SOX, HIPAA, PCI-DSS, GDPR, FISMA

**Key Value Props:**
- Reduces AD admin time by 90% through automation
- Eliminates manual provisioning errors that cause security gaps
- Provides audit-ready compliance reports in minutes instead of weeks
- Works with existing AD — no rip-and-replace needed

**AD360 vs. Competitors:**

| vs. SailPoint | AD360 is faster to deploy (days vs. months), lower cost, better for mid-market. SailPoint is stronger for enterprise-scale governance with complex multi-domain environments. |
| vs. One Identity | AD360 has broader M365 integration and simpler pricing. One Identity is stronger in privileged access management. |
| vs. Okta | Different focus — Okta is cloud identity/SSO, AD360 is on-prem AD management. Complementary in hybrid environments, but AD360 replaces Okta's AD integration modules. |
| vs. CyberArk | CyberArk focuses on privileged access (PAM). AD360 does broader identity lifecycle. Often co-exist, but AD360 can replace CyberArk's basic AD features at lower cost. |

---

## Log360 — Complete Feature Matrix

**Core Capabilities:**
- Unified SIEM: collect, correlate, and analyze logs from 750+ sources
- Real-time threat detection with ML-based anomaly detection
- User and Entity Behavior Analytics (UEBA)
- Integrated incident management and response workflows
- Cloud security monitoring: AWS CloudTrail, Azure, GCP, Salesforce
- Data Loss Prevention (DLP): content-aware monitoring
- Cloud Access Security Broker (CASB): shadow IT discovery, cloud app control
- File integrity monitoring and ransomware detection
- Compliance automation: PCI-DSS, HIPAA, SOX, GDPR, FISMA, GPG 13

**Key Value Props:**
- All-in-one SIEM + DLP + CASB (competitors charge separately for each)
- 70% lower TCO than Splunk/QRadar while covering same compliance requirements
- Deploys in hours, not months
- No per-GB pricing model — predictable costs regardless of log volume

**Log360 vs. Competitors:**

| vs. Splunk | Log360 is 70% cheaper, no per-GB pricing trap. Splunk is stronger for custom analytics at massive scale (10TB+/day). For compliance-focused SIEM, Log360 wins on value. |
| vs. IBM QRadar | Log360 is easier to deploy and manage. QRadar is stronger for large SOC teams with complex SOAR workflows. QRadar's pricing is also volume-based. |
| vs. Microsoft Sentinel | Log360 works across hybrid (not just Azure). Sentinel has deep Azure integration but gets expensive fast with non-Microsoft log sources. |
| vs. Elastic SIEM | Elastic requires significant engineering to operationalize. Log360 is turnkey. Elastic wins for teams with strong engineering who want full customization. |
| vs. Exabeam/LogRhythm | Similar market tier. Log360 differentiates on integrated DLP/CASB and lower cost. Exabeam is stronger on pure UEBA. LogRhythm is strong on compliance out-of-box. |

---

## Ideal Customer Profile — Detailed Scoring Rubrics

### Company Size Scoring (Max 8)
| Employees | Score | Rationale |
|---|---|---|
| 1–49 | 1 | Too small for AD complexity; may use cloud-only identity |
| 50–199 | 3 | Growing AD needs but limited budget |
| 200–499 | 5 | Solid AD environment, compliance starting to matter |
| 500–999 | 7 | Strong fit — AD complexity + compliance pressure + budget |
| 1,000–4,999 | 8 | Sweet spot — complex AD, regulatory pressure, budget available |
| 5,000–9,999 | 7 | Good fit but may evaluate Tier-1 vendors too |
| 10,000+ | 5 | Likely evaluating enterprise vendors; ME can win on value/speed |

### Industry Vertical Scoring (Max 7)
| Industry | Score | Rationale |
|---|---|---|
| Financial Services / Banking | 7 | Heavily regulated (SOX, PCI, GLBA), large AD environments, high security spend |
| Healthcare / Life Sciences | 7 | HIPAA mandate, PHI access control critical, audit-heavy |
| Government / Public Sector | 7 | FISMA/FedRAMP, strict access controls, AD-dependent |
| Education (Higher Ed) | 6 | FERPA, large user populations, seasonal provisioning waves |
| Insurance | 6 | Regulatory pressure (SOX, state regulations), legacy modernization |
| Manufacturing | 4 | Growing OT/IT convergence, but lower IT budget % |
| Retail / eCommerce | 4 | PCI-DSS for payments, but IT is cost center |
| Technology / SaaS | 5 | Technically sophisticated but may build vs. buy, or use cloud-native |
| Professional Services | 3 | Some compliance needs but less AD complexity |
| Media / Entertainment | 2 | Typically cloud-native, less AD dependency |
| Non-Profit | 2 | Budget constrained, smaller IT teams |

### Title/Seniority Scoring (Max 6)
| Title | Score | Why |
|---|---|---|
| CISO / CIO / CTO | 6 | Budget authority, strategic buyer |
| IT Director / VP IT / VP Security | 5 | Strong influence, often the actual decision-maker |
| IT Manager / Security Manager | 4 | Day-to-day evaluator, can champion internally |
| AD Admin / Security Analyst / Compliance Officer | 3 | Hands-on user, strong technical evaluator |
| Individual Contributor / Developer | 1 | May flag need but no purchase authority |

### Technology Alignment Scoring (Max 4)
| Signal | Score | Evidence |
|---|---|---|
| Confirmed AD + compliance need | 4 | Job posts mention AD, compliance tools detected |
| AD environment confirmed | 3 | Microsoft shop, AD mentioned in job posts |
| Microsoft shop likely | 2 | M365, Windows environment indicated |
| Unknown | 1 | No tech signals found |
| Linux/Mac-only / Cloud-native identity | 0 | No AD dependency — poor fit |

---

## Competitive Displacement Playbook

When a competitor is detected, shift from "why buy" to "why switch":

### Displacing SailPoint / One Identity (IAM)
- **Lead with:** Speed of deployment (days vs. months), lower cost, simpler licensing
- **Pain to probe:** "How long did your IGA implementation take? Are your teams actually using all the features?"
- **ManageEngine advantage:** Works alongside existing tools during transition; no rip-and-replace

### Displacing Splunk / QRadar (SIEM)
- **Lead with:** TCO — no per-GB pricing, predictable costs. "What does your annual Splunk bill look like?"
- **Pain to probe:** "Are you using 100% of what you're paying for? How much of your data are you forced to exclude due to cost?"
- **ManageEngine advantage:** Integrated DLP + CASB included; compliance reports built-in

### Displacing Microsoft Sentinel
- **Lead with:** Multi-cloud and hybrid support, not locked to Azure
- **Pain to probe:** "How much are you spending on non-Microsoft log ingestion? Is Sentinel covering your on-prem environment?"
- **ManageEngine advantage:** Flat pricing regardless of data source; works across AWS, Azure, GCP, and on-prem

---

## Common Objections & Responses

| Objection | Response Framework |
|---|---|
| "We already have [competitor]" | "How satisfied is your team with the deployment time and total cost? Many of our customers run AD360/Log360 alongside their existing tools initially — we can show value in a 2-week POC with zero disruption." |
| "ManageEngine is too small / not enterprise enough" | "ManageEngine serves 280,000+ organizations globally, including 60% of Fortune 500 companies. Our parent company, Zoho Corp, is profitable and privately held — no VC pressure, just product focus." |
| "We're evaluating Tier-1 vendors" | "We welcome that comparison. Would a side-by-side POC be useful? Most customers find we cover 95% of their requirements at 30-50% of the cost, deploying in days instead of months." |
| "Budget is tight this quarter" | "AD360/Log360 pricing starts under $1/user/month. More importantly, the ROI from automated provisioning alone typically covers the license cost within 6 months through helpdesk ticket reduction." |
| "We need to involve our CISO/CIO" | "Absolutely — would it help if I prepared a one-page executive briefing tailored to their priorities? I can highlight the compliance and risk reduction angles that typically resonate at the C-level." |
