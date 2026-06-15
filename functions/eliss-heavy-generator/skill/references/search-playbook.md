# ELISS Search Playbook v4 — Intelligence-Grade Research

Execute research layers in order. Each layer informs which queries in the next layer are worth running.

**Companion file:** `references/intelligence-feeds.md` contains the full catalog of **300+ curated data sources across 27 categories** (v6.0 expansion). Each layer below cross-references it — when you see **📚 Feeds:** that's your cue to consult the catalog for the best sources given the prospect's profile and your access level (paid vs. free).

> **v7.0 — Run the preflight script first.** `python scripts/preflight.py <domain>` hits ~8 deterministic free public endpoints (DNS/MX, crt.sh, Microsoft tenant resolution, Web Archive, SEC EDGAR, USAspending, ransomware.live, GitHub, optional HIBP) and writes a JSON file that the skill reads at Layer 1. This moves ~8 mandatory OSINT checks out of Claude's tool budget entirely. The sub-queries below are then executed via the parallel subagent fan-out documented in `SKILL.md` STEP 2 "Parallel Dispatch Pattern" — four concurrent `Agent`-tool subagents, each with its own tool budget, rather than a single-session sequential run.

---

## Layer 1: Identity & Foundation (2-3 searches)

**📚 Feeds:** Firmographic (§5), Sales Intelligence (§3), CRM Enrichment (§11). Start with LinkedIn Company Page (free) + Glassdoor/Crunchbase for triangulation. For EU/UK prospects use **OpenCorporates** (140 jurisdictions) or **UK Companies House** (free, authoritative). If paid access available → ZoomInfo/Cognism consolidates this layer.

**Person:**
- `"[Full Name]" "[company]" site:linkedin.com`
- `"[Full Name]" "[company]" title OR role OR director OR VP OR manager`

**Company:**
- `"[company]" employees revenue industry headquarters`
- If domain is unusual: `site:[domain] about OR "about us" OR company`

**After Layer 1 you know:** Name, title, company, size, industry, HQ. Proceed.

---

## Layer 2: Technology & Security Posture (3-5 searches)

**📚 Feeds:** Technographic (§1), Intent (§2), Job Postings (§8), News (§7), **Security OSINT (§14)** for infrastructure fingerprinting, **Website Monitoring (§17)** for historical change detection, **Partner Ecosystems (§19)** for cloud posture. Job postings via LinkedIn Jobs + Indeed are the #1 signal source. For confirmed tech install data, HG Insights is the best paid feed; BuiltWith and Wappalyzer free tiers cover web-facing tech only.

The most important layer for AD360/Log360 fit scoring. Job postings are the single best source — they reveal tech stack, budget priorities, and team structure before any press release.

**Job posting intelligence (highest priority):**
- `"[company]" hiring "Active Directory" OR "Azure AD" OR "Entra ID" OR "identity management" site:linkedin.com OR site:indeed.com`
- `"[company]" hiring "SIEM" OR "security analyst" OR "SOC" OR "incident response" OR "CISO"`

**Tech stack discovery:**
- `"[company]" site:stackshare.io OR site:builtwith.com`
- `"[company]" "Active Directory" OR "Microsoft 365" OR "Azure AD" OR "Windows Server"`
- `"[company]" "cloud migration" OR "digital transformation" OR "IT modernization" 2025 OR 2026`

**Infrastructure fingerprinting (§14 — zero-contact OSINT):**
- **MXToolbox** → `mxtoolbox.com/SuperTool.aspx?action=mx%3a[prospect-domain]` — email platform reveals Microsoft vs. Google vs. on-prem
- **crt.sh** → `crt.sh/?q=[prospect-domain]` — SSL cert history reveals subdomains (`adfs.`, `vpn.`, `owa.`) confirming AD/Exchange
- **Shodan** (if account) → `org:"[company name]"` — exposed services indicate attack surface (and AD360/Log360 hardening pitch)
- **Netcraft** → web server + hosting history shows cloud migrations

**Security posture:**
- `"[company]" "security incident" OR "data breach" OR "ransomware" OR "cyberattack" 2024 OR 2025 OR 2026`
- `"[company]" "SIEM" OR "Splunk" OR "QRadar" OR "Sentinel" OR "log management"`

**Tech review sites (check if the company has a profile):**
- `"[company]" site:g2.com OR site:capterra.com OR site:trustradius.com OR site:peerspot.com`

**Historical change detection (§17):**
- `web.archive.org/web/*/[prospect-domain]/careers` — compare 6-12mo snapshots of careers page for hiring trend
- `web.archive.org/web/*/[prospect-domain]/security` — track when/if they added a security/trust page

---

## Layer 3: Compliance & Regulatory (2-3 searches)

**📚 Feeds:** News (§7) for audit findings; SEC EDGAR (in §6) for public-company cybersecurity disclosures (now mandatory in 10-Ks); Job Postings (§8) for compliance role hiring; **Legal & Regulatory (§15)** for litigation + breach-notice records; **Gov Contracts (§16)** for federal/state procurement history when prospect is public sector.

Skip this layer if the company is clearly in an unregulated industry with <100 employees.

- `"[company]" "SOC 2" OR "HIPAA" OR "PCI-DSS" OR "SOX" OR "GDPR" OR "FISMA" OR "ISO 27001"`
- `"[company]" "audit" OR "compliance" OR "regulatory" OR "certification" 2024 OR 2025 OR 2026`
- `"[company]" "compliance officer" OR "audit finding" OR "remediation" OR "regulatory fine"`

**For healthcare:** `"[company]" "HIPAA" OR "PHI" OR "electronic health record" OR "patient data"`
**For financial:** `"[company]" "SOX" OR "PCI" OR "GLBA" OR "OCC" OR "SEC filing" OR "10-K"`
**For government:** `"[company]" "FedRAMP" OR "FISMA" OR "NIST" OR site:sam.gov`

**Litigation & regulatory action checks (§15):**
- CourtListener → `courtlistener.com/?q=[company name]` — any active federal cases?
- Federal Register → `federalregister.gov/documents/search?conditions[term]=[company]` — has an agency proposed a rule affecting them?
- For US states, check the AG's catastrophe-notice / breach-notification page directly (e.g. Texas AG, California AG Data Security Breach Reports) — confirms breach timing + scope

**Government prospects only (§16):**
- SAM.gov → `sam.gov/search/?keywords=[agency]` — their active contract opportunities and vendor registrations
- USAspending.gov → search by agency → reveals prior IT spend, existing security vendors (= displacement targets), typical contract vehicle

---

## Layer 4: Financial Intelligence (2-3 searches)

**📚 Feeds:** Financial (§6) for public cos (SEC EDGAR is primary, free; OpenInsider + WhaleWisdom for insider/institutional signals); Firmographic (§5) — Crunchbase/PitchBook/OpenCorporates — for private cos; SaaS benchmarks (in §6: GetLatka, Tom Tunguz) for private SaaS prospects; Glassdoor reviews (§5) for org-health signals regardless; **Gov Contracts (§16)** if the prospect is a public-sector entity.

**For public companies:**
- `"[company]" annual report OR 10-K OR earnings "IT spending" OR "technology investment"`
- `"[company]" site:sec.gov 10-K` (for SEC filings)
- `"[company]" investor relations revenue 2025 2026`
- OpenInsider → `openinsider.com/[ticker]` — recent insider trades (selling = caution flag; buying = confidence)
- WhaleWisdom → `whalewisdom.com/stock/[ticker]` — institutional holding changes (large fund exits = risk)

**For private companies:**
- `"[company]" funding OR "Series" OR acquisition site:crunchbase.com OR site:pitchbook.com`
- `"[company]" revenue OR valuation OR growth`
- GetLatka → `getlatka.com/companies/[company]` — CEO-reported SaaS metrics if they're a SaaS business

**For public-sector prospects (§16):**
- USAspending → lists contracts awarded TO the agency's vendors (IT budget pattern)
- SAM.gov → active opportunities signal upcoming procurements

**For all companies — organizational health:**
- `"[company]" site:glassdoor.com OR site:indeed.com reviews` (recent reviews reveal org health, culture, turnover)
- `"[company]" "layoffs" OR "hiring freeze" OR "restructuring" 2025 OR 2026`

### IT Budget Estimation Methodology

**Step 1: Estimate revenue**
```
Revenue = Employee Count × Revenue-per-Employee (industry benchmark)
```

| Industry | Rev/Employee |
|---|---|
| Technology / SaaS | $200K–$500K |
| Financial Services | $300K–$800K |
| Healthcare | $100K–$250K |
| Manufacturing | $150K–$400K |
| Retail / eCommerce | $100K–$300K |
| Professional Services | $150K–$350K |
| Education | $80K–$200K |
| Government | $100K–$200K |
| Insurance | $250K–$500K |

**Step 2: Estimate IT budget**
| Industry | IT as % Revenue | Security as % of IT |
|---|---|---|
| Technology / SaaS | 8–15% | 15–25% |
| Financial Services | 7–12% | 15–20% |
| Healthcare | 5–9% | 10–18% |
| Insurance | 6–10% | 12–18% |
| Retail / eCommerce | 3–6% | 8–15% |
| Manufacturing | 2–5% | 8–12% |
| Professional Services | 4–7% | 10–15% |
| Education | 3–6% | 8–12% |
| Government | 3–7% | 12–20% |

**Step 3: Show the math**
Example: "FinServ company, ~3,200 employees × $500K rev/emp = ~$1.6B revenue → 9.5% IT = ~$152M IT budget → 17% security = ~$25.8M security budget. AD360+Log360 at $40K is 0.15% of security budget — trivially affordable."

### Deal Authority by Title
| Title | Authority | Deal Limit |
|---|---|---|
| CIO / CTO / CISO | Full | Unlimited (within IT budget) |
| VP IT / VP Security | Major | Up to $500K |
| IT Director / Security Director | Departmental | Up to $200K |
| IT Manager / Security Manager | Project | Up to $50K |
| AD Admin / Analyst | Evaluator | Recommends only |

---

## Layer 4b: Procurement Cycle Intelligence (2-4 searches) [v6.0+]

**Purpose:** Populate the **Buying Signals Timeline** with procurement-cycle data points — fiscal-year windows, budget approval dates, RFP/RFI publications, contract expirations, grant awards, audit-driven remediation deadlines, and internal process signals. These are what turn a HOT/WARM lead from "interested" to "actually procuring in the next 90 days."

**📚 Feeds:** Gov Contracts (§16), Cooperative Purchasing (§22), Legal & Regulatory (§15), Local Government Intelligence (§5 sub-section), Document & Court Records (§26), Financial (§6).

**For each prospect, attempt to map 4–8 of the following signal categories.** Tag each resulting signal with `signal_category: "procurement_cycle"` in the JSON so the report generator color-codes it distinctly in the timeline visualization. Confidence tiers: Tier A = authoritative (gov filings, press releases, council minutes), Tier B = reputable secondary (trade press, job postings), Tier C = inference (industry-convention estimates).

### A. Fiscal year boundary detection (Tier A/B)
Knowing when the prospect's fiscal year starts tells you when budget decisions get locked and when the procurement window opens.
- **Public companies:** `"[company]" "fiscal year" site:sec.gov` — 10-K "Item 1" states FY convention explicitly
- **US Federal agencies:** Fiscal year starts Oct 1 (universal) — always true, Tier A inference
- **US State/Local:** Most states FY starts July 1 (TX, CA, NY, FL, IL, etc.); exceptions are NY state FY Apr 1, TX state FY Sep 1 for some; check the prospect's state budget office → "[state] fiscal year" → state.gov budget page
- **US Municipalities:** Usually match state FY; check city CAFR or budget PDF
- **SaaS/Tech companies:** Usually calendar year (Jan 1) or Feb 1 (e.g., Microsoft FY July 1)
- **Action:** populate `procurement_cycle[]` with `{type: "fiscal_year_start", date: "2026-07-01", confidence: "HIGH", source: "City FY26 Budget (page 3)"}`

### B. Budget approval/passage detection (Tier A)
Annual budget passage is typically 2-4 months before FY start. The passage date confirms budgets are locked.
- Legistar/Granicus → `[city].legistar.com` → search agenda items for "budget," "appropriation," "ordinance FY26 budget"
- State budget offices → `"[state] state budget FY26 signed"` for enacted signing dates
- City press releases → `"[city]" "budget" "approved" OR "adopted" FY26`
- For companies, earnings call mentions → `"[company]" "fiscal 2026 guidance" OR "capital allocation"`

### C. Contract expiration inference (Tier A/B)
Existing vendor contracts expiring = procurement window opening.
- USAspending.gov → `usaspending.gov/search` → filter by recipient name + NAICS 541512 (Computer Systems Design) or 541519 (Other Computer Related). Look at `period_of_performance_end_date` for existing Splunk/SailPoint/Okta/CrowdStrike contracts
- SAM.gov → `sam.gov/opportunities` → search `[prospect agency name] AND (SIEM OR "identity management" OR "privileged access" OR "security monitoring")` for active opportunities
- State procurement portals — most states publish contract awards with expiration dates:
  - TX: `comptroller.texas.gov/purchasing/contracts/`
  - CA: `caleprocure.ca.gov`
  - NY: `nyspro.ogs.ny.gov`
- Standard inference: **3-year contract rule** — for any detected incumbent from Layer 6, the default Timing assumption is contract renewal at year 3 of the relationship. Initial purchase year detectable via: press-release archives, Wayback Machine of prospect's "Partners" or "Technologies" page, case-study publication date from the vendor, analyst reports (Gartner client references).

### D. RFP / RFI / ITN publication detection (Tier A)
Active procurement documents are the single strongest Timing signal — it means the prospect is already buying.
- SAM.gov → federal opportunities
- Local procurement portals: BidNet Direct, PlanetBids, DemandStar, GovernmentBids — searchable by keyword + jurisdiction
- GovWin IQ (Deltek) → PAID, but aggregates state/local/federal opportunities
- Periscope S2G (mdf.com) → some states
- General Google: `"[prospect]" (RFP OR RFQ OR ITN OR ITB) (SIEM OR SOC OR "security operations" OR "identity governance" OR "privileged access management")`
- Detection means the deal cycle started ~30 days before the RFP dropped (internal scoping). Bid deadline + 6-12 weeks = award decision window.

### E. Budget amendment votes (Tier A, public sector)
Mid-year budget transfers often indicate project approvals not anticipated in the original budget — a quiet "we just got funding" signal.
- Legistar → search `[city].legistar.com` for "budget amendment," "transfer," "supplemental appropriation"
- State comptroller/treasurer offices — mid-year amendment notices
- Meeting minutes → `"[city]" "budget amendment" OR "budget transfer"` — these often have line-item detail
- **Interpretation:** a mid-year IT or security amendment that the prospect's department championed = a high-Tier procurement signal within the next 60-90 days

### F. Cybersecurity grant awards (Tier A, public sector & some non-profits)
Many public-sector cyber purchases are grant-funded. Grant awards are often announced 6-12 months before purchases get made.
- **grants.gov** → `grants.gov/search-grants` → filter by CFDA 97.067 (CISA SLCGP - State & Local Cybersecurity Grant Program) or 97.008 (HSGP)
- **CISA SLCGP announcements** → `cisa.gov/cybergrants` — lists state-level grantees, which then sub-grant to municipalities
- **state homeland-security agency pages** → state-level SLCGP distribution announcements
- **DOJ BJA grants** → `bja.ojp.gov/funding/awards` for justice-sector cybersecurity grants
- **Foundation grants for nonprofit cyber** — `foundationcenter.org` for nonprofit prospects
- **Interpretation:** A prospect named in an SLCGP state subaward with "endpoint detection," "identity management," or "SIEM" in the use-of-funds text = Tier A Timing trigger

### G. Audit findings / remediation deadlines (Tier A)
External audit findings often carry mandatory remediation deadlines that drive procurement.
- **State auditor reports** → `"[state] state auditor" site:[state].gov` → many states publish annual local-government IT-audit summaries. A finding of "inadequate audit logging" or "privileged access not reviewed" = direct Log360/AD360 pitch + a deadline.
- **SEC 10-K MD&A / Risk Factors** → `"[company]" 10-K "material weakness" site:sec.gov` — SOX material weaknesses must be remediated within specific timeframes
- **HHS OCR Corrective Action Plans** → `ocrportal.hhs.gov/ocr/breach/breach_report.jsf` → breach entries with "CAP" or "Resolution Agreement" → formal remediation with deadlines
- **FTC Orders** → `ftc.gov/legal-library/browse/cases-proceedings` — consent orders with cybersecurity mandates (e.g., the Equifax order)
- **State AG settlement agreements** → state AG press releases with "cybersecurity" + "settlement" terms
- **Interpretation:** Audit or regulatory deadline ≤12 months out = Tier A Imminent Timing signal

### H. Compliance-rule effective dates (Tier A)
Regulatory deadlines are independent of the prospect's choice to procure but they are deterministic triggers.
- **Federal Register** → `federalregister.gov/search` → filter by effective date + agency (CISA, NIST, HHS OCR, DOL)
- **NIST SP revision windows** — NIST SP 800-53 revisions trigger 12-month compliance windows for federal-contractor-regulated entities
- **PCI DSS 4.0** (effective April 2024 for new requirements) — payment-card entities have remediation deadlines
- **CMMC** — DoD contractor certification deadlines by contract type
- **NYDFS 23 NYCRR 500** amendments — financial services in NY
- **SEC Cyber Disclosure Rules** — 4-business-day incident disclosure for public companies
- **Interpretation:** Prospect's industry + a known compliance deadline within 12 months = Tier A Timing signal

### I. Vendor bake-off / evaluation signals (Tier B)
Indirect evidence that a vendor evaluation is active.
- **Job postings requiring specific vendor experience** → Greenhouse, Lever, LinkedIn → `"[company]" "[Splunk|Sentinel|QRadar|SailPoint|Okta|CyberArk] administrator"` — a hire for a specific vendor = they own or are deploying that vendor NOW
- **Conference speaker submissions** → Sessionize + BSides + DEF CON archives → prospect staff speaking about "our SIEM migration" or "Zero Trust journey" = current initiative
- **Trade-press case studies** — `"[company]" (case study OR testimonial) (SIEM OR identity OR PAM)` — case-study publication = incumbency anchoring
- **Analyst-report client references** — Gartner MQ or Forrester Wave client references list = confirmed customer (often with renewal window inference)

### J. Internal process/policy signals (Tier B/C)
- **New procurement specialist hire** → LinkedIn → `"[company]" procurement specialist` — new hires often signal process tightening
- **New IT procurement ordinance** → Legistar → `[city].legistar.com` → search "procurement" "ordinance" "IT" — municipal procurement-process overhauls
- **CapEx vs OpEx classification** → Municipal CAFR or corporate 10-K — if security is being capitalized (CapEx) = multi-year commitment = longer evaluation cycle. If opex = potentially faster decision path.

### K. Conference speaking engagements (Tier B)
- **Sessionize** → `sessionize.com/event/[event]` — speaker bios often reveal current initiatives
- **RSA Conference** → `rsaconference.com/usa/agenda` — speaker bios
- **Gartner Security & Risk** — client-speaker list
- **BSides community** → `bsides.org/events` — local chapter speaker lineups (often have IT directors speaking about actual deployments)
- **Interpretation:** Prospect's IT/Security leader speaking at conference about a topic X = they either have X deployed or are deploying it now. Either way = Timing signal.

### L. Partnership & integrator announcements (Tier A/B)
- **Prospect press releases** → announcing new SI partnerships (Accenture, Deloitte, CDW, etc.) — often precede RFP activity by 3-6 months
- **SI press releases** → "[SI name] named implementation partner for [prospect]" — same
- **Interpretation:** New SI = new project pipeline; old SI = renewal-driven procurement

### M. Executive-change procurement signals (Tier A)
- **LinkedIn profile changes** → new CIO, CISO, IT Director appointment
- **Press releases** → leadership transition announcements
- **Conference bios** — sometimes update faster than LinkedIn
- **Interpretation:** New CISO typically arrives with a security-tooling evaluation budget (often $100K-$500K) within 90-180 days of start. Tier A Timing trigger.

### N. M&A / integration events (Tier A)
- **SEC 8-K filings** — acquisition disclosures
- **Press releases** — "[company A] acquires [company B]"
- **Crunchbase** — acquisition timeline
- **Interpretation:** 12-24 months post-acquisition = systems integration period = high IAM/SIEM consolidation demand. Tier A Timing trigger especially when acquirer is MS-heavy and acquired uses on-prem AD.

### O. Earnings-call / investor-communication cybersecurity mentions (Tier B)
For public companies only.
- Seeking Alpha, Motley Fool transcripts → search transcripts for "cybersecurity," "security investment," "zero trust," "identity management"
- Interpretation: CEO/CFO-level mentions = board-level priority = procurement intent + budget availability. Tier B because CEOs mention many initiatives.

### P. Breach-remediation public commitments (Tier A)
Post-breach prospects often publicly commit to specific remediation timelines.
- State AG notification letters (§22) — often detail remediation commitments and deadlines
- HHS OCR Resolution Agreements — formal remediation plans with deadlines
- Press releases — "We will deploy [technology] by Q3 2026" type language
- **Interpretation:** Deadline ≤12 months = Tier A Imminent Timing trigger. The Coppell case had this pattern — explicit multi-departmental remediation plan published with the breach notification letter.

---

## Layer 5: Organizational Intelligence (2-3 searches)

**📚 Feeds:** Org Chart (§9) — LinkedIn Sales Navigator is best; Apollo.io covers free-tier needs. For C-suite specifically, RocketReach.

The goal: identify 2-3 other people who matter in the purchase decision, so the sales rep can multi-thread.

- `"[company]" "CIO" OR "CISO" OR "CTO" OR "VP IT" OR "VP Security" site:linkedin.com`
- `"[company]" "IT Director" OR "Security Director" OR "Infrastructure" site:linkedin.com`
- `"[company]" org chart OR leadership team site:[domain]`

**Local Autonomy checks (ELISS v5.5+) — run when the prospect is a subsidiary, regional office, or business unit:**
- `"[parent company]" "standardize on" OR "global standard" OR "enterprise-wide" "security" OR "SIEM" OR "identity"`
- `"[parent company]" "Splunk" OR "SailPoint" OR "Microsoft Sentinel" OR "CyberArk"` — any parent-level incumbent a local office would be forced to adopt
- `"[subsidiary]" "local" OR "regional" "IT budget" OR "procurement authority"` — signals the subsidiary can buy independently
- Check if the contact's LinkedIn title says "[Company] [Country]" (e.g. "AIG Israel") vs. a global title — regional titles often signal constrained buying authority
- If parent-level incumbent detected AND contact is subsidiary-level: classify Local Autonomy as LOW and fire the `low_local_autonomy` (−12) modifier. Worth noting explicitly in the dossier even for MEDIUM autonomy cases (point-tool positioning under the spend threshold still viable).

Map the decision-making unit:
- **Economic buyer**: Who controls the budget? (Usually CIO/CFO/VP)
- **Technical evaluator**: Who runs the POC? (Usually IT Manager/AD Admin/Security Analyst)
- **Champion**: Who's feeling the pain most acutely? (Often the person who contacted you)
- **Blocker**: Who might resist? (Incumbent vendor champion, risk-averse executive)

**Ghost Stakeholder queries (ELISS v5.6+) — run for every prospect, not only when something looks missing:**

Ghost stakeholders are the people who will own the decision in 60–90 days but haven't started yet. The open req for an InfoSec Engineer, SIEM Architect, IAM Analyst, or CISO is often the single most decision-useful piece of intelligence on the account. Their first 90 days define the shortlist.

- `site:[domain]/careers OR site:[domain]/jobs "security" OR "SIEM" OR "identity" OR "CISO" OR "infosec"`
- `"[company]" "hiring" OR "now hiring" OR "we're looking for" "security engineer" OR "security architect" OR "SIEM" OR "identity" 2025 OR 2026`
- `site:linkedin.com/jobs "[company]" "security engineer" OR "CISO" OR "identity" OR "SIEM"`
- Public-sector prospects: `site:governmentjobs.com "[city/agency]" security OR cybersecurity OR "information security"`
- Indeed / Glassdoor / BuiltIn: `"[company]" site:indeed.com "security" OR "SIEM" OR "identity"` — filters often include role level (senior/staff/principal) which signals the level of authority the new hire will carry
- Press releases: `"[company]" "announces" OR "appoints" OR "welcomes" "CISO" OR "Chief Information Security" OR "VP Security"` — if an appointment happens mid-eval, that person's first-90-days tool review is essentially the deal

**For each open role found, record:** title, status (posted / interviewing / offer-stage), estimated arrival, role scope (what they'll own), risk (which previous vendor might they bring in?), opportunity (are they reachable now before they start?), and an explicit action the rep can take in the next 7 days. Empty ghost-stakeholder list is only acceptable with documented confirmation the analyst ran these queries and found nothing relevant.

---

## Layer 6: Competitive Intelligence (1-3 searches, if Layer 2 shows SIEM/IAM activity)

**📚 Feeds:** Competitive (§12) — G2/Gartner Peer Insights + **PeerSpot** (best for enterprise SIEM/IAM reviews) + TrustRadius; **Security OSINT (§14)** to confirm infrastructure signals of specific tools; **AlternativeTo** (§12) for displacement mapping; SimilarWeb for traffic-based signals; Owler for competitor maps.

- `"[company]" "SailPoint" OR "CyberArk" OR "One Identity" OR "Okta" OR "Ping Identity"`
- `"[company]" "Splunk" OR "QRadar" OR "Sentinel" OR "Elastic SIEM" OR "LogRhythm" OR "Exabeam"`
- `"[company]" "replaced" OR "migrated from" OR "switched to" OR "evaluated" SIEM OR IAM OR "identity management"`
- PeerSpot → `peerspot.com/products/[competitor]/reviews` — filter by reviewer industry/size matching prospect; sometimes reveals named installs
- AlternativeTo → `alternativeto.net/software/[competitor]` — shows what current users consider switching to (reverse-angle: who mentions ManageEngine)

**Probabilistic inference when direct evidence is absent (ELISS v5.6+):**

"None detected" is almost always wrong. If the queries above surface nothing, the analyst infers the most likely incumbents from the prospect's tech-stack profile and names them in the Competitive Threat Matrix with Likely / Possible / Unlikely labels. The point is to hand the rep a pressure-tested shortlist they can falsify on the first discovery call, not to claim certainty.

Baseline heuristics (adjust for sector and size):
- **Microsoft-heavy shop (M365/Entra/Azure)** → Microsoft Sentinel + Defender XDR are at minimum *Possible* and usually *Likely*. Cost to add to existing E5 is marginal.
- **Post-breach mid-market (200–2,000 emp)** → CrowdStrike Falcon and Palo Alto Cortex XDR are at minimum *Possible* — both are common post-breach purchases.
- **Sub-500-emp shops** → Splunk is *Unlikely* (cost-prohibitive); Elastic Security and Wazuh are *Possible* at the engineering-heavy end.
- **Financial services / Healthcare / Regulated** → SailPoint or Saviynt for IGA is at least *Possible* above 1,000 emp; below that, built-on-AD is the default.
- **Government / Public sector** → Microsoft GCC + Splunk (via GovCloud) are both *Possible*. FedRAMP-authorized tools get preference; this filters the plausible competitor list hard.

For every Likely entry, also run the renewal-intelligence queries below — the inferred incumbent's adoption-date press release is the best single confirmation and feeds the Timing dimension.

**Competitive Readiness Score (1–10):** after building the matrix, score ME's preparedness to win against the most likely incumbent. Weigh product fit (does ME cover what the incumbent does?), pricing leverage (flat vs. ingest-based?), brand recognition in the segment, channel coverage, and reference customers. Score calibration: 8–10 = ME clearly wins on multiple axes, run the play hard; 5–7 = competitive but no guaranteed win, POC required; 1–4 = uphill battle, consider channel partner or point-tool positioning only.

**Contract renewal intelligence (ELISS v5.5+) — run for every incumbent detected above (including inferred-Likely); this feeds the Timing dimension:**
- `"[company]" "[incumbent]" "selected" OR "chose" OR "partnership" OR "implementation" 2022 OR 2023 OR 2024` — find when the incumbent was adopted (purchase date + 3 years ≈ renewal window)
- `"[company]" "[incumbent]" "renewal" OR "contract" OR "extended" OR "multi-year"`
- `"[company]" "RFP" OR "request for proposal" OR "vendor evaluation" OR "procurement review" 2025 OR 2026` — active RFPs are Active Procurement tier (30)
- For public-sector prospects: SAM.gov + USAspending → `usaspending.gov/search/?keywords=[agency]+[incumbent]` — returns exact contract start/end dates (HIGH confidence renewal data)
- Glassdoor: `"[company]" site:glassdoor.com "[incumbent]"` — employee reviews sometimes mention renewal pain, licensing changes, or "we're stuck with X for another two years"
- LinkedIn posts from the prospect's procurement lead: `"[procurement lead name]" "[incumbent]" renewal OR contract OR "end of life"`

**Interpreting renewal signals for Timing scoring:**
- Confirmed renewal <6 months → Imminent need (24) or Active procurement (30)
- Estimated renewal 6–12 months → Strong trigger (18)
- Estimated renewal 12–24 months → Moderate trigger (12)
- Recently renewed (<12 months ago, 2+ year commit) → fire `recently_renewed_lockout` (−18), Timing caps at 6, lead is structurally cold
- No renewal data AND no other timing signals → "No data" (3)

**Interpret results carefully:**
- Job posting requiring "Splunk experience" = Splunk is in use (displacement opportunity for Log360)
- Press release about "partnering with CyberArk" = CyberArk recently purchased (negative modifier, but AD360 can coexist)
- RFP mentioning multiple vendors = active evaluation (high intent signal)

---

## Layer 7: Personal & Social Intelligence (1-2 searches, run for HOT/WARM leads)

**📚 Feeds:** Org Chart (§9) for verified titles; News (§7) for quoted appearances; developer-ecosystem sources if prospect is technical (Stack Overflow, GitHub, Dev.to per §1). Sessionize for conference speaker trails. Brand24 if you have budget for broader mention monitoring.

- `"[Full Name]" conference OR keynote OR presentation OR webinar OR podcast`
- `"[Full Name]" site:twitter.com OR site:x.com OR site:github.com OR site:medium.com`
- `"[Full Name]" interview OR quote OR "thought leadership"`
- Sessionize → `sessionize.com/[name]` — if they've spoken at conferences, this is the canonical archive
- GitHub → `github.com/[username]` — technical prospects' public repos reveal languages/interests

**What you're looking for:**
- Topics they care about (zero trust? compliance automation? cloud security?) → tailor messaging
- Communication style (technical detail vs. business outcomes?) → adjust pitch tone
- Network (who do they follow, who follows them?) → potential referral paths

---

## Search Best Practices

1. **Exact-match company names** to reduce noise: `"Acme Corp"` not `Acme Corp`
2. **Year-filter aggressively**: `2025 OR 2026` for signal freshness
3. **Job postings are gold**: they reveal tech stack, budget, priorities, and pain points before anything else does
4. **Cross-reference everything**: if LinkedIn says 2,500 employees and Glassdoor says 2,400, that's HIGH confidence. If only one source, that's MEDIUM.
5. **Adapt, don't follow blindly**: if Layer 1 reveals a 15-person startup in media, skip Layers 3-4 compliance and financial deep-dives. Use judgment.
6. **Note what you didn't find**: "No security hiring detected in the past 12 months" is a data point — it may mean a mature team or a company that under-invests in security.
