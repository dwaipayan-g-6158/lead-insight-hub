/** Shared types for lead data across the app */

// Demo Playbook teaser (v7.6.0) — the full card lives in the rendered HTML
// inside the iframe; this teaser is what the leads-list badge and the
// detail-page preview read. The API returns it as a parsed object (the
// route handler JSON.parses the text column at /leads/:id and /leads).
export type DemoPlaybookTeaser = {
  persona: string | null;
  opening_hook: string | null;
  has_ad360: boolean;
  has_log360: boolean;
  has_playbook: true;
};

export type LeadRow = {
  id: string;
  lead_name: string;
  lead_title: string | null;
  company: string | null;
  email: string | null;
  report_date: string | null;
  eliss_version: string | null;
  composite_score: number | null;
  tier: string | null;
  confidence: string | null;
  icp_rating: string | null;
  icp_reason: string | null;
  fit_score: number | null;
  fit_max: number | null;
  fit_conf: string | null;
  intent_score: number | null;
  intent_max: number | null;
  intent_conf: string | null;
  timing_score: number | null;
  timing_max: number | null;
  timing_conf: string | null;
  budget_score: number | null;
  budget_max: number | null;
  budget_conf: string | null;
  verdict_headline: string | null;
  verdict_insight: string | null;
  verdict_next: string | null;
  executive_brief: string | null;
  demo_playbook: DemoPlaybookTeaser | null;
};

export type LeadListRow = {
  id: string;
  lead_name: string;
  lead_title: string | null;
  company: string | null;
  email: string | null;
  composite_score: number | null;
  tier: string | null;
  report_date: string | null;
  created_at: string;
  demo_playbook: DemoPlaybookTeaser | null;
};

export type Signal = {
  id: string;
  signal_type: string;
  label: string;
  points: number | null;
  detail: string | null;
};

export type StatsLead = {
  id: string;
  lead_name?: string | null;
  lead_title?: string | null;
  composite_score: number | null;
  tier: string | null;
  confidence?: string | null;
  icp_rating?: string | null;
  verdict_headline?: string | null;
  company: string | null;
  email?: string | null;
  fit_score: number | null;
  intent_score: number | null;
  timing_score: number | null;
  budget_score: number | null;
  fit_max: number | null;
  intent_max: number | null;
  timing_max: number | null;
  budget_max: number | null;
  fit_conf?: string | null;
  intent_conf?: string | null;
  timing_conf?: string | null;
  budget_conf?: string | null;
  created_at: string;
  report_date: string | null;
};

export type StatsSignal = {
  signal_type: string;
  label: string;
  points: number | null;
};
