import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";
import { parseDossier } from "./parser.server";

const uploadSchema = z.object({
  filename: z.string().min(1).max(255),
  html: z.string().min(50).max(5_000_000),
});

export const uploadDossier = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((input: unknown) => uploadSchema.parse(input))
  .handler(async ({ data, context }) => {
    const { supabase, userId } = context;
    const parsed = parseDossier(data.html, data.filename);

    // Upload original HTML to storage
    const safeName = data.filename.replace(/[^a-zA-Z0-9._-]/g, "_");
    const storagePath = `${userId}/${Date.now()}_${safeName}`;
    const { error: upErr } = await supabase.storage
      .from("dossiers")
      .upload(storagePath, new Blob([data.html], { type: "text/html" }), {
        contentType: "text/html",
        upsert: false,
      });
    if (upErr) throw new Error(`Storage upload failed: ${upErr.message}`);

    const { signals: _signals, ...parsedFields } = parsed;
    const row = {
      uploaded_by: userId,
      storage_path: storagePath,
      filename: data.filename,
      ...parsedFields,
    };

    // Upsert lead by (lead_name, company, report_date)
    let existingQuery = supabase
      .from("leads")
      .select("id, storage_path")
      .eq("lead_name", parsed.lead_name);
    existingQuery = parsed.company
      ? existingQuery.eq("company", parsed.company)
      : existingQuery.is("company", null);
    existingQuery = parsed.report_date
      ? existingQuery.eq("report_date", parsed.report_date)
      : existingQuery.is("report_date", null);
    const { data: existing } = await existingQuery.maybeSingle();

    let leadId: string;
    if (existing) {
      // delete old storage
      if (existing.storage_path && existing.storage_path !== storagePath) {
        await supabase.storage.from("dossiers").remove([existing.storage_path]);
      }
      const { error } = await supabase.from("leads").update(row).eq("id", existing.id);
      if (error) throw new Error(error.message);
      leadId = existing.id;
      await supabase.from("lead_signals").delete().eq("lead_id", leadId);
    } else {
      const { data: ins, error } = await supabase.from("leads").insert(row).select("id").single();
      if (error) throw new Error(error.message);
      leadId = ins.id;
    }

    if (parsed.signals.length) {
      const { error: sigErr } = await supabase.from("lead_signals").insert(
        parsed.signals.map((s) => ({ ...s, lead_id: leadId })),
      );
      if (sigErr) throw new Error(sigErr.message);
    }

    return { id: leadId, lead_name: parsed.lead_name, company: parsed.company, updated: !!existing };
  });

export const listLeads = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((input: unknown) =>
    z.object({
      search: z.string().max(200).optional(),
      tier: z.enum(["HOT", "WARM", "COLD"]).optional(),
      company: z.string().max(200).optional(),
    }).parse(input ?? {}),
  )
  .handler(async ({ data, context }) => {
    const { supabase } = context;
    let q = supabase
      .from("leads")
      .select("id, lead_name, lead_title, company, email, composite_score, tier, report_date, created_at")
      .order("composite_score", { ascending: false, nullsFirst: false })
      .limit(500);

    if (data.tier) q = q.eq("tier", data.tier);
    if (data.company) q = q.eq("company", data.company);
    if (data.search && data.search.trim()) {
      const term = data.search.trim();
      q = q.or(
        `lead_name.ilike.%${term}%,company.ilike.%${term}%,lead_title.ilike.%${term}%,email.ilike.%${term}%`,
      );
    }

    const { data: rows, error } = await q;
    if (error) throw new Error(error.message);
    return { leads: rows ?? [] };
  });

export const getLead = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((input: unknown) => z.object({ id: z.string().uuid() }).parse(input))
  .handler(async ({ data, context }) => {
    const { supabase } = context;
    const { data: lead, error } = await supabase
      .from("leads")
      .select(
        "id, uploaded_by, storage_path, filename, lead_name, lead_title, company, email, report_date, eliss_version, composite_score, tier, confidence, icp_rating, icp_reason, fit_score, fit_max, fit_conf, intent_score, intent_max, intent_conf, timing_score, timing_max, timing_conf, budget_score, budget_max, budget_conf, verdict_headline, verdict_insight, verdict_next, executive_brief, created_at, updated_at"
      )
      .eq("id", data.id)
      .single();
    if (error) throw new Error(error.message);
    const { data: signals } = await supabase
      .from("lead_signals")
      .select("*")
      .eq("lead_id", data.id);

    // Fetch HTML
    const { data: file, error: fErr } = await supabase.storage
      .from("dossiers")
      .download(lead.storage_path);
    if (fErr) throw new Error(`Failed to load dossier: ${fErr.message}`);
    const html = await file.text();

    return { lead, signals: signals ?? [], html };
  });

export const deleteLead = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((input: unknown) => z.object({ id: z.string().uuid() }).parse(input))
  .handler(async ({ data, context }) => {
    const { supabase } = context;
    const { data: lead } = await supabase.from("leads").select("storage_path").eq("id", data.id).single();
    if (lead?.storage_path) {
      await supabase.storage.from("dossiers").remove([lead.storage_path]);
    }
    const { error } = await supabase.from("leads").delete().eq("id", data.id);
    if (error) throw new Error(error.message);
    return { ok: true };
  });

export const getDashboardStats = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    const { supabase } = context;
    const { data: leads, error } = await supabase
      .from("leads")
      .select("id, composite_score, tier, company, fit_score, intent_score, timing_score, budget_score, fit_max, intent_max, timing_max, budget_max, created_at, report_date");
    if (error) throw new Error(error.message);
    const { data: signals } = await supabase.from("lead_signals").select("signal_type, label, points");

    return { leads: leads ?? [], signals: signals ?? [] };
  });