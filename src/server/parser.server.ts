import { parse } from "node-html-parser";

export type ParsedDossier = {
  lead_name: string;
  lead_title: string | null;
  company: string | null;
  email: string | null;
  report_date: string | null; // YYYY-MM-DD
  eliss_version: string | null;
  composite_score: number | null;
  tier: string | null;
  confidence: string | null;
  icp_rating: string | null;
  icp_reason: string | null;
  fit_score: number | null; fit_max: number | null; fit_conf: string | null;
  intent_score: number | null; intent_max: number | null; intent_conf: string | null;
  timing_score: number | null; timing_max: number | null; timing_conf: string | null;
  budget_score: number | null; budget_max: number | null; budget_conf: string | null;
  verdict_headline: string | null;
  verdict_insight: string | null;
  verdict_next: string | null;
  executive_brief: string | null;
  signals: Array<{
    signal_type: "compliance" | "attribution" | "competitor" | "scenario";
    label: string;
    points: number | null;
    detail: string | null;
  }>;
};

const txt = (s: string | null | undefined) => (s ?? "").replace(/\s+/g, " ").trim() || null;
const num = (s: string | null | undefined) => {
  if (!s) return null;
  const m = String(s).match(/-?\d+(\.\d+)?/);
  return m ? Number(m[0]) : null;
};

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

export function parseDossier(html: string, fallbackFilename: string): ParsedDossier {
  const root = parse(html);

  const titleEl = root.querySelector("title");
  const titleText = titleEl?.text || "";

  const leadNameEl = root.querySelector(".lead-name");
  const leadSubEl = root.querySelector(".lead-sub");
  const lead_name = txt(leadNameEl?.text) || titleText.split("—")[1]?.split("@")[0]?.trim() || fallbackFilename.replace(/\.html?$/i, "");

  // lead-sub looks like: "Title at Company • email"
  let lead_title: string | null = null;
  let company: string | null = null;
  let email: string | null = null;
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
  // Fallback: company from title "@ Company"
  if (!company) {
    const m = titleText.match(/@\s*([^—–-]+)/);
    if (m) company = m[1].trim();
  }

  // Header date + version: ".brand-mark" + ".header-date"
  const brandMark = txt(root.querySelector(".brand-mark")?.text);
  const eliss_version = brandMark?.match(/v[\d.]+/i)?.[0] ?? null;
  const headerDate = txt(root.querySelector(".header-date")?.text);
  let report_date: string | null = null;
  if (headerDate) {
    const m = headerDate.match(/(\d{4})-(\d{2})-(\d{2})/);
    if (m) report_date = `${m[1]}-${m[2]}-${m[3]}`;
  }

  // Verdict banner
  const composite_score = num(root.querySelector(".verdict-score")?.text);
  const tier = txt(root.querySelector(".verdict-tier")?.text)?.toUpperCase() ?? null;
  const verdict_headline = txt(root.querySelector(".verdict-headline")?.text);
  const verdict_insight = txt(root.querySelector(".verdict-insight")?.text);
  const verdict_next = txt(root.querySelector(".verdict-next")?.text);

  // Confidence + ICP
  const confidence = txt(root.querySelector(".conf-label")?.text)?.replace(/confidence/i, "").trim() || null;
  const icp_rating = txt(root.querySelector(".icp-label")?.text)?.replace(/^ICP:\s*/i, "") || null;
  const icp_reason = txt(root.querySelector(".icp-reason")?.text);

  // Dimension rows: each .dim-row has .dim-name, .dim-score (with .dim-max inside), .dim-conf
  const dims: Record<string, { score: number | null; max: number | null; conf: string | null }> = {};
  for (const row of root.querySelectorAll(".dim-row")) {
    const name = txt(row.querySelector(".dim-name")?.text)?.toLowerCase() ?? "";
    const scoreEl = row.querySelector(".dim-score");
    const maxEl = row.querySelector(".dim-max");
    const conf = txt(row.querySelector(".dim-conf")?.text);
    let scoreText = scoreEl?.text || "";
    if (maxEl) scoreText = scoreText.replace(maxEl.text, "");
    dims[name] = { score: num(scoreText), max: num(maxEl?.text), conf };
  }

  const executive_brief = txt(root.querySelector(".exec-brief")?.text);

  // Signals
  const signals: ParsedDossier["signals"] = [];

  // Attribution categories from .attr-leg-row (category + pts + evidence)
  for (const r of root.querySelectorAll(".attr-leg-row")) {
    const label = txt(r.querySelector(".attr-leg-cat")?.text);
    const points = num(r.querySelector(".attr-leg-pts")?.text);
    const detail = txt(r.querySelector(".attr-leg-evidence")?.text);
    if (label) signals.push({ signal_type: "attribution", label, points, detail });
  }

  // Scenarios from .sc-card -> sc-label (signal), sc-delta-pill (points)
  for (const c of root.querySelectorAll(".sc-card")) {
    const label = txt(c.querySelector(".sc-label")?.text);
    const points = num(c.querySelector(".sc-delta-pill")?.text);
    const trigger = txt(c.querySelector(".sc-trigger .sc-block-text")?.text);
    if (label) signals.push({ signal_type: "scenario", label, points, detail: trigger });
  }

  // Compliance + competitor mentions: scan executive brief + verdict + icp_reason
  const haystack = [executive_brief, verdict_insight, verdict_headline, icp_reason]
    .filter(Boolean)
    .join(" \n ");
  const seen = new Set<string>();
  for (const term of COMPLIANCE_VOCAB) {
    const re = new RegExp(`\\b${term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i");
    if (re.test(haystack) && !seen.has(`c:${term}`)) {
      seen.add(`c:${term}`);
      signals.push({ signal_type: "compliance", label: term, points: null, detail: null });
    }
  }
  for (const term of COMPETITOR_VOCAB) {
    const re = new RegExp(`\\b${term}\\b`, "i");
    if (re.test(haystack) && !seen.has(`x:${term}`)) {
      seen.add(`x:${term}`);
      signals.push({ signal_type: "competitor", label: term, points: null, detail: null });
    }
  }

  return {
    lead_name: lead_name!,
    lead_title,
    company,
    email,
    report_date,
    eliss_version,
    composite_score,
    tier,
    confidence,
    icp_rating,
    icp_reason,
    fit_score: dims["fit"]?.score ?? null, fit_max: dims["fit"]?.max ?? null, fit_conf: dims["fit"]?.conf ?? null,
    intent_score: dims["intent"]?.score ?? null, intent_max: dims["intent"]?.max ?? null, intent_conf: dims["intent"]?.conf ?? null,
    timing_score: dims["timing"]?.score ?? null, timing_max: dims["timing"]?.max ?? null, timing_conf: dims["timing"]?.conf ?? null,
    budget_score: dims["budget"]?.score ?? null, budget_max: dims["budget"]?.max ?? null, budget_conf: dims["budget"]?.conf ?? null,
    verdict_headline,
    verdict_insight,
    verdict_next,
    executive_brief,
    signals,
  };
}