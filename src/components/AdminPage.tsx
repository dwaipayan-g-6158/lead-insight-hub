import { useCallback, useEffect, useState } from "react";
import { useServerFn } from "@tanstack/react-start";
import { adminListUsers, adminSetRole, adminDeleteUser } from "@/server/admin.functions";
import { useAuth } from "@/lib/auth";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, ShieldCheck, ShieldOff, Trash2, RefreshCw, Users } from "lucide-react";

type AdminUser = {
  id: string;
  email: string | null;
  created_at: string;
  last_sign_in_at: string | null;
  email_confirmed_at: string | null;
  banned_until: string | null;
  provider: string | null;
  roles: string[];
  is_admin: boolean;
};

function fmt(ts: string | null) {
  if (!ts) return "—";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

export function AdminPage() {
  const { user: me } = useAuth();
  const list = useServerFn(adminListUsers);
  const setRole = useServerFn(adminSetRole);
  const deleteUser = useServerFn(adminDeleteUser);

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const res = await list({ data: { page: 1, perPage: 200 } });
      setUsers(res.users as AdminUser[]);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [list]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const onToggleAdmin = async (u: AdminUser) => {
    setBusyId(u.id);
    setErr(null);
    try {
      await setRole({ data: { userId: u.id, role: "admin", grant: !u.is_admin } });
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  const onDelete = async (u: AdminUser) => {
    if (!confirm(`Delete account ${u.email ?? u.id}? This cannot be undone.`)) return;
    setBusyId(u.id);
    setErr(null);
    try {
      await deleteUser({ data: { userId: u.id } });
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  const adminCount = users.filter((u) => u.is_admin).length;
  const confirmedCount = users.filter((u) => u.email_confirmed_at).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-primary">Admin</div>
          <h1 className="text-2xl font-semibold mt-1 flex items-center gap-2">
            <Users className="h-5 w-5" /> User management
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            All accounts that have signed up to ELISS Lead Intelligence Hub.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void reload()} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} /> Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Card className="p-4">
          <div className="text-xs text-muted-foreground">Total users</div>
          <div className="text-2xl font-semibold mt-1">{users.length}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-muted-foreground">Admins</div>
          <div className="text-2xl font-semibold mt-1">{adminCount}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-muted-foreground">Email confirmed</div>
          <div className="text-2xl font-semibold mt-1">{confirmedCount}</div>
        </Card>
      </div>

      {err && <Card className="p-3 border-destructive/40 text-destructive text-sm">{err}</Card>}

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-muted-foreground">
              <tr className="text-left">
                <th className="px-4 py-2 font-medium">Email</th>
                <th className="px-4 py-2 font-medium">Role</th>
                <th className="px-4 py-2 font-medium">Provider</th>
                <th className="px-4 py-2 font-medium">Joined</th>
                <th className="px-4 py-2 font-medium">Last sign-in</th>
                <th className="px-4 py-2 font-medium">Confirmed</th>
                <th className="px-4 py-2 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && users.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                    <Loader2 className="h-5 w-5 animate-spin inline" />
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                    No users found.
                  </td>
                </tr>
              ) : (
                users.map((u) => {
                  const isMe = u.id === me?.id;
                  return (
                    <tr key={u.id} className="border-t border-border">
                      <td className="px-4 py-2">
                        <div className="font-medium">{u.email ?? "(no email)"}</div>
                        <div className="text-[11px] text-muted-foreground font-mono">{u.id}</div>
                      </td>
                      <td className="px-4 py-2">
                        {u.is_admin ? (
                          <Badge className="bg-primary/15 text-primary hover:bg-primary/20">
                            admin
                          </Badge>
                        ) : (
                          <Badge variant="secondary">user</Badge>
                        )}
                        {isMe && (
                          <span className="ml-2 text-[11px] text-muted-foreground">(you)</span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">{u.provider ?? "—"}</td>
                      <td className="px-4 py-2 text-muted-foreground">{fmt(u.created_at)}</td>
                      <td className="px-4 py-2 text-muted-foreground">{fmt(u.last_sign_in_at)}</td>
                      <td className="px-4 py-2">
                        {u.email_confirmed_at ? (
                          <Badge
                            variant="outline"
                            className="border-emerald-500/40 text-emerald-500"
                          >
                            yes
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="border-amber-500/40 text-amber-500">
                            pending
                          </Badge>
                        )}
                      </td>
                      <td className="px-4 py-2 text-right">
                        <div className="inline-flex items-center gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={busyId === u.id}
                            onClick={() => void onToggleAdmin(u)}
                            title={u.is_admin ? "Revoke admin" : "Promote to admin"}
                          >
                            {busyId === u.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : u.is_admin ? (
                              <>
                                <ShieldOff className="h-4 w-4 mr-1" /> Revoke
                              </>
                            ) : (
                              <>
                                <ShieldCheck className="h-4 w-4 mr-1" /> Promote
                              </>
                            )}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-destructive hover:text-destructive"
                            disabled={busyId === u.id || isMe}
                            onClick={() => void onDelete(u)}
                            title={isMe ? "You cannot delete yourself" : "Delete user"}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
