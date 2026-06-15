# ELISS Intelligence Feeds — Master Source Directory

This is the curated directory of 300+ intelligence sources across 27 categories, organized by **when** to use each one during the ELISS 7-layer research protocol. Treat this as a lookup table: given which layer you're in and what you need, this file tells you which feed is the best shot.

**How to use this file:**
- Start from the layer you're currently in (Layer 1–7 from `search-playbook.md`)
- Read the "Primary feeds" for that layer and pick 2–3 based on the prospect's profile (industry, size, public/private)
- Use "Secondary feeds" only if the primary ones don't return enough signal
- Note the "Access" column: many of these are paid — if you don't have an account, fall back to public sources (marked FREE)
- **(v6.1+)** consult the **Claude Reachability Legend** immediately below to know what Claude can actually reach for each Access tier before you rely on a source in your research plan

---

## Claude Reachability Legend (v6.1+)

Every source table in this catalog has an "Access" column with one of three values: **FREE**, **FREEMIUM**, or **PAID**. That tells you how the source is licensed — but not what Claude (as the ELISS research agent) can actually *do* with it. This legend closes that gap.

| Access tier | What it means | What Claude can actually reach |
|---|---|---|
| **FREE** + web UI | No login, no API key, indexed by search engines | **Full reach.** Claude can `web_search` to discover relevant pages and `web_fetch` to retrieve full content. Cite these as Tier-A or Tier-B depending on the source's authority. |
| **FREEMIUM** | Public surface accessible without login; premium features require signup | **Partial reach.** Claude can hit the public surface via `web_fetch`. Any premium data (full search results, API access, detailed exports) requires the operator to pre-configure credentials in the runtime env. Without creds → degrade gracefully to the free surface and log the gap in `data_quality.gaps`. |
| **PAID** (API or login-gated) | Requires credentials to get any useful data | **No reach unless pre-configured.** Claude cannot authenticate on the operator's behalf. The skill supports `RR_API_KEY` (RocketReach) natively via `scripts/rocketreach_client.py` (v6.1+). For other paid sources, the operator must either (a) paste specific findings into the conversation manually, or (b) implement a similar env-var-driven client. |

**Explicit no-reach exceptions** — sources that look accessible but aren't, in Claude's operating context:

- **LinkedIn full profile detail, connections, activity feed** — visible only to logged-in users. Claude can reach public-facing portions (company page, headline, public posts) via search. Cannot read connection graph, endorsements, or private activity.
- **Glassdoor full reviews, salary data, interview questions** — preview-only without account. Search snippets may reveal reviews; full text is behind login.
- **ZoomInfo, 6sense, Apollo, Cognism, PitchBook, Bombora** — all require paid API + credentials. Claude has no reach unless the operator integrates a client script.
- **Shodan API, Censys API, SecurityTrails API, Hunter.io API** — paid tiers gate the interesting queries. Claude can only read the free-tier public reports that the search engine has indexed.
- **MXToolbox, PingCastle Azure Tenant Resolution, crt.sh, DNSDumpster, CompleteDNS** — FREE and publicly queryable. These are reliably reachable; always include them in the Mandatory Free-OSINT Checklist.
- **Shodan/Censys/ONYPHE/ZoomEye free search results** — the web version is rate-limited but indexed by Google. Claude can often find specific hosts via `web_search "target-domain" site:shodan.io` or similar.
- **Dark web sources (Tor, onion, darknet forums)** — zero reach. Claude cannot fetch `.onion` URLs. Anything in §20 that implies dark-web coverage (IntelX, DeHashed) must be accessed through the vendor's surface-web interface.
- **Real-time live-scan tools** (WiGLE wardriving map, live threat maps in §25, Shodan "on-demand scan") — Claude can view cached/indexed snapshots but cannot trigger real-time scans.

**What to do when a source is unreachable:** log it in `data_quality.sources_actually_checked[]` with `access_method: "inferred"` or skip it and note in `data_quality.gaps[]` that the source exists but wasn't queryable in this run. Do NOT fabricate source content for unreachable sources.

---

## Quick Source Index (by category)

| Category | Purpose | When to consult |
|---|---|---|
| Technographic | What tech the company runs | Layer 2 (Tech & Security Posture) |
| Intent | Who's actively researching IAM/SIEM topics | Layer 2 + Layer 7 (high-value for timing score) |
| Sales Intelligence | Contact data + company profiles | Layer 1 + Layer 5 |
| Lead Generation | Email/phone discovery, engagement tools | Layer 1 (contact enrichment only) |
| Firmographic | Company size, industry, ownership, funding | Layer 1 + Layer 4 |
| Financial | Revenue, earnings, IT spend, 10-Ks | Layer 4 |
| News & Media | Press releases, breaches, announcements | Layer 2 + Layer 3 + Layer 6 |
| Job Postings | Tech stack, hiring intent, team gaps | Layer 2 (most valuable single signal) |
| Org Chart | Decision-making unit mapping | Layer 5 |
| ABM | Account targeting platforms (for context) | Reference only — not primary research |
| CRM Enrichment | Data refresh for existing contacts | Layer 1 (if contact already in CRM) |
| Competitive | Product reviews, competitor detection | Layer 6 |
| Verification | Email/phone/data quality checks | Final step before outreach |
| **Security OSINT** (§14) | Infrastructure fingerprinting — AD, email platform, exposed services | Layer 2 + Layer 6 — invaluable for AD360/Log360 |
| **Legal & Regulatory** (§15) | Litigation, regulatory actions, patents | Layer 3 — compliance-timing signals |
| **Gov Contracts** (§16) | Federal/state/local spending + contract vehicles | Layer 4 — mandatory for Gov vertical |
| **Website Monitoring** (§17) | Historical site snapshots + change alerts | Layer 2 + Layer 6 — detect silent changes |
| **Workflow Automation** (§18) | AI extraction + scraping for scaled research | When researching >20 leads at once |
| **Partner Ecosystems** (§19) | Cloud partner directories (AWS, MS, GCP) | Layer 2 + Layer 6 for hybrid cloud prospects |
| **Breach & Leak Intelligence** (§20) | Confirmed breaches, exposed credentials, dark-web mentions | Layer 2 + Layer 3 — single highest-value Timing trigger when prospect has been hit |
| **Threat Intelligence & Reputation** (§21) | URL/IP/domain reputation, hosting infrastructure threat scoring | Layer 2 + Layer 6 — adjacent to OSINT, scores real-world risk posture |
| **Cooperative Purchasing & State AG Breach Pages** (§22) | Non-DIR cooperative contract vehicles + 50-state AG catastrophe-notice URLs | Layer 4 (procurement path) + Layer 3 (post-breach prospects) |
| **Hardware & Infrastructure Fingerprinting** (§23) | Attack-surface mapping, asset discovery, BGP/ASN intel, Wi-Fi wardriving, Azure tenant resolution | Layer 2 (critical for AD360/Log360 — direct hardware/software inference) |
| **Threat Actor Intelligence & Attribution** (§24) | Sector-specific threat actors, APT group TTPs, adversary profiles | Layer 3 (sector threat pressure narrative) + Layer 6 (competitive positioning) |
| **Live Cyber Threat Maps** (§25) | Real-time visualizations of attacks by geography/sector | Layer 3 (talking points for "your industry is under attack") |
| **Document, Legal & Court Records** (§26) | Court filings, PACER, nonprofit 990s, offshore leaks, public document archives | Layer 3 + Layer 4 — extends §15 with document-centric research paths |
| **AI Research Accelerators** (§27) | LLM-powered search engines for fast synthesis and citation discovery | All layers — force-multiplier for the analyst rather than a primary data source |

---

## Category 1 — TECHNOGRAPHIC DATA (Layer 2: Tech & Security Posture)

These feeds tell you what tech stack the company runs. This is the single biggest input to the **Tech Alignment** score (0–4 points) and a major input to displacement strategy.

### Primary feeds
| Source | URL | Access | Best for |
|---|---|---|---|
| BuiltWith | https://builtwith.com | FREE tier | Public-facing web tech (CMS, analytics, marketing stack). Weak for internal IT. |
| HG Insights | https://hginsights.com | PAID | Enterprise tech install base (AD, SIEM, VMware, databases). The best single source for AD/SIEM detection. |
| Datanyze | https://www.datanyze.com | PAID | SMB/mid-market tech stacks, especially SaaS. |
| Crustdata | https://crustdata.com | PAID | Hybrid data — technographic + hiring signals in one query. |

### Secondary feeds
| Source | URL | Access | Best for |
|---|---|---|---|
| Clearbit (HubSpot) | https://clearbit.com | FREEMIUM | Quick company → tech stack lookups from domain |
| ZoomInfo | https://www.zoominfo.com | PAID | Tech stack layer inside broader company intelligence |
| Demandbase | https://www.demandbase.com | PAID | Technographic + intent fusion for ABM |
| 6sense | https://6sense.com | PAID | Same as Demandbase; stronger intent component |
| Bombora | https://www.bombora.com | PAID | Pure intent but reveals what tech categories are being researched |
| Wappalyzer | https://wappalyzer.com | FREEMIUM | Browser extension + API — CMS, frameworks, analytics, JS libraries on any public site |
| StackShare | https://stackshare.io | FREEMIUM | Crowdsourced stacks for 60K+ companies; good for tech dev prospects who self-declare |
| WhatRuns | https://www.whatruns.com | FREE | Chrome extension — fast technology fingerprint for a prospect website |
| PredictLeads | https://predictleads.com | FREEMIUM | Technographic + job-posting fusion — 100 free API calls/month, MCP-ready |
| BuiltWith Pro | https://builtwith.com/pro | PAID | Deeper tech history + alternates tracking (paid upgrade from free tier) |

### Open-source & code-level signals
For prospects where engineering maturity matters (identifying mature DevSecOps teams who would evaluate integrated AD360+Log360 over point tools):

| Source | URL | Access | Best for |
|---|---|---|---|
| GitHub | https://github.com | FREE | Public repos, contributors, engineering team size |
| Sourcegraph | https://www.sourcegraph.com | FREEMIUM | Cross-repo code search — finds company-specific technology usage |
| Libraries.io | https://libraries.io | FREE | npm/PyPI/Maven dependency tracking — reveals language preferences |
| npm Registry | https://www.npmjs.com | FREE | Package download trends; useful for Node-heavy prospects |
| Stack Overflow | https://stackoverflow.com | FREE | Company pages + tag activity reveal engineering investments |
| Dev.to | https://dev.to | FREE | Engineering blogs — culture + tech stack signals |

### Usage pattern for AD360/Log360
Always ask these three questions in this order:
1. **AD detection?** → HG Insights or job postings mentioning "Active Directory"
2. **SIEM detected?** → HG Insights or BuiltWith (rarely — SIEMs are internal) or job postings mentioning specific SIEMs
3. **Microsoft 365 / Azure AD?** → BuiltWith often catches M365 signals

---

## Category 2 — INTENT DATA (Layer 2 + Timing Score)

Intent data reveals **who is actively researching topics related to our product categories**. This is a direct Timing-score input (Active procurement signal +20, Imminent need +16).

| Source | URL | Access | Best for |
|---|---|---|---|
| Bombora | https://www.bombora.com | PAID | Broadest intent taxonomy — look for "SIEM," "identity management," "privileged access" |
| 6sense | https://6sense.com | PAID | Intent + predictive scoring — good for buying stage estimation |
| Cognism | https://www.cognism.com | PAID | Intent + verified contacts in one platform (EU-strong) |
| Factors.ai | https://factors.ai | PAID | Website visitor intent — who's on YOUR site but hasn't filled a form |
| AI Ark | https://www.aiark.com | PAID | Emerging intent provider; lower coverage but lower cost |
| MarketJoy | https://www.marketjoy.com | PAID | Managed intent service — they hand you qualified leads |
| ZoomInfo Streaming Intent | https://www.zoominfo.com/products/streaming-intent | PAID | Intent bundled with firmographic — single pane, real-time feed |
| Amplemarket Signals | https://www.amplemarket.com/signals | PAID | Job changes + competitor-review tracking as intent signals |
| Salesmotion | https://www.salesmotion.io | PAID | Monitors 1,000+ public sources (earnings calls, executive hires, funding) |
| Intentsify | https://intentsify.io | PAID | Persona-level intent + full buying-group signal from content monitoring |
| TechTarget Priority Engine | https://www.techtarget.com/priority-engine | PAID | Tech-buyer research across 150+ tech publications — most valuable for our ICP |
| TrustRadius | https://www.trustradius.com | FREEMIUM | Downstream intent — prospect behavior on their review platform |
| NetLine INTENTIVE | https://www.netline.com/intentive | PAID | Person-level intent (who inside an account engaged with what content) |
| Coresignal | https://www.coresignal.com | PAID | Fresh firmographic + job posting data; API-first, LLM-friendly |
| Warmly | https://www.warmly.ai | FREEMIUM | Website visitor ID + composite buying-signal alerts |
| KickFire | https://www.kickfire.com | PAID | IP-to-company reverse lookup — de-anonymize anonymous web traffic |
| Albacross | https://www.albacross.com | PAID | GDPR-compliant website visitor ID (EU-focused; Dealfront ecosystem) |

**Key intent keywords to look for** for AD360/Log360:
- "Active Directory management," "identity governance," "privileged access management"
- "SIEM," "log management," "UEBA," "security information event management"
- "SOX compliance," "HIPAA compliance," "PCI-DSS audit"
- "zero trust," "identity-first security"

A prospect spiking on **3+ of these topics in the last 30 days** → strong Intent signal (+10 to +15 depending on triangulation).

---

## Category 3 — SALES INTELLIGENCE PLATFORMS (Layer 1 + Layer 5)

One-stop platforms for company + contact + some tech data.

| Source | URL | Access | Best for |
|---|---|---|---|
| ZoomInfo | https://www.zoominfo.com | PAID | Deepest US contact coverage; strong firmographics |
| Apollo.io | https://www.apollo.io | FREEMIUM | Best free tier for contact discovery; decent data quality |
| Cognism | https://www.cognism.com | PAID | EU/GDPR-compliant contact data (use this for EU prospects) |
| Clearbit | https://clearbit.com | FREEMIUM | API-first; great for domain → company lookups |
| MarketJoy | https://www.marketjoy.com | PAID | Managed outreach service; use only as fallback |
| Demandbase | https://www.demandbase.com | PAID | Account-based focus (not individual leads) |
| LeadIQ | https://leadiq.com | FREEMIUM | Real-time job-change alerts + ICP prospecting; CRM sync (SFDC/HubSpot) |
| UpLead | https://www.uplead.com | FREEMIUM | 95%+ accuracy guarantee; 50+ search filters; bounce credits |
| Lead411 | https://www.lead411.com | PAID | Unlimited-access plans; Bombora intent integration |
| Prospeo | https://prospeo.io | FREEMIUM | 143M+ verified emails; Chrome extension; API + MCP |
| LeadsRx | https://www.leadsrx.com | PAID | Multi-touch attribution across digital touchpoints |
| Breadcrumbs | https://www.breadcrumbs.io | PAID | Co-dynamic lead scoring (firmographic + behavioral + intent) |

**Triangulation rule:** If you have access to two of these, cross-reference employee counts and revenue estimates. Disagreements >20% → mark confidence MEDIUM.

---

## Category 4 — LEAD GENERATION TOOLS (Layer 1, contact enrichment only)

Use these **after** you've identified the right prospect — for finding email + phone.

| Source | URL | Access | Best for |
|---|---|---|---|
| Salesforce Marketing Cloud | https://www.salesforce.com/marketing/ | PAID | Marketing automation + lead scoring (inbound) |
| HubSpot | https://www.hubspot.com | FREEMIUM | CRM + lead scoring (inbound) |
| Apollo.io | https://www.apollo.io | FREEMIUM | Email + phone at scale |
| LinkedIn Sales Navigator | https://business.linkedin.com/sales-solutions/sales-navigator | PAID | Verified titles + warm intro paths |
| Lusha | https://www.lusha.com | FREEMIUM | Fast email/phone lookup, Chrome extension |
| Cognism | https://www.cognism.com | PAID | GDPR-compliant contact data |
| Seamless.AI | https://www.seamless.ai | PAID | High-volume email discovery |
| Hunter.io | https://hunter.io | FREEMIUM | Email pattern detection from domain |
| Leadfeeder (Dealfront) | https://www.dealfront.com | PAID | Website visitor identification |
| Drift | https://www.drift.com | PAID | Conversational marketing (live chat intent) |
| Intercom | https://www.intercom.com | PAID | Engagement + chat-based lead capture |

**Priority order for contact discovery:** LinkedIn Sales Navigator → Apollo.io → Lusha/Hunter → ZoomInfo.

### Email discovery specialists (lighter-weight alternatives)
| Source | URL | Access | Best for |
|---|---|---|---|
| Snov.io | https://www.snov.io | FREEMIUM | Email finder + verifier + drip campaigns |
| Voila Norbert | https://www.voilanorbert.com | FREEMIUM | Bulk email finder with accuracy guarantee |
| FindThatLead | https://www.findthatlead.com | FREEMIUM | Email + domain search + LinkedIn extraction |
| Skrapp.io | https://www.skrapp.io | FREEMIUM | LinkedIn email extractor (Chrome extension) |
| Anymail Finder | https://www.anymailfinder.com | PAID | Name+domain lookup with real-time verification |
| EmailRep.io | https://emailrep.io | FREE | Reputation check before sending outreach |

---

## Category 5 — FIRMOGRAPHIC & COMPANY RESEARCH (Layer 1 + Layer 4)

Baseline facts about the company — size, industry, ownership, funding, reviews.

| Source | URL | Access | Best for |
|---|---|---|---|
| D&B Hoovers | https://www.dnb.com/duns-number/get-a-duns.html | PAID | Authoritative firmographic data (D-U-N-S numbers, hierarchy) |
| ZoomInfo | https://www.zoominfo.com | PAID | Rich company profiles with departmental headcount |
| Crunchbase | https://www.crunchbase.com | FREEMIUM | Funding history, founder info, acquisitions (tech-heavy) |
| PitchBook | https://pitchbook.com | PAID | Private company data, PE/VC ownership, valuations |
| Owler | https://www.owler.com | FREEMIUM | Community-sourced estimates + competitor lists |
| LinkedIn Company Pages | https://www.linkedin.com/company/ | FREE | Employee count, recent hires/departures, growth trend |
| Glassdoor | https://www.glassdoor.com | FREE | Employee reviews, culture signals, leadership ratings |
| Comparably | https://www.comparably.com | FREE | Similar to Glassdoor; often has different sample |
| eCommerceDB | https://www.ecommercedb.com | PAID | E-commerce-specific revenue estimates |
| CB Insights | https://www.cbinsights.com | PAID | Startup/tech trend intelligence; funding, M&A, market maps |
| Tracxn | https://www.tracxn.com | PAID | Startup + sector intelligence (strong APAC coverage) |
| Growjo | https://www.growjo.com | FREEMIUM | "Fastest-growing companies" rankings; employee + revenue growth signals |
| Blind (Teamblind) | https://teamblind.com | FREE | Anonymous employee sentiment — cultural health, insider perspectives |
| Fishbowl | https://www.fishbowlapp.com | FREEMIUM | Verified-professional industry discussions (competitor intel from employees) |

### Corporate registries (official records — authoritative for legal name, officers, filings)
| Source | URL | Access | Geographic scope |
|---|---|---|---|
| OpenCorporates | https://opencorporates.com | FREEMIUM | 200M+ companies across 140 jurisdictions — start here for EU/UK/global |
| UK Companies House | https://find-and-update.company-information.service.gov.uk | FREE | Authoritative UK company filings, officer records, financials |
| SEC EDGAR Full-Text | https://www.sec.gov/edgar/search | FREE | Full-text search across all US SEC filings |
| DomainTools | https://www.domaintools.com | PAID | WHOIS history, reverse IP lookup, domain profiling |

### Local government intelligence (v5.7+ — for municipal / county / school district prospects)
For public-sector ICP, the firmographic-equivalent intelligence lives in different places. These sources expose city budgets, council agendas, recent leadership changes, and procurement vehicles in a way commercial firmographic tools entirely miss.

| Source | URL | Access | Best for |
|---|---|---|---|
| Granicus / Legistar | https://www.granicus.com (and individual `<city>.legistar.com` deployments) | FREE | City council agenda + minutes search — finds procurement items, vendor selections, budget transfers by keyword |
| CivicEngage / CivicPlus | https://www.civicplus.com | FREE | The CMS most US cities use; detection signals municipal IT vendor relationships |
| OpenGov | https://opengov.com | FREE (public portals) | City budget transparency portals — line-item IT/security spend |
| Texas Municipal League (TML) Directory | https://directory.tml.org | FREE | Authoritative directory of all 1,200+ Texas cities with mayor/manager/budget contacts |
| GFOA Awards Database | https://www.gfoa.org/awards | FREE | Distinguished Budget Presentation winners — signals fiscal-discipline-mature cities (good ICP indicator) |
| NACo (National Association of Counties) | https://www.naco.org | FREE | County-level peer benchmarking, leadership directory |
| NLC (National League of Cities) | https://www.nlc.org | FREE | City-level peer benchmarking + leadership |
| GovDelivery / Granicus Comms | https://granicus.com/solution/govdelivery | FREE | Tracks city press release patterns (RSS feeds) — early signal on leadership announcements + cyber incidents |
| ICMA (City/County Management Association) | https://icma.org | FREEMIUM | City Manager directory + tenure tracking — manager turnover = budget reset window |
| Texas Association of Government IT Managers (TAGITM) | https://tagitm.org | FREE | TX municipal IT director community — useful for warm-intro paths and conference attendance |
| ELGL (Engaging Local Government Leaders) | https://elgl.org | FREE | Modern local-government practitioner network; podcast/Slack signals for individual prospects |
| MuniNet Guide | https://www.muninetguide.com | FREE | Curated municipal data + news aggregator |

**Public-sector usage pattern:**
1. Identify city → check **TML Directory / NACo / NLC** for confirmed leadership + size + budget bracket
2. Search **Legistar / Granicus** at `<city>.legistar.com` for "security," "SIEM," "Active Directory," "Microsoft" agenda items in the last 24 months — confirms procurement intent
3. Pull **OpenGov budget portal** if available, or city's PDF budget — security-budget line items are often itemized
4. Cross-check **GFOA awards** for fiscal sophistication signal (Coppell has 15 consecutive years of Distinguished Budget Award)

**Employee count triangulation:** LinkedIn + Glassdoor + (D&B or ZoomInfo). If all three agree within ±10%, HIGH confidence. For public sector: TML/NACo + city-published staffing numbers + LinkedIn = HIGH confidence.

---

## Category 6 — FINANCIAL & EARNINGS (Layer 4, public companies)

For **public companies only**. For private, skip to Crunchbase/PitchBook.

| Source | URL | Access | Best for |
|---|---|---|---|
| SEC EDGAR | https://www.sec.gov/cgi-bin/browse-edgar | FREE | 10-K, 10-Q, 8-K filings — the primary source |
| LSEG Eikon / Datastream | https://www.lseg.com/en/data-analytics | PAID | Real-time financial data + analyst estimates |
| Seeking Alpha | https://seekingalpha.com | FREEMIUM | Earnings call transcripts, analyst commentary |
| Yahoo Finance | https://finance.yahoo.com | FREE | Quick financial snapshots, insider transactions |
| Capital IQ (S&P Global) | https://www.spglobal.com/marketintelligence/en/ | PAID | Institutional-grade financial data |
| Bloomberg Terminal | https://www.bloomberg.com/professional/solutions/bloombergterminal/ | PAID | Bloomberg — if you have access, this is the gold standard |
| Macrotrends | https://www.macrotrends.net | FREE | Historical financials, valuations, revenue trends |
| StockAnalysis.com | https://stockanalysis.com | FREE | Earnings, estimates, analyst sentiment for US public cos |
| GuruFocus | https://gurufocus.com | FREEMIUM | Fundamental health + valuation metrics |
| Simply Wall St | https://simplywall.st | FREEMIUM | Visual financial health snapshots (quick qualification) |
| OpenInsider | https://openinsider.com | FREE | SEC Form 4 insider trading tracker — executive-confidence signal |
| WhaleWisdom | https://whalewisdom.com | FREEMIUM | 13F institutional holdings — fund confidence + ownership changes |
| Morningstar | https://www.morningstar.com | FREEMIUM | Research + star ratings; useful for mutual-fund-dominated ownership |

### SaaS & private-company benchmarks (for Layer 4 when no 10-K exists)
| Source | URL | Access | Best for |
|---|---|---|---|
| GetLatka | https://www.getlatka.com | FREEMIUM | CEO-reported SaaS revenue/ARR/growth database |
| Tom Tunguz Blog | https://tomtunguz.com | FREE | SaaS benchmarks from Theory Ventures; ARR, churn, growth patterns |
| IndieHackers | https://www.indiehackers.com | FREE | SMB/founder-reported revenue (only for SMB prospects) |
| Ben Evans | https://ben-evans.com | FREE | Macro tech market analysis — timing + platform dynamics |

**Search 10-Ks for these specific phrases** to extract IT-relevant signals:
- `"information technology" AND "spending"` or `"IT investments"`
- `"cybersecurity"` — SEC now requires cybersecurity disclosure; these sections reveal security maturity
- `"material weakness"` — red flag suggesting audit pressure (trigger event)
- `"data breach"` or `"security incident"` — explicit breach disclosures

---

## Category 7 — NEWS, MEDIA & PRESS (Layer 2, 3, 6)

Time-sensitive signals — breaches, tech announcements, leadership changes, funding.

| Source | URL | Access | Best for |
|---|---|---|---|
| Factiva (Dow Jones) | https://www.dowjones.com/professional/factiva/ | PAID | Professional-grade news archive; great for historical context |
| Google Alerts | https://www.google.com/alerts | FREE | Set ongoing alerts for named prospects — single best free monitoring tool |
| Mention | https://mention.com | FREEMIUM | Multi-channel mention monitoring (web + social) |
| Meltwater | https://www.meltwater.com | PAID | Enterprise media monitoring + sentiment |
| TechCrunch | https://techcrunch.com | FREE | Tech-sector fundraising, launches, M&A |
| Crunchbase News | https://news.crunchbase.com | FREE | Funding announcements digest |
| PR Newswire | https://www.prnewswire.com | FREE | Official company press releases (US-focused) |
| Business Wire | https://www.businesswire.com | FREE | Official company press releases (global) |
| The Information | https://www.theinformation.com | PAID | Deep investigative reporting — executive-level intelligence, M&A signals |
| SaaStr | https://www.saastr.com | FREE | SaaS industry trends, funding rounds, growth benchmarks |
| BetaKit | https://www.betakit.com | FREE | Canadian startup + AI innovation coverage |
| GeekWire | https://www.geekwire.com | FREE | Pacific NW tech (Amazon, Microsoft, regional startups) |
| Sifted | https://sifted.eu | FREEMIUM | European startup news (FT-backed) |
| Hacker News | https://news.ycombinator.com | FREE | Early adoption signals; developer sentiment |
| Product Hunt | https://www.producthunt.com | FREE | New tool launches; adoption signals |
| Feedly | https://www.feedly.com | FREEMIUM | RSS/topic monitoring for automated competitor tracking |
| Stratechery | https://stratechery.com | FREEMIUM | Ben Thompson's strategic analysis — platform dynamics |
| Brand24 | https://brand24.com | FREEMIUM | Real-time mentions across 25M+ sources (social, news, reviews, forums) |

### Competitive/SEO intelligence (for understanding market position, ad spend, content strategy)
| Source | URL | Access | Best for |
|---|---|---|---|
| SpyFu | https://www.spyfu.com | FREEMIUM | Competitive PPC keywords + ad budget estimates |
| SEMrush | https://www.semrush.com | PAID | Full competitive digital footprint (traffic, keywords, backlinks) |
| Ahrefs | https://ahrefs.com | PAID | Backlink analysis + content gap discovery |
| Moz | https://www.moz.com | FREEMIUM | Domain Authority scoring — quick strength check |
| BuzzSumo | https://www.buzzsumo.com | PAID | Top-performing content + brand mention monitoring |
| Mangools | https://www.mangools.com | FREEMIUM | Affordable SEO suite (KWFinder, SERPWatcher) |
| Social Blade | https://www.socialblade.com | FREE | Social media growth analytics — content strategy signals |

**High-value keyword searches** (run these for every prospect):
- `"[company]" breach OR ransomware OR attack 2024..2026` → security incident check
- `"[company]" CISO OR CIO appointed OR "joins as"` → leadership changes (new leaders often reevaluate tools)
- `"[company]" acquired OR merger` → M&A = integration need = AD/SIEM trigger

---

## Category 8 — JOB POSTINGS (Layer 2, highest-value single feed)

**Job postings are the single most valuable source for tech stack + intent detection**. They reveal what tools a company runs *before* any press release does, and hiring roles signal priorities.

| Source | URL | Access | Best for |
|---|---|---|---|
| LinkedIn Jobs | https://www.linkedin.com/jobs/ | FREE | Largest volume, most detail in descriptions |
| Indeed | https://www.indeed.com | FREE | Broader coverage including smaller companies |
| Crustdata | https://crustdata.com | PAID | Aggregated job data with historical trends |
| Glassdoor | https://www.glassdoor.com | FREE | Overlaps with Indeed; useful for salary context |
| Greenhouse public boards | https://www.greenhouse.io | FREE | Many enterprises use Greenhouse — direct company-hosted job boards |
| Lever public boards | https://www.lever.co | FREE | Alternative ATS — same approach as Greenhouse boards |
| Wellfound (AngelList Talent) | https://www.wellfound.com | FREE | Startup roles + equity data (use only for Series A+ prospects) |
| ZipRecruiter | https://www.ziprecruiter.com | FREE | Broad coverage + salary benchmarking |
| Remotive | https://remotive.com | FREE | Remote-first companies — distributed hiring patterns |
| levels.fyi | https://www.levelsfyi.com | FREE | Compensation by company/level — budget health indicator |
| Welcome to the Jungle | https://www.welcometothejungle.com | FREE | EU tech roles — culture profiles + team insights |

### Job-posting query patterns for AD360/Log360
```
site:linkedin.com/jobs "[company]" ("Active Directory" OR "Azure AD" OR "Entra ID")
site:linkedin.com/jobs "[company]" ("SIEM" OR "SOC analyst" OR "Splunk" OR "QRadar" OR "Sentinel")
site:linkedin.com/jobs "[company]" ("compliance" OR "audit" OR "SOX" OR "HIPAA")
site:indeed.com "[company]" CISO OR "Chief Information Security Officer"
```

### What postings tell you (and how to score)
| Posting type | Intent score boost | Why |
|---|---|---|
| "Hiring CISO / Head of Security" | +6 to +10 | New security leader often triggers tool reevaluation |
| "SIEM engineer" / "Splunk admin" | +6 | Confirms SIEM in use (displacement opp) |
| "AD/Identity admin" (multiple open roles) | +6 | AD team stretched thin → AD360 automation pitch |
| "Compliance analyst" / "Auditor" | +4 | Compliance pressure confirmed |
| "Cloud security architect" | +3 | Cloud migration → Log360 cloud monitoring angle |

---

## Category 9 — ORG CHART & DECISION-MAKER MAPPING (Layer 5)

For mapping the decision-making unit beyond the primary contact.

| Source | URL | Access | Best for |
|---|---|---|---|
| LinkedIn Sales Navigator | https://business.linkedin.com/sales-solutions/sales-navigator | PAID | Best single tool — filter by title + company + team |
| ZoomInfo Org Charts | https://www.zoominfo.com | PAID | Pre-built reporting hierarchies |
| Apollo.io | https://www.apollo.io | FREEMIUM | Free-tier access to org structure |
| Cognism | https://www.cognism.com | PAID | Strong in EU orgs |
| Lusha | https://www.lusha.com | FREEMIUM | Quick lookups for specific roles |
| RocketReach | https://rocketreach.co | FREEMIUM | Phone/email for C-suite specifically |

### DMU mapping checklist for every ELISS dossier
Find at least **2–3 people** from this list:
- [ ] CIO or CTO (economic buyer, strategic)
- [ ] CISO or VP Security (economic buyer, security-specific)
- [ ] IT Director / Security Director (technical evaluator)
- [ ] IT Manager / Security Manager (day-to-day user, often champion)
- [ ] CFO or VP Finance (budget approval, >$50K deals)
- [ ] Compliance Officer (champion for regulated industries)

---

## Category 10 — ABM PLATFORMS (reference only)

These are platforms our sales team might use to *run* ABM campaigns — not research sources. Listed for completeness.

| Source | URL | Notes |
|---|---|---|
| Demandbase | https://www.demandbase.com | Full ABM platform |
| 6sense | https://6sense.com | ABM + predictive |
| Terminus | https://terminus.com | Multi-channel ABM |
| RollWorks | https://rollworks.com | Mid-market ABM |
| Triblio | https://www.triblio.com | Acquired by Foundry; ABM orchestration |

---

## Category 11 — CRM ENRICHMENT (Layer 1 if contact already in CRM)

| Source | URL | Best for |
|---|---|---|
| Clearbit | https://clearbit.com | Real-time enrichment as records are created |
| ZoomInfo + Salesforce | https://www.zoominfo.com | Bulk enrichment inside SFDC |
| Apollo.io | https://www.apollo.io | Free-tier enrichment for small teams |
| Cognism | https://www.cognism.com | GDPR-compliant enrichment |
| Clay | https://www.clay.com | Waterfall enrichment across multiple providers |
| Derrick App | https://derrickapp.com | Lightweight Gmail-based enrichment |

---

## Category 12 — COMPETITIVE INTELLIGENCE (Layer 6)

| Source | URL | Best for |
|---|---|---|
| G2 | https://www.g2.com | User reviews of specific products — look for reviewer company names to detect competitor installs |
| Gartner Peer Insights | https://www.gartner.com/reviews/ | Enterprise-oriented reviews |
| TrustRadius | https://www.trustradius.com | Detailed reviews with use cases |
| Capterra | https://www.capterra.com | SMB-focused reviews |
| Owler | https://www.owler.com | Competitor mapping, news mentions |
| SimilarWeb | https://www.similarweb.com | Website traffic + tech signals |
| Software Advice | https://www.softwareadvice.com | Software comparison platform — buyer research signals |
| PeerSpot | https://www.peerspot.com | Enterprise-focused reviews (formerly IT Central Station) — best for AD360/Log360 competitor detection |
| G2 Track | https://www.g2.com/products/track | SaaS spend intelligence — vendor switching + shadow IT discovery |
| AlternativeTo | https://alternativeto.net | Crowdsourced software alternatives — displacement opportunity discovery |

### Competitive detection tactics
On G2/Gartner review pages for competitors (Splunk, SailPoint, CyberArk, Okta, etc.):
1. Filter reviews by reviewer's company size + industry matching our prospect
2. Search review text for prospect's company name directly
3. Look for "Reviewer from [prospect company]" in reviewer profiles (sometimes visible)

A **named positive review of a competitor by our prospect** = confirmed installed base (strong displacement signal). A **named negative review** = even stronger (displacement with pain).

---

## Category 13 — VERIFICATION & COMPLIANCE (final step)

Before any outreach, validate emails to avoid bouncing and damaging sender reputation.

| Source | URL | Best for |
|---|---|---|
| Cognism | https://www.cognism.com | GDPR compliance built in |
| ZeroBounce | https://www.zerobounce.net | Email validation + abuse/spam trap detection |
| NeverBounce | https://neverbounce.com | Bulk email verification |
| BriteVerify | https://www.briteverify.com | Real-time email + phone verification |
| ZoomInfo Compliance | https://www.zoominfo.com | Data compliance (GDPR, CCPA) layer |

---

## Category 14 — SECURITY & INFRASTRUCTURE OSINT (Layer 2 + Layer 6)

**Uniquely valuable for AD360/Log360 prospecting.** These tools let you fingerprint a target's infrastructure without ever sending a message — reveal AD controllers, email platforms, SSL certificate patterns, and exposed services. Critical for post-breach prospects (like City of Coppell) where you can validate the incident and current posture.

| Source | URL | Access | Best for |
|---|---|---|---|
| Shodan | https://shodan.io | FREEMIUM | Internet-facing devices/services — find exposed AD, RDP, VPN, IoT |
| Censys | https://censys.io | FREEMIUM | Internet-wide scanning + certificate transparency — attack surface view |
| SecurityTrails | https://securitytrails.com | FREEMIUM | Historical DNS records — detect infrastructure migrations (SIEM-relevant) |
| crt.sh | https://crt.sh | FREE | SSL certificate transparency log — discover subdomains + cert lifecycle |
| VirusTotal | https://www.virustotal.com | FREEMIUM | 70+ security vendor aggregate — domain reputation check |
| Netcraft | https://netcraft.com | PAID | Web server infrastructure + SSL/hosting analysis at scale |
| ViewDNS.info | https://viewdns.info | FREE | Reverse DNS, WHOIS, DNS propagation, IP location lookups |
| MXToolbox | https://mxtoolbox.com | FREEMIUM | **MX record lookup — fingerprints email infrastructure (Google Workspace vs. Microsoft Exchange vs. on-prem)** — this tells you Microsoft shop quickly |
| Statuspage (Atlassian) | https://statuspage.io | FREE | Many companies publish — reveals their actual service dependencies |
| **DNSDumpster** | https://dnsdumpster.com | FREE | Fast host discovery for a domain — companion to crt.sh |
| **DNSViz** | http://dnsviz.net | FREE | DNS configuration visualizer (DNSSEC analysis — signals mature infra) |
| **intoDNS** | http://www.intodns.com | FREE | Domain DNS health check |
| **Icann Lookup** | https://lookup.icann.org/en/lookup | FREE | Official ICANN WHOIS — authoritative |
| **Robtex** | https://www.robtex.com | FREE | Reverse DNS, WHOIS, AS macros — infrastructure graphing |
| **Domain Dossier** | http://centralops.net/co/DomainDossier.aspx | FREE | All-in-one domain lookup toolkit |
| **SubDomainRadar.io** | https://subdomainradar.io | FREEMIUM | Fast subdomain enumeration with real-time notifications |
| **DomainRecon** | https://kriztalz.sh/domain-recon/ | FREE | DNS + subdomains + SSL certs + WHOIS/RDAP in one query |
| **DNS History (CompleteDNS)** | https://completedns.com/dns-history/ | FREEMIUM | Historical DNS records — detect infrastructure migrations |
| **Validin** | https://app.validin.com | FREE | Free current and historical DNS record search |
| **Web-Check** | https://web-check.as93.net/ | FREE | All-in-one viewer of website + server meta data — OSS |
| **Webscout** | https://webscout.io/ | FREEMIUM | IP + domain metadata at scale — Swiss Army knife |
| **TinyScan** | https://www.tiny-scan.com | FREEMIUM | URL scan → IP, location, tech stack, performance metrics |

### What these reveal for AD360/Log360 positioning
- **MXToolbox** → `mx:[prospect_domain]` returns MX records. `outlook.com` or `protection.outlook.com` = Microsoft 365 shop = AD360 fit. `google.com` = Google Workspace = lower AD dependency but still possible hybrid. `mimecast.com` / `proofpoint.com` = enterprise email security already in place.
- **crt.sh** → `crt.sh/?q=[domain]` lists issued certs. Many `.corp.[domain]` or `vpn.[domain]` subdomains = complex internal infrastructure. Recent cert for `adfs.[domain]` confirms AD Federation Services.
- **Shodan** → `org:"[company name]"` reveals exposed services. Open RDP ports or LDAP on the internet = major security posture signal (and AD360 / Log360 hardening pitch).
- **Netcraft** → `site:[domain]` shows hosting provider history. Recent migration to Azure or AWS = cloud transformation = Log360 cloud monitoring angle.
- **DNSDumpster + SubDomainRadar + DomainRecon** → layer together to enumerate full attack surface quickly. Subdomains like `jira.*`, `confluence.*`, `sharepoint.*`, `workday.*`, `servicenow.*`, `splunk.*` are gold — direct technographic signals.
- **DNS History** → compare current DNS records against 6-12 months ago to detect SIEM migration (e.g., new `siem.*` subdomain appearing indicates deployment window).

**Ethical guardrails:** All of these query **publicly available** infrastructure data. Do NOT use them to probe or scan — they show what's already indexed by legitimate crawlers. Cite as `crt.sh` or `Shodan public index`, not "we scanned you."

---

## Category 15 — LEGAL, LITIGATION & REGULATORY INTELLIGENCE (Layer 3)

Compliance pressure is the #1 trigger for AD360/Log360 purchases. Legal filings tell you when a prospect is *under* pressure — pending litigation, regulatory actions, patent disputes — all strong compliance-timing signals.

| Source | URL | Access | Best for |
|---|---|---|---|
| CourtListener | https://www.courtlistener.com | FREE | **Free PACER alternative** — federal court filings + RECAP archive |
| PACER | https://www.pacer.uscourts.gov | PAID-per-page | Official US federal court system (authoritative but fee per doc) |
| Federal Register | https://www.federalregister.gov | FREE | Daily federal agency rules + proposed regulations |
| Google Patents | https://patents.google.com | FREE | Full-text patent search — R&D direction signals for technical prospects |
| Espacenet (EPO) | https://worldwide.espacenet.com | FREE | 150M+ patents worldwide — international innovation trajectory |
| Texas AG Catastrophe Notices | https://www.texasattorneygeneral.gov/open-government/governmental-bodies/catastrophe-notice | FREE | TX state-level breach notices (example: confirmed Coppell breach) — check analogous state AG pages |

### How to use for ELISS scoring
- **Active breach-related litigation against prospect** → +10 Intent (compliance need) + timing boost (Imminent)
- **Patent filings around identity/security** → signals internal R&D — possible build-vs-buy consideration (blocker)
- **SEC cybersecurity disclosures** in a 10-K "Risk Factors" section → +5 Intent (board-level security concern)
- **State AG data-breach notices** for prospect → equivalent to SEC cyber disclosure for private/public-sector prospects

---

## Category 16 — GOVERNMENT CONTRACTS & PUBLIC SECTOR SPENDING (Layer 4 — Gov vertical only)

Essential for our Government vertical. These are the mandatory feeds when prospecting federal/state/local agencies.

| Source | URL | Access | Best for |
|---|---|---|---|
| SAM.gov | https://www.sam.gov | FREE | **Federal contract opportunities + entity registration + awards** |
| USAspending.gov | https://www.usaspending.gov | FREE | All federal spending by agency/contractor/category/location |
| Texas DIR | https://dir.texas.gov/contracts | FREE | TX state government cooperative contracts (ManageEngine is DIR-listed) |
| GovWin IQ (Deltek) | https://iq.govwin.com | PAID | Federal/state/local bid intelligence (deep contract pipeline) |
| GSA eLibrary | https://www.gsaelibrary.gsa.gov | FREE | GSA Schedule contracts — verify vendor pricing + availability |

### Why this matters for AD360/Log360 Gov deals
- **USAspending** → search prospect agency name → reveals IT spending patterns, prior security vendors, contract vehicle preferences. A government prospect with a $2M prior Splunk contract = known displacement target.
- **SAM.gov** → check prospect's entity registration + FY-specific procurement calendar. If they're registered as an agency buyer, they can use DIR cooperative purchasing.
- **Texas DIR** → specifically for TX municipal/state prospects. ManageEngine is on the DIR contract vehicle, which bypasses RFP — 60-90 day procurement instead of 6+ months.

---

## Category 17 — WEBSITE MONITORING & HISTORICAL INTELLIGENCE (Layer 2 + Layer 6)

Track change over time — pricing updates, careers page additions, feature launches, leadership bios.

| Source | URL | Access | Best for |
|---|---|---|---|
| Wayback Machine | https://web.archive.org | FREE | **25+ years of historical snapshots** — reconstruct how a company evolved |
| Visualping | https://visualping.io | FREEMIUM | Automated change alerts for tracked page elements |
| Distill.io | https://www.distill.io | FREEMIUM | Browser extension — monitor specific page regions with alerts |

### Use pattern
- Archive a prospect's careers page TODAY (`web.archive.org/save/[url]`) and compare to snapshots 6-12 months ago. A 3x increase in security roles = clear hiring trend.
- Visualping on a competitor's pricing page = know when they change pricing (and your prospect may be re-evaluating).
- Distill.io on the prospect's leadership page = real-time notice when a new CISO/CIO is announced.

---

## Category 18 — WORKFLOW AUTOMATION & AI EXTRACTION (for scaled research)

When doing >20 leads at once, these tools move the research from manual to programmatic.

| Source | URL | Access | Best for |
|---|---|---|---|
| Diffbot | https://www.diffbot.com | PAID | AI web extraction — structured data from any page automatically |
| Apify | https://www.apify.com | FREEMIUM | Web scraping platform with pre-built actors (LinkedIn, Google, etc.) |
| Clay | https://www.clay.com | PAID | Waterfall enrichment across multiple providers (best for bulk) |

**Caveat:** Stay within each platform's ToS. Respect robots.txt. Never scrape content that requires login or bypasses rate limits — the ethical line for ELISS is "would this prospect be comfortable knowing we collected this?" If no, skip.

---

## Category 19 — PARTNER ECOSYSTEMS (Layer 2 / Layer 6 for cloud prospects)

For prospects in cloud migration — partner directories reveal their ecosystem positioning.

| Source | URL | Access | Best for |
|---|---|---|---|
| AWS Partner Network | https://partners.amazonaws.com | FREE | AWS partners with tiers + competencies |
| Microsoft Partner | https://partner.microsoft.com | FREE | Microsoft AI Cloud Partner Program — competency verification |
| Google Cloud Partners | https://cloud.google.com/partners | FREE | GCP partner directory with specialization tiers |

### Signal interpretation
- Prospect listed as **Microsoft Gold Partner** → heavy MS ecosystem investment → AD360 (deep M365 integration) is a natural fit
- Prospect listed as **AWS Advanced tier** → hybrid cloud → Log360's multi-cloud support advantage over Sentinel
- **No cloud partnership** → often on-prem / hybrid → perfect AD360 ICP (our strongest value prop)

---

## Category 20 — BREACH & LEAK INTELLIGENCE (Layer 2 + Layer 3) [v5.7+]

The single highest-value Timing trigger when a prospect has been hit. Direct evidence of a breach (or exposed credentials in a third-party leak) drives the **post-breach remediation** trigger to Strong-or-Imminent. Always check these sources for any prospect with a confirmed incident OR for any high-priority prospect to surface incidents the public press never covered.

| Source | URL | Access | Best for |
|---|---|---|---|
| HaveIBeenPwned | https://haveibeenpwned.com | FREE (API: paid) | Single-domain breach exposure check — confirms if employee emails appeared in any known data leak |
| **XposedOrNot** | https://xposedornot.com | FREE (public endpoints; domain-org summary requires free signup) | Email/domain breach lookup + yearly-trend analytics + industry-classification breakdown. **Also API-integrated in `scripts/preflight.py` (v7.4.2+)** — domain breach catalog always runs (no key); when `--lead-email` is supplied, per-email breach check + analytics run too. All free public endpoints; rate-limited 1 req/sec. |
| HIBP Domain Search | https://haveibeenpwned.com/DomainSearch | FREE (verified ownership) | Bulk view of all breached emails on a verified domain — only works if you control the domain |
| BreachDirectory | https://breachdirectory.org | FREEMIUM | Aggregator of public breach datasets — searchable by email/domain |
| DeHashed | https://dehashed.com | PAID | Comprehensive leak/breach search; includes hashed credentials, often surfaces unreported incidents |
| Intelligence X (IntelX) | https://intelx.io | FREEMIUM | Leak archive + dark-web index; searches Tor mirrors + paste sites for prospect-domain mentions |
| LeakIX | https://leakix.net | FREEMIUM | Open services + leaked databases scanner — finds unsecured Elasticsearch/MongoDB/etc. |
| Ransomware.live | https://www.ransomware.live | FREE | Real-time tracker of ransomware victim claims — searchable by victim org name |
| Ransom-DB | https://www.ransom-db.com | FREE | Ransomware leak-site monitoring; cross-reference to confirm group claims |
| The Record by Recorded Future | https://therecord.media | FREE | Highest-quality cybersecurity journalism — primary source for confirming/contextualizing incidents (RansomHub Coppell story originated here) |
| Comparitech Breach Tracker | https://www.comparitech.com/blog/information-security/data-breaches-2024 | FREE | Independent counter of breach impact + victim communications |
| BleepingComputer | https://www.bleepingcomputer.com | FREE | Tactical incident reporting + IOC details |
| DataBreaches.net | https://www.databreaches.net | FREE | Long-running aggregator of US breach disclosures |
| Krebs on Security | https://krebsonsecurity.com | FREE | Investigative cybersecurity reporting — strong on supply-chain + financial-sector incidents |
| HHS Breach Portal | https://ocrportal.hhs.gov/ocr/breach/breach_report.jsf | FREE | **Authoritative US HIPAA breach registry** — required reporting for any healthcare PHI breach affecting 500+ individuals |
| **Hudson Rock** | https://www.hudsonrock.com/threat-intelligence-cybercrime-tools | FREEMIUM | **Infostealer infection check — flags if ANY prospect-domain email shows up in stealer-log archives.** Often surfaces quiet incidents never publicly disclosed. MAJOR for post-breach selling. |
| **InfoStealers** | https://infostealers.info/en/info | FREE | Indexes darknet-exposed infostealer logs — searchable and actionable for forensics |
| **IntelBase** | https://intelbase.is | FREEMIUM | Reverse email lookup + breach-data enrichment |
| **LeakCheck** | https://leakcheck.io | FREEMIUM | Breach search engine — 7.5B+ entries from 3000+ databases |
| **LeakRadar** | https://leakradar.io | PAID | Proactive compromised-email/domain scanning via stealer logs |
| **CredenShow** | https://credenshow.com | FREEMIUM | Compromised credential discovery pre-ATO |
| **IKnowYour.Dad** | https://iknowyour.dad | FREE | Data breach search engine |
| **StealSeek** | https://stealseek.io | FREEMIUM | Data breach analyzer |
| **Venacus** | https://venacus.com | FREEMIUM | Breach alerts + notification |
| **MalwareBazaar (abuse.ch)** | https://bazaar.abuse.ch/browse/ | FREE | Confirmed malware samples searchable by hash/family/tag |
| **YARAify (abuse.ch)** | https://yaraify.abuse.ch/scan/ | FREE | YARA-engine threat intel through pattern matching |
| **URLhaus (abuse.ch)** | https://urlhaus.abuse.ch | FREE | Malicious URL feeds — combat malware and botnets |
| **Abuse.ch Unified Search** | https://hunting.abuse.ch | FREE | Single query across all abuse.ch platforms (MalwareBazaar, ThreatFox, URLhaus, YARAify, SSLBL) |

### Use pattern for ELISS scoring
- **Confirmed incident in last 24 months** → +10 Intent (security incident) + Strong-to-Imminent Timing trigger
- **Domain appears in HIBP Domain Search with recent breach** → +5 Intent + ask in discovery (gentle framing)
- **Ransomware.live shows prospect as recent victim** → confirms incident even when prospect hasn't publicly disclosed; treat with extreme discretion
- **HHS Breach Portal entry for healthcare prospect** → mandatory cross-check; 500+ records affected = MUST be reported
- **Hudson Rock flags stealer-log hits** → implies endpoint compromise somewhere in the org → even if public breach isn't disclosed, this is a timing signal and a Log360/AD360 UEBA talking point

**Ethical guardrails:** Never use leaked credentials. Never reference the leak directly in outreach. Use ONLY to inform your understanding of the prospect's posture and timing. The dossier may note "Prospect appeared in a 2024 third-party breach (HIBP)" as a Tier-A signal, but outreach language must NEVER reference the credentials themselves.

---

## Category 21 — THREAT INTELLIGENCE & REPUTATION (Layer 2 + Layer 6) [v5.7+]

Adjacent to Security OSINT (§14) but focused on real-world threat signals: domain/IP/URL reputation, hosting threat scores, and observed malicious activity targeting the prospect. These help quantify the prospect's actual exposure (vs. just their visible attack surface) and surface adjacent post-breach pressure.

| Source | URL | Access | Best for |
|---|---|---|---|
| URLscan.io | https://urlscan.io | FREEMIUM | Domain/URL scan history — shows phishing kits hosted on prospect look-alike domains (typosquatting threats) |
| GreyNoise | https://www.greynoise.io | FREEMIUM | Distinguishes targeted attacks from internet background noise — informs whether prospect is being actively targeted |
| AbuseIPDB | https://www.abuseipdb.com | FREE | Crowdsourced IP-reputation database — check prospect's IP ranges for past abuse reports |
| AlienVault OTX (AT&T) | https://otx.alienvault.com | FREE | Open Threat Exchange — community IOCs; pulse subscriptions track threats targeting specific industries. **Also API-integrated in `scripts/preflight.py` (v7.4.1+) when `OTX_API_KEY` is set** — fetches domain pulse hits + IP pulse hits (chained off DNS A/MX records) + recent sector pulses (when `--industry` is supplied), all outside Claude's tool budget. Free API key: signup at otx.alienvault.com. |
| ThreatBook / ThreatCrowd-style aggregators | https://x.threatbook.com | FREEMIUM | Domain/IP threat intelligence aggregator (replacement for the discontinued ThreatCrowd) |
| Cisco Talos Intelligence | https://talosintelligence.com | FREE | Email/domain reputation + recent threat campaign reporting |
| Spamhaus | https://www.spamhaus.org | FREE | Spam/abuse lookup — confirms prospect's network is or isn't on a block list |
| MISP Communities | https://www.misp-project.org | FREE | Open-source threat intelligence sharing platform — sector-specific threat feeds |
| RiskIQ PassiveTotal (Microsoft Defender Threat Intelligence) | https://ti.defender.microsoft.com | FREEMIUM | Passive DNS + WHOIS history + threat indicators — Microsoft consolidated the RiskIQ acquisition here |
| BitSight (rating snapshot) | https://www.bitsight.com | PAID | Cybersecurity rating service — sometimes prospect's BitSight grade is published in their RFPs or vendor risk questionnaires |
| SecurityScorecard (rating snapshot) | https://securityscorecard.com | PAID | Same category as BitSight — adjacent reputation grading |

### Use pattern for AD360/Log360 positioning
- **Active phishing kits targeting prospect domain (URLscan)** → Log360 talking point: real-time phishing detection + DNS sinkhole alerts
- **Prospect IPs in AbuseIPDB** → likely compromised endpoints inside their network → Log360 UEBA + EDR-feed positioning
- **OTX pulses for prospect's industry** → contextual ammunition: "your industry saw N specific campaigns this quarter; here's how Log360 detects them"

**Ethical guardrails:** Same as §14 + §20 — query ONLY publicly available data. Never run active scans. Never reference these sources by name in outreach unless the prospect raises the topic.

---

## Category 22 — COOPERATIVE PURCHASING & STATE AG BREACH PAGES (Layer 4 + Layer 3) [v5.7+]

### Cooperative purchasing vehicles (non-DIR procurement paths)
For US state/local prospects, DIR (Texas) is just one option. The following cooperative contracts let prospects bypass formal RFP for IT purchases — knowing which vehicles your prospect uses is the difference between a 60-day and a 6-month deal cycle.

| Source | URL | Access | Geographic / scope |
|---|---|---|---|
| Sourcewell | https://www.sourcewell-mn.gov | FREE | National cooperative; 50K+ government members; fast IT procurement path |
| OMNIA Partners | https://www.omniapartners.com/publicsector | FREE | National cooperative; consolidates former US Communities + National IPA |
| TIPS (The Interlocal Purchasing System) | https://www.tips-usa.com | FREE | Texas-based national cooperative; especially strong for K-12 + municipal |
| NASPO ValuePoint | https://www.naspovaluepoint.org | FREE | Multi-state cooperative; strong for IT category contracts |
| GSA Schedule 70 / MAS IT | https://www.gsaelibrary.gsa.gov | FREE | Federal IT acquisition path (also accessible to state/local via Cooperative Purchasing Program) |
| E&I Cooperative Services | https://www.eandi.org | FREE | Higher-education cooperative (200+ products) |
| HGAC Buy | https://www.hgacbuy.org | FREE | Houston-Galveston Area Council cooperative — TX regional |
| BuyBoard (TX Local Govt Cooperative) | https://www.buyboard.com | FREE | Texas Association of School Boards cooperative; 60K+ members |
| Mohave Educational Services Cooperative | https://www.mesc.org | FREE | AZ-based cooperative; significant national K-12 reach |

### State Attorney General breach-notice pages (50-state coverage for Layer 3 post-breach research)
Required cross-check for any prospect with a suspected incident. Not all states require central AG reporting (HI, ID), and a few use the Department of Justice or Consumer Protection division instead — links below reflect actual current locations.

| State | URL | Notes |
|---|---|---|
| California | https://oag.ca.gov/privacy/databreach/list | Strict reporting; searchable database |
| Texas | https://www.texasattorneygeneral.gov/open-government/governmental-bodies/catastrophe-notice | Confirmed Coppell breach via this page |
| New York | https://ag.ny.gov/internet/data-breach | NY DFS also separately reports for financial sector |
| Florida | https://oag.myfloridalegal.com | Public records request needed; less searchable |
| Massachusetts | https://www.mass.gov/lists/data-breach-notification-letters | Excellent searchable archive |
| Washington | https://www.atg.wa.gov/data-breach-notifications | Searchable + public-facing |
| Maryland | https://www.marylandattorneygeneral.gov/Pages/IdentityTheft/breachnotices.aspx | Searchable |
| Indiana | https://www.in.gov/attorneygeneral/consumer-protection-division/identity-theft/data-breach-notifications | Public list |
| New Hampshire | https://www.doj.nh.gov/consumer/security-breaches | Lists 1,000+ historical notifications |
| Oregon | https://justice.oregon.gov/consumer/databreach | Searchable |
| Vermont | https://ago.vermont.gov/cap/data-breaches | Searchable |
| Iowa | https://www.iowaattorneygeneral.gov/for-consumers/security-breach-notifications | Searchable list |
| Wisconsin | https://datcp.wi.gov/Pages/Programs_Services/DataBreaches.aspx | Lists incidents |
| All others (40 states) | Search format: `"<state name>" "data breach notification" attorney general` | Most states post breach notifications somewhere on the AG or Consumer Protection sites; searchability varies |

**Use pattern:**
1. For any prospect domain, check both the prospect's home-state AG page AND California's (CA reporting is mandatory for any breach affecting CA residents — most national breaches show up here)
2. For HHS-regulated prospects, also check the HHS Breach Portal (in §20) — the most authoritative source for healthcare breaches
3. Note the entry URL in the dossier as Tier-A evidence; tag the source explicitly

---

## Category 23 — HARDWARE & INFRASTRUCTURE FINGERPRINTING (Layer 2) [v6.0+]

**This is the single highest-value category for AD360/Log360 sales intelligence.** These tools reveal what hardware the prospect runs, what software versions are exposed, what cloud/identity providers they're bound to, and what attack-surface footprint they show to the world. Every entry here serves the 7-layer protocol's Technology & Security Posture layer (Layer 2) with direct evidence rather than inference.

The §14 Security OSINT category remains the primary infra reconnaissance bench; §23 adds specialized tools for deeper fingerprinting — Azure tenant resolution, BGP/ASN, attack-surface-management platforms, Wi-Fi wardriving, and asset-discovery engines.

### Azure / Entra ID tenant resolution (AD360 jackpot)
| Source | URL | Access | Best for |
|---|---|---|---|
| **Azure Tenant Resolution by PingCastle** | https://tenantresolution.pingcastle.com | FREE | **Domain → Azure/Entra tenant ID via OpenID discovery. Instantly confirms prospect has Azure AD/Entra and reveals federated domain relationships.** Gold for AD360 positioning — knowing tenant exists = Microsoft-heavy shop = AD360 deep fit. |
| AADInternals | https://aadinternals.com/ | FREE | Azure AD attack research — adjacent tooling; use reputationally only |

### BGP / ASN / network-layer intelligence
| Source | URL | Access | Best for |
|---|---|---|---|
| **BGP.tools** | https://bgp.tools | FREE | Modern BGP toolkit — reveals prospect's upstream ISPs, peering relationships, AS size |
| **BGP.he.net (Hurricane Electric)** | https://bgp.he.net | FREE | Free BGP + network intelligence toolkit — IP ranges owned by org |
| **BGPView.io** | https://bgpview.io | FREE | ASN lookup + IP ranges + BGP route history |

### Attack-Surface Management (ASM) platforms — third-party asset discovery
| Source | URL | Access | Best for |
|---|---|---|---|
| **FullHunt** | https://fullhunt.io | FREEMIUM | External attack-surface management — 2B+ indexed hosts, CVE→host mapping, internet-scale discovery |
| **FOFA** | https://en.fofa.info | FREEMIUM | Asset search & analysis — Chinese cyberspace search engine with rich fingerprinting |
| **Hunter Search Engine** (hunter.how) | https://hunter.how | FREEMIUM | Exposed internet assets + open web directories |
| **Netlas.io** | https://app.netlas.io/ | FREEMIUM | Internet asset discovery with query-based search |
| **ODIN** | https://search.odin.io | FREEMIUM | Host/CVE/bucket search (10 free searches/day) |
| **ONYPHE** | https://search.onyphe.io | FREEMIUM | OSINT engine indexing exposed assets/services across the internet |
| **Criminal IP** | https://www.criminalip.io | FREEMIUM | Cyber threat intelligence + attack-surface management |
| **ZoomEye** | https://www.zoomeye.ai | FREEMIUM | Cyberspace search for IPs/domains/IoT/routers/webcams |
| **Shadowserver** | https://dashboard.shadowserver.org | FREE | Global statistics dashboard on cyber threats — sector-level exposure view |

### Cloud & storage exposure
| Source | URL | Access | Best for |
|---|---|---|---|
| **GrayhatWarfare** | https://grayhatwarfare.com | FREEMIUM | Indexes **open AWS S3 / Azure Blob / GCS buckets** — surfaces misconfigurations that drive a breach-prevention pitch |
| **Cloudflare Radar** | https://radar.cloudflare.com | FREE | Internet traffic patterns + technology trends — sector-level narratives |

### SSL/TLS & certificate transparency (deep)
| Source | URL | Access | Best for |
|---|---|---|---|
| **CertKit Certificate Search** | https://www.certkit.io/tools/ct-logs/ | FREE | Fast SSL/TLS CT log search — companion to crt.sh |
| **Qualys SSL Labs** | https://www.ssllabs.com/ssltest/ | FREE | SSL/TLS config compliance — flags legacy TLS = aging infrastructure |

### Wi-Fi & physical-infrastructure intelligence
| Source | URL | Access | Best for |
|---|---|---|---|
| **WiGLE** | https://wigle.net | FREE | **Crowdsourced global Wi-Fi wardriving database.** For specific corporate addresses, WiGLE may show enterprise SSID patterns, AP vendors (Cisco/Aruba/Meraki inference from BSSID OUI), and physical-site infrastructure signals. |

### Infrastructure scoring & threat reputation
| Source | URL | Access | Best for |
|---|---|---|---|
| **Pulsedive** | https://pulsedive.com | FREEMIUM | Threat intelligence aggregator — domain/IP/URL scoring |
| **isMalicious** | https://ismalicious.com | FREE | Aggregates malicious IP/domain feeds with real-time reputation scoring |
| **BrightCloud URL/IP Lookup** | https://brightcloud.com/tools/url-ip-lookup.php | FREE | Webroot's URL/IP reputation + category — threat detection |
| **Focsec** | https://focsec.com | FREEMIUM | Threat Intelligence API detecting VPN/Proxy/TOR/Bot traffic |
| **Hybrid Analysis** | https://www.hybrid-analysis.com | FREE | Detailed sandbox analysis of suspicious files/URLs |
| **MetaDefender** | https://metadefender.com | FREEMIUM | Multi-engine threat analysis for URLs/files/certs/domains/hashes |
| **Browserling** | https://www.browserling.com | FREEMIUM | Sandboxed browser — safely test suspicious links across browsers/OSes |

### Mobile + website source-code exposure
| Source | URL | Access | Best for |
|---|---|---|---|
| **BeVigil** | https://bevigil.com/search | FREEMIUM | Asset search (subdomains/URLs/params) inside mobile applications — reveals internal API endpoints |
| **WebsiteTechMiner.py** | https://github.com/cybersader/WebsiteTechMiner-py | FREE (OSS) | Automation script wrapping BuiltWith/Wappalyzer APIs for bulk technographic CSV extraction |

### Usage pattern for AD360/Log360 (the v6.0 playbook)
1. **Start with tenant resolution.** Run `tenantresolution.pingcastle.com` on the prospect domain. Tenant ID returned = Microsoft-shop confirmation → AD360 fit confidence +20%.
2. **BGP/ASN inventory.** `bgp.tools/as/[ASN]` → learn prospect's IP ranges. Feed those into Shodan (`net:[range]`), Censys, ONYPHE, and FullHunt for service-level exposure.
3. **Subdomain enumeration.** SubDomainRadar + DNSDumpster + crt.sh → cross-reference for `adfs.*`, `*.corp.*`, `vpn.*`, `portal.*`, `siem.*`, `splunk.*` — direct technographic signals.
4. **Cloud exposure check.** GrayhatWarfare → any open buckets on `[company].s3.amazonaws.com` or `[company].blob.core.windows.net` = immediate breach-prevention pitch for Log360's cloud-log correlation.
5. **Wi-Fi physical check.** WiGLE BSSID-OUI lookup for corporate HQ/branch addresses → infer AP vendor → if Cisco/Aruba/Meraki → adjacent opportunity for AD360 integration (RADIUS + 802.1x authentication auditing).

---

## Category 24 — THREAT ACTOR INTELLIGENCE & ATTRIBUTION (Layer 3 + Layer 6) [v6.0+]

**For sector-level narratives and compliance-pressure sourcing.** These tools let you say "Your industry has been targeted by X threat group 47 times this quarter, with these specific TTPs" — gold for executive-level conversations where abstract-risk arguments fail but specific-adversary arguments land.

| Source | URL | Access | Best for |
|---|---|---|---|
| **MITRE ATT&CK** | https://attack.mitre.org/groups/ | FREE | Canonical threat group taxonomy + TTPs. Cite by group ID (e.g., G0016 APT29). |
| **MISP Galaxy** | https://www.misp-galaxy.org/360net/ | FREE | Community-curated adversary groups (360.net view) |
| **Malpedia (Fraunhofer FKIE)** | https://malpedia.caad.fkie.fraunhofer.de/actors | FREE | Academic threat-actor index — rigorous attribution |
| **ETDA Thailand** | https://apt.etda.or.th/cgi-bin/listgroups.cgi | FREE | Threat actor directory with tooling overlap |
| **FortiGuard Threat Actor Encyclopedia** | https://www.fortiguard.com/threat-actor | FREE | Fortinet's actor encyclopedia with active campaign intel |
| **SOCRadar LABS Threat Actor** | https://socradar.io/labs/threat-actor/ | FREEMIUM | Threat actor profiles + TTPs — commercially rigorous |
| **KnowledgeNow (Netenrich)** | https://know.netenrich.com/content/track/threat-actor | FREEMIUM | Trending-threats tracker |
| **APT Groups and Operations (Google Sheet)** | https://docs.google.com/spreadsheets/u/0/d/1H9_xaxQHpWaa4O_Son4Gx0YOIzlcBWMsdvePFX68EKU/pubhtml | FREE | Florian Roth's legendary curated APT spreadsheet |
| **APTWiki** | https://apt.threatradar.net/ | FREE | Historical wiki with 214 actor entries |
| **Bi.Zone GTI** | https://gti.bi.zone/ | FREE | 148 threat groups with detailed TTPs |
| **BreachHQ Threat Actors** | https://breach-hq.com/threat-actors | FREE | Breach-centric threat actor list |
| **Cybergeist** | https://cybergeist.io/threat-actor | FREE | AI-generated threat actor intelligence profiles |
| **Dark Web Informer** | https://darkwebinformer.com/threat-actor-database | FREE | Active threat actor tracker (854+ actors, active curation) |
| **OPENHUNTING.IO** | https://openhunting.io/threat-library | FREE | Threat library |
| **Lazarus.day** | https://lazarus.day/actors/ | FREE | Specialized tracker for Lazarus / DPRK-aligned groups |
| **Thales Cyberthreat Attacks** | https://cds.thalesgroup.com/en/cyberthreat/attacks-page | FREE | Graphical attack explorer with actor-group view |

### Use pattern for ELISS
- **For the prospect's sector, pull 3–5 active actor groups** targeting it per FortiGuard/SOCRadar/MITRE.
- **Map TTPs to AD360/Log360 detection capabilities** — e.g., "RansomHub's Coppell TTP included AD credential theft + lateral movement; AD360's privileged-account monitoring + Log360's UEBA detect this specific technique."
- **This becomes Tier-A evidence in the "Competitive Pressure" narrative** and the compliance-deadline rationale.

---

## Category 25 — LIVE CYBER THREAT MAPS (Layer 3) [v6.0+]

**Supplementary narrative material.** These are not primary-research sources but help reps open calls with "Your region / your industry is under visible attack right now."

| Source | URL | Access | Best for |
|---|---|---|---|
| Bitdefender Threat Map | https://threatmap.bitdefender.com/ | FREE | Real-time attack visualization |
| Check Point Live | https://threatmap.checkpoint.com/ | FREE | Top cyber threats with ransomware/infostealer/cloud slices |
| FortiGuard Outbreak Alerts | https://fortiguard.fortinet.com/threat-map | FREE | Ongoing attack visualization + industry impact |
| IBM X-Force Exchange | https://exchange.xforce.ibmcloud.com/activity/map | FREE | Current malicious activity map |
| Imperva Live Threat Map | https://www.imperva.com/cyber-threat-attack-map/ | FREE | Real-time DDoS + hacking attempts |
| Kaspersky Cyberthreat Map | https://cybermap.kaspersky.com/ | FREE | Interactive global cyberthreat map |
| NETSCOUT Horizon | https://horizon.netscout.com/ | FREE | Real-time DDoS attack map |
| Radware Live Threat Map | https://livethreatmap.radware.com/ | FREE | Near-real-time cyberattack visualization |
| Zscaler ThreatLabz | https://threatlabz.zscaler.com/cloud-insights/threat-map-dashboard | FREE | Past-24-hour detected threats dashboard |
| Thales Cyberthreat Map | https://cds.thalesgroup.com/en/cyberthreat/hitmap | FREE | Regional + sector trends |

**Rule:** cite these as Tier-C (promotional/aggregated) sources. Never rely on them for specific claims about a prospect — use for color commentary only.

---

## Category 26 — DOCUMENT, LEGAL & COURT RECORDS (Layer 3 + Layer 4) [v6.0+]

Extends §15 Legal/Regulatory with document-centric research paths — court filings, offshore leaks, government document archives, public company document repositories.

| Source | URL | Access | Best for |
|---|---|---|---|
| **CourtListener** | https://www.courtlistener.com | FREE | (In §15 — cross-referenced here) Federal court filings + RECAP archive |
| **RECAP Archive** | https://www.courtlistener.com/recap/ | FREE | Public archive of PACER court documents — free alternative to PACER per-doc fees |
| **Judyrecords** | https://www.judyrecords.com/ | FREE | 400M+ US court cases searchable nationwide |
| **UniCourt** | https://unicourt.com/ | FREEMIUM | 100M+ US court cases with premium data upsell |
| **Caselaw Access Project (Harvard)** | https://case.law/ | FREE | Full text of US state appellate cases (historical, not real-time) |
| **DocumentCloud** | https://www.documentcloud.org | FREE | Platform for document analysis + annotation (journalism-focused, huge archive) |
| **Offshore Leaks Database (ICIJ)** | https://offshoreleaks.icij.org | FREE | Panama/Paradise/Pandora Papers searchable — beneficial-ownership disclosure |
| **Epstein Exposed** | https://epsteinexposed.com | FREE | 2M+ DOJ Epstein documents searchable — example of scoped document archives |
| **OCCRP Aleph** | https://aleph.occrp.org/ | FREE | Global investigative journalism archive |
| **Free Full PDF** | http://www.freefullpdf.com | FREE | Technical/academic PDF search |
| **Scribd** | https://www.scribd.com | FREEMIUM | Document hosting — sometimes surfaces leaked internal decks |
| **SlideShare** | https://www.slideshare.net | FREE | Public deck archive — occasionally reveals prospect's internal pitch decks |
| **Federal Register** | https://www.federalregister.gov | FREE | US federal regulatory rules + proposed rule comment periods |
| **Google Patents** | https://patents.google.com | FREE | Patent search — signals R&D direction |
| **USPTO TSDR** | https://tsdr.uspto.gov | FREE | Trademark status + document retrieval |
| **Espacenet (EPO)** | https://worldwide.espacenet.com | FREE | 150M+ patents worldwide |
| **WIPO Global Brand Database** | https://www3.wipo.int/branddb/en/ | FREE | International trademark search |

### Use pattern for ELISS
- **Court cases against prospect** (CourtListener/Judyrecords): check for data-breach-related, employment, ADA, or regulatory cases — all signal risk environment
- **RFP/procurement docs** (DocumentCloud): many FOIA-released procurement records live here; searchable by prospect name + keyword "RFP" or "security"
- **SlideShare/Scribd**: legacy channels but occasionally surface investor decks, org charts, technical architecture overviews leaked by employees
- **Offshore Leaks**: for private-company ownership-transparency work, and for diligence on beneficial owners

---

## Category 27 — AI RESEARCH ACCELERATORS (All Layers) [v6.0+]

**Force multipliers, not primary sources.** LLM-powered search engines help the analyst synthesize and discover citations faster, but every claim must still be verified against the primary-source feeds in §1–§26. Cite outputs by their underlying source documents, not the AI tool itself.

| Source | URL | Access | Best for |
|---|---|---|---|
| **Perplexity** | https://www.perplexity.ai | FREEMIUM | AI-powered search with inline source citations — excellent for rapid summarization |
| **Phind** | https://www.phind.com | FREEMIUM | Developer-focused AI search — good for technical-stack questions |
| **You.com** | https://you.com | FREEMIUM | General AI search |
| **Brave Search** | https://search.brave.com | FREE | Independent, transparent search engine — useful fallback when Google de-prioritizes niche content |
| **Kagi Search** | https://kagi.com/ | PAID | Ad-free, tracker-free — high signal on technical queries |
| **DuckDuckGo** | https://duckduckgo.com | FREE | Privacy-focused search — useful for queries that get personalized on Google |
| **Wolfram Alpha** | https://www.wolframalpha.com | FREEMIUM | Computational knowledge engine — handy for quantitative inference (employee-count → revenue estimation, etc.) |

### Rules of use for ELISS
1. **Never cite the AI engine as a source.** If Perplexity points you at an SEC filing, cite the SEC filing.
2. **Always click through to the underlying source** and confirm the claim before including it in the dossier.
3. **AI engines hallucinate URLs** — verify each URL via web_fetch or browser click before entering it into the dossier.
4. **Use for synthesis, not discovery of facts.** They help you organize research you've already done; they're not a substitute for the curated feeds above.

---



## Selection Heuristics

**If you have a ZoomInfo/6sense/Cognism subscription**, use it as the primary feed for Layers 1, 2, 5 — it consolidates firmographic + technographic + intent in one place.

**If you don't have a paid subscription**, this is the free-tier stack that gets you 80% of the value:
- Layer 1: LinkedIn Company Page + Glassdoor + Crunchbase + OpenCorporates (EU/UK)
- Layer 2: BuiltWith (free tier) + Wappalyzer + LinkedIn Jobs + Greenhouse/Lever boards + MXToolbox (email fingerprint) + crt.sh (infra) + **Azure Tenant Resolution (§23)** + **SubDomainRadar + DNSDumpster (§14)** + press releases via Google Alerts
- Layer 3: Google + SEC EDGAR (public cos) + CourtListener (litigation) + Federal Register (regulatory) + **MITRE ATT&CK + FortiGuard Threat Actor (§24)** for sector-threat narrative
- Layer 4: SEC EDGAR + Yahoo Finance + OpenInsider (insider trades) + USAspending.gov (for Gov prospects) + GetLatka (private SaaS) + **Judyrecords + RECAP (§26)** for public-records signal
- Layer 5: LinkedIn Sales Navigator free trial + Apollo.io free tier + RocketReach
- Layer 6: G2 + PeerSpot + AlternativeTo + Owler + SimilarWeb + **FullHunt / FOFA / ONYPHE (§23)** for incumbent-infrastructure evidence
- Layer 7: Google + LinkedIn personal profiles + Hacker News + Sessionize (conference speakers)

**Regional considerations:**
- EU/UK prospects: Prefer Cognism (GDPR-compliant) over ZoomInfo for contact data; use **UK Companies House** (free) and **OpenCorporates** (140 jurisdictions) for authoritative registry data
- APAC prospects: Coverage in ZoomInfo/Apollo drops significantly — rely more on LinkedIn + local job boards + **Tracxn** (APAC-strong)
- Government prospects: **SAM.gov** + **USAspending.gov** + **Texas DIR** (for TX) are mandatory feeds; commercial tools miss most of this. Also check the **Local Government Intelligence sub-section of §5** (Legistar/Granicus, TML/NACo, GFOA) and **Cooperative Purchasing vehicles in §22** (Sourcewell, OMNIA, TIPS, BuyBoard) for non-DIR procurement paths. For municipal cyber-grant-funded procurement, check **grants.gov + CISA SLCGP** (v6.0 additions in §22)
- Post-breach prospects: Always check **CourtListener** (litigation), the prospect's **state AG catastrophe-notice page** (50-state list in §22), **Shodan/Censys/FullHunt (§23)** for current infrastructure exposure, **Hudson Rock + LeakCheck + InfoStealers (§20)** for infostealer-log hits, **Ransomware.live + IntelX + The Record** (§20) for breach-claim confirmation and context
- Microsoft-heavy prospects: Run **Azure Tenant Resolution by PingCastle (§23)** first — a returned tenant ID confirms Azure/Entra tenancy, which is a direct AD360 fit signal and also reveals federated domain relationships

---

## Source Freshness Notes

All URLs were valid as of April 2026. A few flagged for watch:
- **Clearbit** was acquired by HubSpot (2023) — still operational but some standalone features have moved into HubSpot
- **Leadfeeder** is now **Dealfront** (rebrand completed 2023)
- **Triblio** was acquired by Foundry — platform name may change
- **AI Ark** is a smaller provider; verify coverage before paying
- **Capterra** and **Software Advice** are both Gartner-owned — data overlap is significant, use one or the other
- **Wellfound** (ex-AngelList Talent) — focus is startups, lower signal for regulated mid-market ICP

Before any systematic campaign, confirm the URL still resolves and the feature you're relying on still exists.

---

## Total: 300+ URLs across 27 categories → ~200 unique domains

This directory is canonical for ELISS research. If new sources become available, add them here with a category tag and usage note. Sources removed from production should be retained with a "DEPRECATED" marker rather than deleted, so historical dossiers remain interpretable.

**Version history:**
- v1.0 — 88 URLs, 13 categories (original skill baseline)
- v1.1 (April 2026) — added Security OSINT (§14), Legal/Regulatory (§15), Gov Contracts (§16), Website Monitoring (§17), Automation (§18), Partner Ecosystems (§19) + targeted additions to existing categories. Net +50 high-signal URLs relevant to AD360/Log360 ICP.
- v1.2 (April 2026, ELISS v5.7) — added Local Government Intelligence sub-section to §5 Firmographic (12 new sources for municipal/county prospects); added Breach & Leak Intelligence (§20, 14 sources including HIBP, IntelX, Ransomware.live, HHS Breach Portal); added Threat Intelligence & Reputation (§21, 11 sources including URLscan, GreyNoise, AbuseIPDB, OTX); added Cooperative Purchasing & State AG Breach Pages (§22, 9 cooperatives + 13 confirmed-listed state AG pages with 50-state coverage notes). Net +60 sources, three new categories. Driven by gaps surfaced during the City of Coppell post-breach research case.
- **v1.3 (April 2026, ELISS v6.0)** — **major expansion derived from jivoi/awesome-osint (25.1k stars, 1,225 commits, active curation).** Expanded §14 Security OSINT with 13 new infrastructure-fingerprinting sources (DNSDumpster, DNSViz, ICANN Lookup, Robtex, Domain Dossier, SubDomainRadar, DomainRecon, DNS History, Validin, Web-Check, Webscout, TinyScan, intoDNS). Expanded §20 Breach & Leak with 12 new sources (Hudson Rock, InfoStealers, IntelBase, LeakCheck, LeakRadar, CredenShow, IKnowYour.Dad, StealSeek, Venacus, MalwareBazaar, YARAify, URLhaus, abuse.ch unified). Added **§23 Hardware & Infrastructure Fingerprinting** (~30 sources — Azure Tenant Resolution by PingCastle, BGP.tools, BGP.he.net, BGPView, FullHunt, FOFA, Hunter.how, Netlas, ODIN, ONYPHE, Criminal IP, ZoomEye, Shadowserver, GrayhatWarfare, Cloudflare Radar, CertKit, Qualys SSL Labs, WiGLE, Pulsedive, isMalicious, BrightCloud, Focsec, Hybrid Analysis, MetaDefender, Browserling, BeVigil, WebsiteTechMiner.py + usage playbook). Added **§24 Threat Actor Intelligence & Attribution** (16 sources — MITRE ATT&CK, MISP Galaxy, Malpedia, ETDA, FortiGuard, SOCRadar, APT Groups Google Sheet, APTWiki, Bi.Zone, BreachHQ, Cybergeist, Dark Web Informer, OPENHUNTING.IO, Lazarus.day, Thales, KnowledgeNow). Added **§25 Live Cyber Threat Maps** (10 sources — Bitdefender, Check Point, FortiGuard, IBM X-Force, Imperva, Kaspersky, NETSCOUT, Radware, Zscaler, Thales). Added **§26 Document, Legal & Court Records** (17 sources — RECAP, Judyrecords, UniCourt, Caselaw Access Project, DocumentCloud, Offshore Leaks, OCCRP Aleph, Epstein Exposed, Scribd, SlideShare, USPTO TSDR, Espacenet, WIPO Global Brand DB, Google Patents, etc.). Added **§27 AI Research Accelerators** (7 sources — Perplexity, Phind, You.com, Brave Search, Kagi, DuckDuckGo, Wolfram Alpha) with explicit rules against citing AI engines as primary sources. Net +100 sources, five new categories. Driven by user request for comprehensive OSINT expansion with explicit emphasis on hardware/software information for AD360/Log360 ICP. **Validation methodology:** master list fetched from GitHub (awesome-osint), critical/high-stakes new additions spot-checked individually via web_fetch (PingCastle Azure Tenant Resolution, Hudson Rock, FullHunt confirmed live), remaining sources inherit curation from the awesome-osint maintainers.
