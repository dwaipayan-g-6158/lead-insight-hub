
-- Leads table
CREATE TABLE public.leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  uploaded_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  storage_path TEXT NOT NULL,
  filename TEXT NOT NULL,

  -- Identity
  lead_name TEXT NOT NULL,
  lead_title TEXT,
  company TEXT,
  email TEXT,
  report_date DATE,
  eliss_version TEXT,

  -- Scoring
  composite_score INTEGER,
  tier TEXT, -- HOT / WARM / COLD
  confidence TEXT,
  icp_rating TEXT,
  icp_reason TEXT,

  fit_score INTEGER, fit_max INTEGER, fit_conf TEXT,
  intent_score INTEGER, intent_max INTEGER, intent_conf TEXT,
  timing_score INTEGER, timing_max INTEGER, timing_conf TEXT,
  budget_score INTEGER, budget_max INTEGER, budget_conf TEXT,

  -- Narrative
  verdict_headline TEXT,
  verdict_insight TEXT,
  verdict_next TEXT,
  executive_brief TEXT,

  -- Search
  search_tsv tsvector GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(lead_name,'')), 'A') ||
    setweight(to_tsvector('english', coalesce(company,'')), 'A') ||
    setweight(to_tsvector('english', coalesce(lead_title,'')), 'B') ||
    setweight(to_tsvector('english', coalesce(email,'')), 'B') ||
    setweight(to_tsvector('english', coalesce(verdict_headline,'')), 'C') ||
    setweight(to_tsvector('english', coalesce(executive_brief,'')), 'D')
  ) STORED,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (lead_name, company, report_date)
);

CREATE INDEX leads_search_idx ON public.leads USING GIN (search_tsv);
CREATE INDEX leads_company_idx ON public.leads (company);
CREATE INDEX leads_tier_idx ON public.leads (tier);
CREATE INDEX leads_score_idx ON public.leads (composite_score DESC);
CREATE INDEX leads_created_idx ON public.leads (created_at DESC);

-- Signals (compliance, attribution, competitors, scenarios)
CREATE TABLE public.lead_signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id UUID NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
  signal_type TEXT NOT NULL, -- 'compliance' | 'attribution' | 'competitor' | 'scenario'
  label TEXT NOT NULL,
  points INTEGER,
  detail TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX lead_signals_lead_idx ON public.lead_signals (lead_id);
CREATE INDEX lead_signals_type_label_idx ON public.lead_signals (signal_type, label);

-- updated_at trigger
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END; $$;

CREATE TRIGGER leads_updated_at BEFORE UPDATE ON public.leads
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- RLS
ALTER TABLE public.leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lead_signals ENABLE ROW LEVEL SECURITY;

CREATE POLICY "auth read leads" ON public.leads FOR SELECT TO authenticated USING (true);
CREATE POLICY "auth insert leads" ON public.leads FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "auth update leads" ON public.leads FOR UPDATE TO authenticated USING (true);
CREATE POLICY "auth delete leads" ON public.leads FOR DELETE TO authenticated USING (true);

CREATE POLICY "auth read signals" ON public.lead_signals FOR SELECT TO authenticated USING (true);
CREATE POLICY "auth insert signals" ON public.lead_signals FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "auth update signals" ON public.lead_signals FOR UPDATE TO authenticated USING (true);
CREATE POLICY "auth delete signals" ON public.lead_signals FOR DELETE TO authenticated USING (true);

-- Storage bucket for original HTML
INSERT INTO storage.buckets (id, name, public) VALUES ('dossiers', 'dossiers', false)
ON CONFLICT (id) DO NOTHING;

CREATE POLICY "auth read dossier files" ON storage.objects FOR SELECT TO authenticated
  USING (bucket_id = 'dossiers');
CREATE POLICY "auth upload dossier files" ON storage.objects FOR INSERT TO authenticated
  WITH CHECK (bucket_id = 'dossiers');
CREATE POLICY "auth update dossier files" ON storage.objects FOR UPDATE TO authenticated
  USING (bucket_id = 'dossiers');
CREATE POLICY "auth delete dossier files" ON storage.objects FOR DELETE TO authenticated
  USING (bucket_id = 'dossiers');
