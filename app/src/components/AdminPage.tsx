import { useCallback, useEffect, useState } from "react";
import { useServerFn } from "@/lib/use-server-fn";
import { adminListUsers, adminSetRole, adminDeleteUser } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ShieldCheck, ShieldOff, Trash2, RefreshCw, Users } from "lucide-react";
import { Spinner } from "@/components/Spinner";
import { CreateUserDialog } from "./CreateUserDialog";
import { safeDate } from "@/lib/utils";

type AdminUser = {
  id: string;
  email: string | null;
  created_at: string;
  last_sign_in_at: string | null;
  confirmed?: boolean;
  email_confirmed_at: string | null;
  banned_until: string | null;
  provider: string | null;
  roles: string[];
  is_admin: boolean;
};

function fmt(ts: string | null) {
  // safeDate normalizes Catalyst's non-ISO datetime so this works on
  // Safari/iOS (V8 lenient-parses; JSC throws RangeError on .toLocaleString).
  const d = safeDate(ts);
  if (!d) return "—";
  try {
    return d.toLocaleString();
  } catch {
    return ts ?? "—";
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
  const confirmedCount = users.filter((u) => (u.confirmed || u.email_confirmed_at)).length;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-primary">Admin</div>
          <h1 className="text-2xl font-semibold mt-1 flex items-center gap-2">
            <Users className="h-5 w-5" /> User management
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            All accounts that have signed up to ELISS Lead Intelligence Hub.
          </p>
        </div>
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <CreateUserDialog
            onCreated={(u) => setUsers((prev) => [u, ...prev])}
          />
          <Button variant="outline" size="sm" onClick={() => void reload()} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} /> Refresh
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 sm:gap-3">
        <Card className="p-3 sm:p-4">
          <div className="text-[10px] sm:text-xs text-muted-foreground">Total users</div>
          <div className="text-xl sm:text-2xl font-semibold mt-1">{users.length}</div>
        </Card>
        <Card className="p-3 sm:p-4">
          <div className="text-[10px] sm:text-xs text-muted-foreground">Admins</div>
          <div className="text-xl sm:text-2xl font-semibold mt-1">{adminCount}</div>
        </Card>
        <Card className="p-3 sm:p-4">
          <div className="text-[10px] sm:text-xs text-muted-foreground">Confirmed</div>
          <div className="text-xl sm:text-2xl font-semibold mt-1">{confirmedCount}</div>
        </Card>
      </div>

      {err && <Card className="p-3 border-destructive/40 text-destructive text-sm">{err}</Card>}

      {/* Desktop table */}
      <Card className="overflow-hidden hidden md:block">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-muted-foreground">
              <tr className="text-left">
                <th className="px-4 py-2 font-medium">Email</th>
                <th className="px-4 py-2 font-medium">Role</th>
                <th className="px-4 py-2 font-medium">Provider</th>
                <th className="px-4 py-2 font-medium">Joined</th>
                <th className="px-4 py-2 font-medium">Last seen</th>
                <th className="px-4 py-2 font-medium">Confirmed</th>
                <th className="px-4 py-2 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && users.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                    <Spinner className="h-5 w-5 inline" />
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
                  // `me` is a CatalystUser (lib/auth.tsx) whose ID field is
                  // `user_id`, not `id`; coerce both sides to string because
                  // the SDK can return user_id as a number.
                  const isMe = u.id === String(me?.user_id ?? "");
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
                        {(u.confirmed || u.email_confirmed_at) ? (
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
                            /* Fixed width keeps the cell from re-flowing when
                               the role flips between admin (Revoke, 6ch) and
                               user (Promote, 7ch), and visually aligns the
                               action column across rows. */
                            className="w-28 justify-center"
                          >
                            {busyId === u.id ? (
                              <Spinner className="h-4 w-4" />
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
                            aria-label={`Delete user ${u.email ?? u.id}`}
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

      {/* Mobile card list */}
      <div className="md:hidden space-y-3">
        {loading && users.length === 0 ? (
          <Card className="p-8 text-center text-muted-foreground">
            <Spinner className="h-5 w-5 inline" />
          </Card>
        ) : users.length === 0 ? (
          <Card className="p-8 text-center text-sm text-muted-foreground">No users found.</Card>
        ) : (
          users.map((u) => {
            const isMe = u.id === String(me?.user_id ?? "");
            return (
              <Card key={u.id} className="p-3 space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-sm truncate">{u.email ?? "(no email)"}</div>
                    <div className="text-[10px] text-muted-foreground font-mono truncate">{u.id}</div>
                  </div>
                  {u.is_admin ? (
                    <Badge className="bg-primary/15 text-primary hover:bg-primary/20 shrink-0">admin</Badge>
                  ) : (
                    <Badge variant="secondary" className="shrink-0">user</Badge>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <div className="text-muted-foreground">Provider</div>
                    <div className="truncate">{u.provider ?? "—"}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Confirmed</div>
                    <div>
                      {(u.confirmed || u.email_confirmed_at) ? (
                        <Badge variant="outline" className="border-emerald-500/40 text-emerald-500 text-[10px]">yes</Badge>
                      ) : (
                        <Badge variant="outline" className="border-amber-500/40 text-amber-500 text-[10px]">pending</Badge>
                      )}
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Joined</div>
                    <div className="truncate">{fmt(u.created_at)}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Last seen</div>
                    <div className="truncate">{fmt(u.last_sign_in_at)}</div>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-1">
                  {isMe && <span className="text-[10px] text-muted-foreground mr-auto">(you)</span>}
                  <Button
                    size="sm"
                    variant="outline"
                    className="flex-1"
                    disabled={busyId === u.id}
                    onClick={() => void onToggleAdmin(u)}
                  >
                    {busyId === u.id ? (
                      <Spinner className="h-4 w-4" />
                    ) : u.is_admin ? (
                      <><ShieldOff className="h-4 w-4 mr-1" /> Revoke</>
                    ) : (
                      <><ShieldCheck className="h-4 w-4 mr-1" /> Promote</>
                    )}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-destructive hover:text-destructive"
                    disabled={busyId === u.id || isMe}
                    onClick={() => void onDelete(u)}
                    aria-label={`Delete user ${u.email ?? u.id}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </Card>
            );
          })
        )}
      </div>
    </div>
  );
}
