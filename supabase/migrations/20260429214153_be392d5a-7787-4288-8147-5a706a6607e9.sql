
-- Tighten RLS: require auth.uid() IS NOT NULL on writes
DROP POLICY "auth insert leads" ON public.leads;
DROP POLICY "auth update leads" ON public.leads;
DROP POLICY "auth delete leads" ON public.leads;
DROP POLICY "auth insert signals" ON public.lead_signals;
DROP POLICY "auth update signals" ON public.lead_signals;
DROP POLICY "auth delete signals" ON public.lead_signals;

CREATE POLICY "team insert leads" ON public.leads FOR INSERT TO authenticated
  WITH CHECK (auth.uid() IS NOT NULL);
CREATE POLICY "team update leads" ON public.leads FOR UPDATE TO authenticated
  USING (auth.uid() IS NOT NULL) WITH CHECK (auth.uid() IS NOT NULL);
CREATE POLICY "team delete leads" ON public.leads FOR DELETE TO authenticated
  USING (auth.uid() IS NOT NULL);

CREATE POLICY "team insert signals" ON public.lead_signals FOR INSERT TO authenticated
  WITH CHECK (auth.uid() IS NOT NULL);
CREATE POLICY "team update signals" ON public.lead_signals FOR UPDATE TO authenticated
  USING (auth.uid() IS NOT NULL) WITH CHECK (auth.uid() IS NOT NULL);
CREATE POLICY "team delete signals" ON public.lead_signals FOR DELETE TO authenticated
  USING (auth.uid() IS NOT NULL);

DROP POLICY "auth upload dossier files" ON storage.objects;
DROP POLICY "auth update dossier files" ON storage.objects;
DROP POLICY "auth delete dossier files" ON storage.objects;

CREATE POLICY "team upload dossier files" ON storage.objects FOR INSERT TO authenticated
  WITH CHECK (bucket_id = 'dossiers' AND auth.uid() IS NOT NULL);
CREATE POLICY "team update dossier files" ON storage.objects FOR UPDATE TO authenticated
  USING (bucket_id = 'dossiers' AND auth.uid() IS NOT NULL);
CREATE POLICY "team delete dossier files" ON storage.objects FOR DELETE TO authenticated
  USING (bucket_id = 'dossiers' AND auth.uid() IS NOT NULL);

-- Fix function search path
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = public AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END; $$;
