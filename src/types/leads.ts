/** Shared types for lead data across the app */

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
  composite_score: number | null;
  tier: string | null;
  company: string | null;
  fit_score: number | null;
  intent_score: number | null;
  timing_score: number | null;
  budget_score: number | null;
  fit_max: number | null;
  intent_max: number | null;
  timing_max: number | null;
  budget_max: number | null;
  created_at: string;
  report_date: string | null;
};

export type StatsSignal = {
  signal_type: string;
  label: string;
  points: number | null;
};
