import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import type { SupabaseClient } from "@supabase/supabase-js";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";
import { supabaseAdmin } from "@/integrations/supabase/client.server";

// The generated Database types don't yet include `user_roles` (added by
// migration 20260501000000_user_roles_admin.sql). Cast to an untyped client
// for those queries.
const sa = supabaseAdmin as unknown as SupabaseClient;

type RoleRow = { user_id: string; role: "admin" | "user" };

/**
 * Returns the current user's role information.
 * Safe to call from any authenticated client.
 */
export const getMyRole = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    const { userId } = context;
    const { data, error } = await sa.from("user_roles").select("role").eq("user_id", userId);
    if (error) throw new Error(error.message);
    const roles = ((data ?? []) as { role: RoleRow["role"] }[]).map((r) => r.role);
    return { userId, roles, isAdmin: roles.includes("admin") };
  });

async function assertAdmin(userId: string) {
  const { data, error } = await sa
    .from("user_roles")
    .select("role")
    .eq("user_id", userId)
    .eq("role", "admin")
    .maybeSingle();
  if (error) throw new Error(error.message);
  if (!data) throw new Error("Forbidden: admin role required");
}

/**
 * List every auth user (admins only).
 */
export const adminListUsers = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((input: unknown) =>
    z
      .object({
        page: z.number().int().min(1).max(1000).optional(),
        perPage: z.number().int().min(1).max(200).optional(),
      })
      .parse(input ?? {}),
  )
  .handler(async ({ data, context }) => {
    await assertAdmin(context.userId);

    const page = data.page ?? 1;
    const perPage = data.perPage ?? 100;

    const { data: list, error } = await supabaseAdmin.auth.admin.listUsers({ page, perPage });
    if (error) throw new Error(error.message);

    const ids = list.users.map((u) => u.id);
    const { data: roleRows, error: rErr } = await sa
      .from("user_roles")
      .select("user_id, role")
      .in("user_id", ids.length ? ids : ["00000000-0000-0000-0000-000000000000"]);
    if (rErr) throw new Error(rErr.message);

    const roleMap = new Map<string, string[]>();
    for (const r of (roleRows ?? []) as RoleRow[]) {
      const cur = roleMap.get(r.user_id) ?? [];
      cur.push(r.role);
      roleMap.set(r.user_id, cur);
    }

    const users = list.users.map((u) => ({
      id: u.id,
      email: u.email ?? null,
      created_at: u.created_at,
      last_sign_in_at: u.last_sign_in_at ?? null,
      email_confirmed_at: u.email_confirmed_at ?? null,
      banned_until: (u as { banned_until?: string | null }).banned_until ?? null,
      provider: (u.app_metadata as { provider?: string } | undefined)?.provider ?? null,
      roles: roleMap.get(u.id) ?? [],
      is_admin: (roleMap.get(u.id) ?? []).includes("admin"),
    }));

    return {
      users,
      total: (list as { total?: number }).total ?? users.length,
      page,
      perPage,
    };
  });

/**
 * Promote/demote a user to/from admin (admins only).
 */
export const adminSetRole = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((input: unknown) =>
    z
      .object({
        userId: z.string().uuid(),
        role: z.enum(["admin", "user"]),
        grant: z.boolean(),
      })
      .parse(input),
  )
  .handler(async ({ data, context }) => {
    await assertAdmin(context.userId);

    if (data.role === "admin" && !data.grant) {
      const { count, error: cErr } = await sa
        .from("user_roles")
        .select("user_id", { count: "exact", head: true })
        .eq("role", "admin");
      if (cErr) throw new Error(cErr.message);
      if ((count ?? 0) <= 1) {
        throw new Error("Cannot remove the last remaining admin.");
      }
    }

    if (data.grant) {
      const { error } = await sa
        .from("user_roles")
        .upsert({ user_id: data.userId, role: data.role }, { onConflict: "user_id,role" });
      if (error) throw new Error(error.message);
    } else {
      const { error } = await sa
        .from("user_roles")
        .delete()
        .eq("user_id", data.userId)
        .eq("role", data.role);
      if (error) throw new Error(error.message);
    }

    return { ok: true };
  });

/**
 * Delete a user account entirely (admins only).
 */
export const adminDeleteUser = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((input: unknown) => z.object({ userId: z.string().uuid() }).parse(input))
  .handler(async ({ data, context }) => {
    await assertAdmin(context.userId);
    if (data.userId === context.userId) {
      throw new Error("You cannot delete your own account.");
    }
    const { error } = await supabaseAdmin.auth.admin.deleteUser(data.userId);
    if (error) throw new Error(error.message);
    return { ok: true };
  });
