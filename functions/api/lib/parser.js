const { parse } = require("node-html-parser");

const txt = (s) => (s ?? "").replace(/\s+/g, " ").trim() || null;
const num = (s) => {
  if (!s) return null;
  const m = String(s).match(/-?\d+(\.\d+)?/);
  return m ? Number(m[0]) : null;
};

// Map ICP rating string → integer 1..5 used for `icp_stars` column.
// Same vocab as the LIKE patterns in routes/leads.js icp_min handling.
function icpRatingToStars(rating) {
  if (rating == null) return null;
  const s = String(rating).toLowerCase().trim();
  if (!s) return null;
  // Numeric form: "4", "4/5", "4.2"
  const numMatch = s.match(/(\d+)/);
  if (numMatch) {
    const n = parseInt(numMatch[1], 10);
    if (n >= 1 && n <= 5) return n;
  }
  if (/(excellent|perfect|ideal|bullseye)/.test(s)) return 5;
  if (/(strong|great|high)/.test(s)) return 4;
  if (/(moderate|medium|good|fair)/.test(s)) return 3;
  if (/(weak|low|marginal)/.test(s)) return 2;
  if (/(poor|none|very weak|reject)/.test(s)) return 1;
  return null;
}

// Title-case a label for display. Internal grouping/dedup uses
// .toLowerCase() so "Compliance Need" and "Compliance need" collapse.
function canonicalizeLabel(label) {
  if (label == null) return label;
  const trimmed = String(label).trim().replace(/\s+/g, " ");
  if (!trimmed) return trimmed;
  return trimmed
    .toLowerCase()
    .split(" ")
    .map((w) => (w.length <= 2 || /^[a-z0-9]+\/[a-z0-9]+$/i.test(w) ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

// Clamp dim score to [0, max]. Real-world dossiers occasionally emit
// score > max (typo / regenerated dossier with stale rubric); without
// this, dashboards display percentages > 100% and composite_score
// inflation goes unnoticed.
function clampScore(score, max) {
  if (score == null || max == null) return score;
  if (typeof score !== "number" || typeof max !== "number") return score;
  if (score < 0) return 0;
  if (score > max) return max;
  return score;
}

// Strip mojibake-prone doubled quote sequences ("" or '') that
// upstream templates sometimes emit when escaping is run twice.
function fixDoubledQuotes(s) {
  if (typeof s !== "string") return s;
  return s
    .replace(/""+/g, '"')
    .replace(/''+/g, "'")
    .replace(/““+/g, "“")
    .replace(/””+/g, "”");
}

const COMPLIANCE_VOCAB = [
  "CJIS", "PCI-DSS", "PCI DSS", "HIPAA", "SOC 2", "SOC2", "ISO 27001", "ISO27001",
  "NIST", "GDPR", "FERPA", "GLBA", "FedRAMP", "SOX", "CMMC", "SB 271", "HB 3834",
  "TX DIR", "DIR ISP", "TCF", "§521.053", "TX-RAMP",
];

const COMPETITOR_VOCAB = [
  "Sentinel", "Defender", "Splunk", "QRadar", "CrowdStrike", "Okta", "SailPoint",
  "Saviynt", "Varonis", "Rapid7", "Elastic", "Datadog", "SolarWinds", "Tenable",
  "Palo Alto", "Cisco",
];

function parseDossier(html, fallbackFilename) {
  const root = parse(html);

  const titleEl = root.querySelector("title");
  const titleText = titleEl?.text || "";

  const leadNameEl = root.querySelector(".lead-name");
  const leadSubEl = root.querySelector(".lead-sub");
  const lead_name =
    txt(leadNameEl?.text) ||
    titleText.split("—")[1]?.split("@")[0]?.trim() ||
    fallbackFilename.replace(/\.html?$/i, "");

  let lead_title = null;
  let company = null;
  let email = null;
  if (leadSubEl) {
    const sub = leadSubEl.text.trim();
    const emailMatch = sub.match(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/);
    email = emailMatch ? emailMatch[0] : null;
    const beforeEmail = sub.split("•")[0].trim();
    const atIdx = beforeEmail.toLowerCase().lastIndexOf(" at ");
    if (atIdx > -1) {
      lead_title = beforeEmail.slice(0, atIdx).trim();
      company = beforeEmail.slice(atIdx + 4).trim();
    } else {
      lead_title = beforeEmail || null;
    }
  }
  if (!company) {
    const m = titleText.match(/@\s*([^—–-]+)/);
    if (m) company = m[1].trim();
  }

  const brandMark = txt(root.querySelector(".brand-mark")?.text);
  const eliss_version = brandMark?.match(/v[\d.]+/i)?.[0] ?? null;
  const headerDate = txt(root.querySelector(".header-date")?.text);
  let report_date = null;
  if (headerDate) {
    const m = headerDate.match(/(\d{4})-(\d{2})-(\d{2})/);
    if (m) report_date = `${m[1]}-${m[2]}-${m[3]}`;
  }

  const composite_score = num(root.querySelector(".verdict-score")?.text);
  const tier = txt(root.querySelector(".verdict-tier")?.text)?.toUpperCase() ?? null;
  const verdict_headline = txt(root.querySelector(".verdict-headline")?.text);
  const verdict_insight = txt(root.querySelector(".verdict-insight")?.text);
  const verdict_next = txt(root.querySelector(".verdict-next")?.text);

  const confidence =
    txt(root.querySelector(".conf-label")?.text)
      ?.replace(/confidence/i, "")
      .trim() || null;
  const icp_rating =
    txt(root.querySelector(".icp-label")?.text)?.replace(/^ICP:\s*/i, "") || null;
  const icp_reason = txt(root.querySelector(".icp-reason")?.text);

  const dims = {};
  for (const row of root.querySelectorAll(".dim-row")) {
    const name = txt(row.querySelector(".dim-name")?.text)?.toLowerCase() ?? "";
    const scoreEl = row.querySelector(".dim-score");
    const maxEl = row.querySelector(".dim-max");
    const conf = txt(row.querySelector(".dim-conf")?.text);
    let scoreText = scoreEl?.text || "";
    if (maxEl) scoreText = scoreText.replace(maxEl.text, "");
    const rawScore = num(scoreText);
    const max = num(maxEl?.text);
    dims[name] = { score: clampScore(rawScore, max), max, conf };
  }

  const executive_brief = txt(root.querySelector(".exec-brief")?.text);

  // v7.6.0 Demo Playbook teaser — the full card renders inside the iframe;
  // this teaser unlocks the React leads-list "Demo ready" badge + detail-page
  // preview without re-parsing the whole HTML on the response path.
  //
  // Renderer (scripts/generate_report.py build_demo_playbook_html) emits:
  //   <div class="section infographic-section">
  //     <div class="section-title">Demo Playbook</div>
  //     <div class="demo-head">
  //       <div class="demo-persona"><span class="demo-persona-text">{persona}</span>...</div>
  //       <div class="demo-hook"><span class="demo-hook-text">{hook}</span>...</div>
  //     </div>
  //     <div class="demo-product" ...><div class="demo-product-head">AD360</div>...</div>
  //     <div class="demo-product" ...><div class="demo-product-head">Log360</div>...</div>
  //   </div>
  let demo_playbook = null;
  {
    let demoSection = null;
    for (const sec of root.querySelectorAll(".section.infographic-section")) {
      const title = txt(sec.querySelector(".section-title")?.text);
      if (title === "Demo Playbook") { demoSection = sec; break; }
    }
    if (demoSection) {
      const persona = txt(demoSection.querySelector(".demo-persona-text")?.text);
      const opening_hook = txt(demoSection.querySelector(".demo-hook-text")?.text);
      let has_ad360 = false;
      let has_log360 = false;
      for (const prod of demoSection.querySelectorAll(".demo-product")) {
        const head = txt(prod.querySelector(".demo-product-head")?.text);
        if (!head) continue;
        if (/AD360/i.test(head)) has_ad360 = true;
        else if (/Log360/i.test(head)) has_log360 = true;
      }
      const has_playbook = !!(opening_hook || has_ad360 || has_log360);
      if (has_playbook) {
        demo_playbook = { persona, opening_hook, has_ad360, has_log360, has_playbook: true };
      }
    }
  }

  const signals = [];
  // Dedup signals by (signal_type, lowercased label) so cosmetically
  // different casings ("Compliance Need" vs "Compliance need") collapse
  // into a single canonical row. Display label is title-cased.
  const seenSig = new Set();
  const pushSignal = (signal_type, rawLabel, points, detail) => {
    const label = canonicalizeLabel(rawLabel);
    if (!label) return;
    const key = `${signal_type}|${label.toLowerCase()}`;
    if (seenSig.has(key)) return;
    seenSig.add(key);
    signals.push({ signal_type, label, points, detail: fixDoubledQuotes(detail) });
  };

  for (const r of root.querySelectorAll(".attr-leg-row")) {
    pushSignal(
      "attribution",
      txt(r.querySelector(".attr-leg-cat")?.text),
      num(r.querySelector(".attr-leg-pts")?.text),
      txt(r.querySelector(".attr-leg-evidence")?.text),
    );
  }

  for (const c of root.querySelectorAll(".sc-card")) {
    pushSignal(
      "scenario",
      txt(c.querySelector(".sc-label")?.text),
      num(c.querySelector(".sc-delta-pill")?.text),
      txt(c.querySelector(".sc-trigger .sc-block-text")?.text),
    );
  }

  const haystack = [executive_brief, verdict_insight, verdict_headline, icp_reason]
    .filter(Boolean)
    .join(" \n ");
  for (const term of COMPLIANCE_VOCAB) {
    const re = new RegExp(`\\b${term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i");
    if (re.test(haystack)) pushSignal("compliance", term, null, null);
  }
  for (const term of COMPETITOR_VOCAB) {
    const re = new RegExp(`\\b${term}\\b`, "i");
    if (re.test(haystack)) pushSignal("competitor", term, null, null);
  }

  // Recompute composite from clamped dim scores so a score>max in the
  // dossier doesn't inflate the composite. Falls back to the parsed
  // .verdict-score only when no dim rows were emitted.
  const dimSum =
    (dims["fit"]?.score ?? 0) +
    (dims["intent"]?.score ?? 0) +
    (dims["timing"]?.score ?? 0) +
    (dims["budget"]?.score ?? 0);
  const hasAnyDim = !!(dims["fit"] || dims["intent"] || dims["timing"] || dims["budget"]);
  const composite_score_clamped = hasAnyDim ? dimSum : composite_score;

  return {
    lead_name,
    lead_title,
    company,
    email,
    report_date,
    eliss_version,
    composite_score: composite_score_clamped,
    tier,
    confidence,
    icp_rating,
    icp_stars: icpRatingToStars(icp_rating),
    icp_reason,
    fit_score: dims["fit"]?.score ?? null,
    fit_max: dims["fit"]?.max ?? null,
    fit_conf: dims["fit"]?.conf ?? null,
    intent_score: dims["intent"]?.score ?? null,
    intent_max: dims["intent"]?.max ?? null,
    intent_conf: dims["intent"]?.conf ?? null,
    timing_score: dims["timing"]?.score ?? null,
    timing_max: dims["timing"]?.max ?? null,
    timing_conf: dims["timing"]?.conf ?? null,
    budget_score: dims["budget"]?.score ?? null,
    budget_max: dims["budget"]?.max ?? null,
    budget_conf: dims["budget"]?.conf ?? null,
    verdict_headline,
    verdict_insight,
    verdict_next,
    executive_brief,
    demo_playbook,
    signals,
  };
}

module.exports = { parseDossier };
