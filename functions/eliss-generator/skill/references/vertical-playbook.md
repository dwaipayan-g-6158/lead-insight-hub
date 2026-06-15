# Vertical Operational Playbook — How each industry actually talks

> **Purpose.** When `company.industry` (or close proxies in `company.tags`/SIC/NAICS) maps to one of the nine sections below, every narrative-producing prompt — Subagents A/B/C/D and the parent synthesis (or, in `/eliss-light`, the single synthesis prompt) — MUST anchor its language on that section. The dossier exists so the rep walks into the call already speaking the customer's operational reality. Generic-vendor framings are a render-gate violation; see `mom-test-discipline.md` and the `[depth-lint] industry_language_missing` check.
>
> **How to cite.** Composer prompts cite this file by name in their reasoning ("per `vertical-playbook.md` § Banking"), and the `data.industry_operational_lens` field must use ≥2 phrases from the matched section's **Customer language** list. The `company.micro_segment` field must be a who-where slice that maps to one of the section's **Micro-segment slices** (or a documented variant).
>
> **Mom Test grounding.** Each section's Anchor Questions follow the book's good/bad bank verbatim (talk-me-through-the-last-time, how-are-you-dealing-with-it-now, implications, where-does-the-money-come-from). Bad-side questions are the ones that produce compliments and fluff. See `mom-test-discipline.md`.

---

## Banking & Financial Services

**Operational reality.** "System availability" here means *transaction continuity and audit trail integrity* — every minute a core-banking, payments, or branch-teller system is degraded is measured in stalled wires, failed ATM transactions, and OCC/FFIEC examiner exposure. The CISO answers to the Board's Risk Committee, not the CIO.

**Customer language.** *Examination cycle* (not "audit"), *issues management* / *MRA* / *MRIA* (Matters Requiring Attention / Immediate Attention), *third-party risk*, *core banking platform* (FIS, Fiserv, Jack Henry), *segregation of duties*, *privileged access review*, *FFIEC IT Handbook*, *change-window*, *T+1 settlement*, *FedNow*, *examiner findings*, *attestation*.

**Operating model defaults.** SecOps usually has 24×5 in-house coverage with weekend on-call rotations. PAM/IAM ownership often split across an Identity team and a Cyber Defense / Fusion Center. Change management runs through a CAB with mandatory Risk + Compliance sign-off. Two-line-of-defense model: 1st line ops, 2nd line risk, 3rd line internal audit (then external + regulator).

**Micro-segment slices** (pin one as `company.micro_segment`):
- *Regional bank, 50–200 branches, mid core-consolidation, OCC-examined* — wrestling with multi-AD-forest cleanup post merger.
- *De-novo digital-only bank, BSA/AML pressure, hosted core* — needs SOC2 + FFIEC parity without a Tier-1 SIEM budget.
- *Mid-market credit union, NCUA-supervised, <$10B assets* — examiner just flagged user-access-review cadence.
- *Top-50 US bank subsidiary, on a parent's enterprise contract* — low local autonomy; SIEM/IAM decisions ride the parent's renewal.

**Obstacle / workaround patterns.** The obstacle is almost always *change-window scarcity* + *parent-company tooling mandate* + *examiner-driven prioritization queue*. The workaround is usually a sprawl of scheduled SQL/PowerShell scripts feeding spreadsheets that the IAM lead manually reconciles before each quarterly access review.

**Sensitive-topic phrasings.** Don't say "breach" — say *security incident* or *event*. Don't say "you failed an audit" — say *the last exam cycle's findings*. Don't say "compliance gap" — say *open MRA* or *issue in remediation*. "How are you tracking remediation for the open items from the last exam?" lands; "are you struggling with compliance?" gets a polite brush-off.

**Anchor questions (good vs bad).**
| Good (signal-anchored) | Bad (generic) |
|---|---|
| "Talk me through the last access review cycle — where did you spend the most time chasing approvers?" | "Do you have a strong access review process?" |
| "What are the implications when an MRA misses its remediation date — who hears about it first?" | "Are MRAs a problem for you?" |
| "Where does the budget for the next SIEM refresh actually come from — Risk, IT, or Cyber's own line?" | "Do you have budget for security tooling next year?" |

**OSINT signals already in the harvest.** OCC Enforcement Actions, FDIC press releases, NYDFS Section 500.17 breach notifications, SEC 10-K Item 1C (Cybersecurity) disclosures, FFIEC Call Report tech-spend ratios, FedFin issuance dates (BSA, FedNow onboarding), USAspending if government-linked.

---

## Oil & Gas / Refining

**Operational reality.** "System availability" means *plant uptime and HSE safety integrity* — a downed control system isn't a Slack ping, it's a flaring event, a NERC-CIP reportable, or a TSA pipeline directive violation. IT is subordinate to OT/Operations; the CISO's hardest stakeholder is the Plant Manager, not the CFO.

**Customer language.** *OT* / *ICS* / *SCADA*, *Purdue model levels 0–3.5*, *DMZ between IT and OT*, *historian* (PI System / OSIsoft / AVEVA), *engineering workstation*, *jump host*, *site survey*, *turnaround* (planned shutdown), *NERC CIP-002 through CIP-014*, *TSA Pipeline-2021-01/02*, *API 1164*, *upstream / midstream / downstream*, *flare event*, *LOTO* (lockout-tagout).

**Operating model defaults.** Plant-level IT often reports dotted-line to corporate IT and solid-line to the Plant Manager. OT cybersecurity sits with Process Control Engineering, not the CISO. 12-hour shifts (days/nights, 4-on-4-off rotations) at the plant; corporate SOC is M–F business hours. Change windows aligned to turnarounds — sometimes only twice a year.

**Micro-segment slices.**
- *Midstream pipeline operator, post-2021 TSA directives, multi-state ROW* — under pressure to demonstrate 24×7 SOC visibility into OT.
- *Independent refiner, 1–3 sites, EPA Title V permitted* — IT/OT cybersecurity converging under a single new VP role.
- *Upstream E&P, frac-spread heavy, public ticker* — board started asking about ransomware after Colonial Pipeline.
- *Integrated supermajor's downstream subsidiary, on parent's GRC platform* — low autonomy, parent's tooling mandate.

**Obstacle / workaround patterns.** Obstacle: *OT vendor warranty clauses* (changing a Yokogawa/Honeywell config voids support) + *turnaround calendar* (no patch windows for 6 months) + *plant-network-air-gap mythology*. Workaround: an engineering laptop with a dual NIC that "occasionally" bridges the two networks, plus a 4-year-old version of WSUS in the OT DMZ.

**Sensitive-topic phrasings.** Don't say "your OT is exposed" — say *the IT/OT boundary's hardening posture*. Don't say "you missed CIP-007 patching" — say *the patch-cadence finding from the last NERC audit*. "How does your turnaround calendar shape what you can change between now and the next outage?" lands.

**Anchor questions (good vs bad).**
| Good | Bad |
|---|---|
| "Talk me through the last time a TSA directive landed — who in the org actually owned closing it?" | "Are TSA directives keeping you up at night?" |
| "How are you dealing with privileged jump-host access into the historian today — what does the rep on shift actually do?" | "Do you need better OT access control?" |
| "What are the implications if NERC flags the access-review process at the next on-site?" | "Would better access reviews help?" |

**OSINT signals already in the harvest.** FERC Form 715, NERC press releases, TSA Security Directive numbering, CISA ICS-CERT advisories citing the org, EPA ECHO, Job postings naming "OT cybersecurity," DOE LPO awards, SEC 10-K Item 1A (Risk Factors) language on ransomware.

---

## Aviation / Airports

**Operational reality.** "System availability" means *passenger ops and airfield continuity* — every minute of degraded DCS (departure control), BHS (baggage handling), or FIDS (flight info display) cascades into delays, CRMs, missed-bag rates, and IATA OTP slip. For airports specifically, a 30-minute IT outage at peak is a Reuters headline.

**Customer language.** *Common-use* (CUTE/CUPPS terminal infra), *DCS* (Amadeus Altéa, Sabre, Navitaire), *PSS* (passenger service system), *FIDS / BIDS / GIDS*, *AODB* (airport operational database), *RMS* (resource management), *Type-B / SITA messaging*, *load-control*, *turnaround time*, *NOTAM*, *PCI-DSS scope for self-service kiosks*, *TSA Surface Transportation Cybersecurity Toolkit*, *ASR* (air safety report), *IATA OTP*.

**Operating model defaults.** Airlines run a 24×7 NOC distinct from a 24×7 SOC; airports usually run a single 24×7 Airport Operations Center (AOC) where IT, security, and airfield ops sit together. Many systems are *common-use* — shared by multiple airlines on a single airport platform — so the airport's IT team is effectively a multi-tenant operator with airline tenants as "customers."

**Micro-segment slices.**
- *Mid-size regional airport authority, 5–15M PAX/year, FAA Part 139* — modernizing AODB with cybersecurity bolted on late.
- *LCC (low-cost carrier), single-fleet, point-to-point* — outsources most IT to a CUSS/CUTE vendor; CISO is a one-person team.
- *Legacy hub-and-spoke carrier post-merger* — multi-AD-forest, dual-PSS migration, examiner-grade scrutiny from cyber-insurers.
- *Ground handler servicing 30+ stations* — IT spread thin across stations, regulator pressure from each country's CAA.

**Obstacle / workaround patterns.** Obstacle: *vendor concentration* (Amadeus/Sabre own the PSS, change-requests take quarters) + *24×7 ops* (no maintenance window without an irrops impact assessment) + *multi-tenant common-use* (airport can't unilaterally change auth flows that affect carrier tenants). Workaround: a shared service account on the DCS with credentials in a shared password vault that "everyone knows."

**Sensitive-topic phrasings.** Don't say "outage" — say *irrops event* or *operational disruption*. Don't say "your IT can't handle this" — say *during peak banks, the system's headroom*. "How was the last winter-ops weekend in terms of system pressure?" lands.

**Anchor questions (good vs bad).**
| Good | Bad |
|---|---|
| "Talk me through the last irrops weekend — what did your access controls cost you in recovery time?" | "Do irrops events impact your security?" |
| "How are you dealing with vendor-account access into the DCS today — for the ground handlers and the cleaners?" | "Do you manage third-party access?" |
| "Where does the money for the next CUTE refresh come from — IT, terminal ops, or capex?" | "Do you have budget for security?" |

**OSINT signals already in the harvest.** FAA Service Difficulty Reports, DOT Air Travel Consumer Reports (irrops mentions), IATA OTP rankings, airport authority board minutes (capex requests), TSA Surface advisories, Eurocontrol cyber bulletins, recent CrowdStrike / Microsoft-Azure-outage references in the airport's press.

---

## Healthcare

**Operational reality.** "System availability" means *patient safety and care continuity* — EHR downtime forces a switch to paper, every minute of which costs the hospital nurse-time, billing-leakage, and OCR risk. "Compliance" is HIPAA but more importantly it's *survey* (Joint Commission/CMS) and *patient-safety event reporting*.

**Customer language.** *EHR* (Epic, Cerner/Oracle Health, Meditech, Athena), *downtime procedures*, *break-the-glass*, *PHI*, *ePHI*, *minimum necessary*, *OCR portal* (HHS public breach reporting), *Joint Commission survey*, *MEDITECH expanse*, *Charge capture*, *clinical informatics*, *RN super-user*, *RTLS*, *bed census*, *HHS 405(d) HICP*, *340B*, *VA/DOD MHS Genesis if federal*.

**Operating model defaults.** Clinical IT is often a 24×7 team distinct from the SecOps team; large IDNs have a dedicated CISO reporting to the General Counsel or the COO. Change freezes during go-lives, JCo survey weeks, and year-end. Many smaller hospitals outsource SOC entirely (managed SIEM/MDR).

**Micro-segment slices.**
- *Regional non-profit IDN, 5–15 hospitals, Epic Community Connect tenant* — examiner-grade pressure from cyber-insurers after Change Healthcare.
- *Academic medical center with a research arm* — dual mandate, NIH grant compliance + HIPAA + IRB.
- *Critical-access rural hospital, 25 beds, single-CIO* — outsourced SIEM/MDR, no internal SecOps headcount.
- *For-profit hospital corp, multi-state, public ticker* — under SEC Item 1C cyber disclosure pressure.

**Obstacle / workaround patterns.** Obstacle: *clinical workflow primacy* (anything that slows down a clinician at the bedside is killed) + *EHR vendor lock-in* (Epic/Cerner config gates everything) + *24×7 patient-care change windows* (essentially zero). Workaround: shared "department" Epic logins on shared workstations on wheels, plus break-the-glass usage that nobody reviews.

**Sensitive-topic phrasings.** Don't say "you had a breach" — say *the recent OCR portal entry* or *event*. Don't say "compliance gap" — say *open OCR investigation item* or *survey finding*. "How did the team handle the last downtime drill — what surfaced?" lands. *Never* lead with the word "ransomware" — say *availability event*.

**Anchor questions (good vs bad).**
| Good | Bad |
|---|---|
| "Talk me through the last EHR downtime — paper or full failover — how did your access controls behave?" | "Do you worry about EHR downtime?" |
| "How are you dealing with break-the-glass review today — who actually reads the report?" | "Do you have a break-the-glass process?" |
| "What are the implications if OCR flags the access-review cadence at the next data-request?" | "Are you HIPAA compliant?" |

**OSINT signals already in the harvest.** HHS OCR Wall of Shame entries (500+ PHI breach reports), Joint Commission Quality Check pages, CMS Quality Star ratings, AHA hospital cyber statements, 340B Apexus disclosures, SEC 8-K Item 1.05 (Material Cybersecurity Incident), state AG breach portals (CA, NY, IL, MA), MedTech ISAC bulletins.

---

## Public Sector / Government

**Operational reality.** "System availability" means *constituent-service continuity and election/safety mission integrity* — DMV systems down = lines around the block on the local news; a CJIS system down = police can't run plates. Procurement is calendar-driven (fiscal-year boundaries), not pain-driven; the buyer is rarely the user.

**Customer language.** *CJIS Security Policy*, *FedRAMP Mod/High*, *StateRAMP*, *FISMA Moderate/High*, *NIST 800-53 r5*, *RMF* (Risk Management Framework), *ATO* (Authority to Operate), *POA&M* (Plan of Action & Milestones), *Continuous Monitoring*, *eRulemaking*, *cooperative purchasing* (NASPO ValuePoint, Sourcewell, GSA Schedule), *MS-ISAC*, *EI-ISAC*, *whole-of-state cyber*, *appropriation cycle*, *RFI / RFQ / RFP / IFB*, *cyber grant* (SLCGP).

**Operating model defaults.** Tiny SecOps teams (often 2–6 FTE) across state/local/educational ("SLED") agencies, supplemented by MS-ISAC and the state's whole-of-state program. Federal civilian agencies run larger SOCs but defer to CISA for incident response. Procurement gates: market research → RFI → RFP → award (often 9–18 months).

**Micro-segment slices.**
- *US state agency, mid-sized, on a NASPO ValuePoint contract* — cyber-grant-funded SIEM modernization in motion.
- *County / municipal government, <500 employees* — uses cooperative purchasing, MS-ISAC for monitoring, no internal SOC.
- *K-12 district, 5–50 schools, multi-tenant Microsoft 365 EDU* — under state Department of Education cyber mandates.
- *Federal civilian agency component, FISMA Moderate ATO, MGT funded* — multi-year cyber modernization, FedRAMP-only vendor list.

**Obstacle / workaround patterns.** Obstacle: *appropriation cycle* (money exists only in specific windows) + *cooperative-purchasing vendor list* (off-list = procurement says no) + *ATO inheritance* (every new tool is a 6-month security-package fight). Workaround: a "pilot" running on a single department's budget for 18 months until someone finds a grant or a contract vehicle to scale it.

**Sensitive-topic phrasings.** Don't say "outdated" — say *behind on the modernization roadmap*. Don't say "compliance gap" — say *open POA&M item* or *finding in remediation*. "Where are you in the appropriation cycle right now?" lands. Cite the grant program by name (SLCGP, MGT, TMF).

**Anchor questions (good vs bad).**
| Good | Bad |
|---|---|
| "Talk me through the last ATO renewal — which control families ate the most time?" | "Is your ATO process painful?" |
| "Where does the money come from — appropriation, SLCGP, MGT, or department-level?" | "Do you have budget?" |
| "How are you dealing with continuous monitoring evidence collection today?" | "Do you need a SIEM?" |

**OSINT signals already in the harvest.** USAspending contract awards + end dates, SAM.gov RFI/RFP postings, state legislative cyber bills, CISA advisories citing the agency, MS-ISAC quarterly threat reports, OIG reports (FISMA), state portal breach-notice pages, SLCGP award announcements, K-12 Cyber Incident Map.

---

## Manufacturing

**Operational reality.** "System availability" means *line uptime and shipment-on-time* — a degraded MES, ERP, or warehouse system stalls the line, which stalls the truck, which slips OTIF and triggers customer chargebacks. The CISO answers to the COO via Operations or to the CFO via IT.

**Customer language.** *MES* (Rockwell FT ProductionCentre, Siemens Opcenter, Wonderware), *ERP* (SAP, Oracle, Infor, Dynamics 365 F&O), *historian*, *PLC / HMI / SCADA*, *ANDON*, *takt time*, *OEE* (overall equipment effectiveness), *OTIF*, *tier meeting*, *kaizen*, *line-side*, *gemba walk*, *NIST CSF*, *CMMC* (if defense supply chain), *ISO 27001*, *plant-floor network*.

**Operating model defaults.** Multi-plant manufacturers run a corporate SOC plus plant-level IT. Plant IT reports dotted-line to corporate IT, solid-line to the Plant Manager. Shift patterns 2- or 3-shift; changes scheduled around production runs. CMMC-bound defense suppliers operate to a higher control bar than commercial peers.

**Micro-segment slices.**
- *Tier-1 auto supplier, multi-plant, post-CHIPS-Act capacity expansion* — under cyber-insurer pressure after the 2024 industry wave.
- *Defense industrial base, DoD prime/sub, CMMC Level 2 in scope* — has a hard 2025–2026 attestation deadline.
- *Food & beverage manufacturer, FSMA/204 traceability mandates* — IT and quality-systems converging.
- *Mid-market private equity portfolio plant* — PE owner driving a centralized GRC platform across portfolio.

**Obstacle / workaround patterns.** Obstacle: *line-stop economics* (every minute counts, no maintenance window) + *legacy PLC stacks* (1990s gear running 2025 production) + *PE-owner centralization pressure*. Workaround: a plant-floor jump server with 6 admin accounts shared across 4 vendors and 2 contractors, plus a backup tape that goes home with someone on Fridays.

**Sensitive-topic phrasings.** Don't say "you got ransomware" — say *the production-impact event*. Don't say "patch your PLCs" — say *the line-floor patch backlog*. "How are you scheduling change against the production calendar?" lands.

**Anchor questions (good vs bad).**
| Good | Bad |
|---|---|
| "Talk me through the last production-impact event — what did the access trail look like the morning after?" | "Did you ever have a cyber incident?" |
| "How are you dealing with vendor-account access onto the plant floor — the MES vendor, the line builder, the integrator?" | "Do you manage third-party access?" |
| "Where does the money come from — capex, IT opex, or the plant's discretionary budget?" | "Do you have budget?" |

**OSINT signals already in the harvest.** SEC 10-K Item 1A on cyber operational risk, BIS / Commerce Department enforcement, CMMC SPRS public data, DCSA findings, OSHA accident reports (gives a glimpse of operational reality), customer SBOM / chargeback announcements (auto OEMs, retail buyers), CHIPS Act award announcements, FSMA 204 rule timelines.

---

## Retail

**Operational reality.** "System availability" means *POS continuity and e-commerce conversion* — a degraded POS at peak (Black Friday, BOGO weekend) is direct lost revenue measurable in dollars per minute. The CISO usually answers to the CIO; PCI is the daily heartbeat, not a once-a-year audit.

**Customer language.** *POS*, *PA-DSS / P2PE*, *PCI-DSS v4.0*, *card-not-present*, *EMV*, *tokenization*, *e-commerce platform* (Salesforce Commerce, Shopify Plus, Adobe Commerce), *order-management system* (OMS), *omnichannel*, *BOPIS*, *loyalty program* (PII-heavy), *peak / holiday freeze*, *segmentation* (PCI scope), *SAQ-A vs SAQ-D vs RoC*, *acquirer*, *card brand fine*.

**Operating model defaults.** Corporate SOC + store-IT helpdesk + e-commerce DevSecOps. Holiday freeze typically Oct 1 → Jan 15: no production changes, no tooling migrations, no exec demos that require IT bandwidth. PCI QSA engagement annual; ASV scans quarterly.

**Micro-segment slices.**
- *Specialty retailer, 200–800 stores, single-banner* — POS refresh cycle just opened.
- *Multi-banner retail holding company* — segmented per banner, shared GRC center of excellence.
- *E-commerce-first DTC brand, IPO-stage* — under SEC Item 1C cyber disclosure pressure.
- *Quick-service restaurant (QSR) chain, franchisor + franchisees* — franchisee POS variance creates a long-tail PCI-scope nightmare.

**Obstacle / workaround patterns.** Obstacle: *holiday freeze* (no change Oct–Jan) + *franchisee independence* (corporate can't mandate POS hygiene) + *PCI scope creep* (every loyalty feature pulls more systems in-scope). Workaround: a back-office PC in the stockroom running everything from PoS-management to Excel-on-USB-stick, with a credential sticky-note under the monitor.

**Sensitive-topic phrasings.** Don't say "data breach" — say *cardholder data event* or *POS incident*. Don't say "PCI fail" — say *the last QSA's RoC findings*. "How did peak go last year — what surfaced in the SOC?" lands. Cite the card brands by name only if the rep knows the prospect's acquirer relationship.

**Anchor questions (good vs bad).**
| Good | Bad |
|---|---|
| "Talk me through the last holiday peak — what did your SOC actually flag?" | "How was your Black Friday?" |
| "How are you dealing with franchisee POS hygiene today — what does the rep on store-IT actually do?" | "Do you have store-level visibility?" |
| "Where does the money for the next PCI scope reduction come from — IT, loss-prevention, or marketing?" | "Do you have budget?" |

**OSINT signals already in the harvest.** PCI Council enforcement announcements, FTC settlements, state AG breach portals, Visa/Mastercard ADC compliance announcements, SEC 10-K Item 1A, Glassdoor reviews mentioning POS/IT pain, store-opening / closure news (signals scope change), DTC-IPO S-1 cyber sections.

---

## Education (K-12 and Higher Ed)

**Operational reality.** "System availability" means *instruction continuity and FERPA-protected record integrity* — a degraded SIS during a registration window or an LMS during finals is a board-meeting-level event. K-12 is increasingly a ransomware-target sector; HigherEd has decentralized identity sprawl.

**Customer language.** *SIS* (PowerSchool, Infinite Campus, Banner, PeopleSoft Campus), *LMS* (Canvas, Blackboard, Moodle, D2L Brightspace), *IdP* (Shibboleth, Azure AD/Entra, ADFS), *InCommon federation*, *FERPA*, *COPPA* (K-12), *eduroam*, *BYOD*, *1:1 device program*, *e-rate funding* (K-12), *SLCGP cyber grant*, *State EdTech Director*, *CIPA*, *parent-portal*.

**Operating model defaults.** K-12 districts: tiny IT team (1–15 FTE) covering thousands of student devices; HigherEd: federated, each college/school runs its own IT to some degree, with a central CIO/CISO trying to mandate from above. Change windows: between semesters / breaks. Outsourced SOC common in K-12.

**Micro-segment slices.**
- *Mid-size K-12 district, 5–50 schools, Microsoft 365 EDU + Google Workspace EDU* — cyber-grant-funded modernization.
- *Regional public university, R2, 10–30k students* — federated IdM messy, FERPA Office of the Registrar paranoid.
- *R1 flagship state university* — research data classification + HIPAA in the med school + FERPA + CMMC at the engineering school.
- *Community college system, multi-campus* — under state-DoE cyber audit pressure.

**Obstacle / workaround patterns.** Obstacle: *budget cycles tied to state legislature and federal grants* + *academic-freedom culture* (resists central mandates) + *student-turnover identity churn* (40% of accounts new every August). Workaround: a delegated-admin OU per school/department, a manual Excel-to-AD script run once a semester by an intern, and shared classroom logins on Chromebook carts.

**Sensitive-topic phrasings.** Don't say "you got ransomware" — say *the August/September event* (most K-12 incidents are seasonal). Don't say "compliance gap" — say *the audit finding* or *the privacy-office inquiry*. "How did the start-of-year identity provisioning go?" lands.

**Anchor questions (good vs bad).**
| Good | Bad |
|---|---|
| "Talk me through how onboarding goes the first week of August — what does your IAM lead actually do?" | "Do you have IAM challenges?" |
| "How are you dealing with FERPA evidence requests today — who pulls the access trail?" | "Are you FERPA compliant?" |
| "Where does the money come from — district/state operational, SLCGP, e-rate, or a foundation grant?" | "Do you have budget?" |

**OSINT signals already in the harvest.** K-12 Cyber Incident Map (Doug Levin), state DoE incident notices, SLCGP awards, USAspending federal-research grants (HigherEd), institutional accreditation reviews (SACSCOC, HLC, etc.), state legislative cyber bills, parent-portal breach notices, IPEDS data on IT spend (HigherEd).

---

## Telecom

**Operational reality.** "System availability" means *network uptime and lawful-intercept readiness* — every minute of degraded service surfaces in NetOps SLAs, regulator notices, and (for carriers) FCC NORS / DIRS reportables. Identity for telco is dual: *workforce IAM* (employees, MVNO partners) plus *subscriber-IAM* (millions of consumer/business accounts).

**Customer language.** *NetOps* / *NOC*, *OSS / BSS*, *CALEA*, *SS7*, *Diameter*, *5G core / SBA*, *CNF / VNF*, *MEF*, *NORS / DIRS* (FCC outage reporting), *eCPRI / RAN / O-RAN*, *NEBS*, *SOC2 + ISO 27001*, *CTIA cyber best practices*, *carrier-grade*, *6-nines / 9-9-9-9-9-9 availability*, *peering*, *route leak / hijack*.

**Operating model defaults.** Huge 24×7 NOC + separate 24×7 SOC; NetOps and Cybersecurity historically siloed but converging under a single VP Network & Security. Long change-control cycles (carrier-grade testing requirements). MVNOs operate leaner, often outsourcing SOC and IT entirely.

**Micro-segment slices.**
- *Tier-2 regional carrier (CLEC/RLEC), Connect America Fund recipient* — under FCC cyber baseline pressure.
- *MVNO on a Tier-1 host network* — leaner SOC, dependent on host carrier for network telemetry.
- *Cable MSO with broadband + voice + mobile* — multi-product IAM sprawl across acquired businesses.
- *Tower / infra operator (no consumer subscribers)* — workforce IAM + physical-site PACS converging.

**Obstacle / workaround patterns.** Obstacle: *carrier-grade testing overhead* (any change to auth flows triggers a multi-quarter regression cycle) + *NEBS / FCC compliance bar* + *legacy OSS/BSS depth*. Workaround: a privileged-access path through a "vendor jump host" that's exempt from the regular access-review cadence because "operations needs it."

**Sensitive-topic phrasings.** Don't say "outage" — say *availability event* or *NORS-reportable*. Don't say "you got hacked" — say *the security event surfaced through the NOC*. "How does the NOC and the SOC hand off when a privileged-access alert fires at 3am?" lands.

**Anchor questions (good vs bad).**
| Good | Bad |
|---|---|
| "Talk me through the last NORS event — what did the post-mortem say about access trail?" | "Do you worry about outages?" |
| "How are you dealing with vendor jump-host accounts today — who reviews them?" | "Do you have third-party access controls?" |
| "Where does the money for IAM modernization come from — NetOps, SecOps, or a corporate IT line?" | "Do you have budget?" |

**OSINT signals already in the harvest.** FCC NORS / DIRS public filings, FCC enforcement bureau orders, CTIA Cybersecurity working-group publications, USAspending RDOF/CAF awards, SEC 10-K Item 1C for public carriers, peering-DB / BGP-leak reports referencing the org, MVNO host-carrier announcements.

---

## How to use this file in narrative composition

1. **Identify the section.** Subagent A and the parent synthesis use `company.industry`, SIC/NAICS, and `company.tags` to pick a section. If two might apply (e.g. *Hospital + Health Insurance*), pick the one whose Operational Reality is the dominant day-to-day driver.
2. **Pin the micro-segment.** Choose a slice from the section that matches the prospect's revenue / footprint / regulator status — write it verbatim into `company.micro_segment`. If none fit, write a new slice in the same who-where + one-problem shape.
3. **Stock the customer-language vocabulary.** `data.industry_operational_lens` must contain ≥2 phrases from the section's Customer Language list, or `[depth-lint] industry_language_missing` fires.
4. **Generate good questions from the templates.** Every entry in `discovery_discipline.good_questions[]` is a prospect-specific instance of one of the section's Anchor Questions — tied to a dossier fact via `demo_playbook.{ad360,log360}.discovery_anchors[i]`.
5. **Generate bad-question warnings from the bad column.** `discovery_discipline.bad_questions[]` cites why the bad-side question is generic ("anything involving the future is an over-optimistic lie", "compliments are not buying signals").
6. **Apply the obstacle/workaround pattern.** Every evidence-backed problem in `signals.positive[]` gains an `obstacle` + `workaround` pair, drawn from this section's Obstacle/Workaround paragraph and the prospect's specific evidence.
7. **Phrase sensitive topics correctly.** Outreach `recommendations.outreach.hook` and `vision`/`framing` use only the section's Sensitive-Topic Phrasings.
