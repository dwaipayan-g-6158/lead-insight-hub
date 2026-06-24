import { useEffect, useState } from "react";
import { useServerFn } from "@/lib/use-server-fn";
import { getAuditDrilldown } from "@/lib/api";
import { useIsMobile } from "@/hooks/use-mobile";
import { Spinner } from "@/components/Spinner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
} from "@/components/ui/drawer";
import {
  AuditEventList,
  TYPE_META,
  relTime,
  absTime,
  initialsOf,
} from "@/components/AuditEventList";
import { Activity, Users, FileText, Search, ScrollText } from "lucide-react";
import type {
  AuditActiveUser,
  AuditDrilldownCard,
  AuditDrilldownResponse,
  AuditEventType,
} from "@/types/audit";

const CARD_META: Record<
  AuditDrilldownCard,
  { title: string; Icon: typeof Activity; empty: string }
> = {
  events: { title: "Events today", Icon: Activity, empty: "No events in the last 24 hours." },
  active_users: {
    title: "Active users",
    Icon: Users,
    empty: "No users active in the last 24 hours.",
  },
  dossiers: {
    title: "Dossiers today",
    Icon: FileText,
    empty: "No dossiers created in the last 24 hours.",
  },
  searches: { title: "Searches today", Icon: Search, empty: "No searches in the last 24 hours." },
};

function ActiveUserList({ users }: { users: AuditActiveUser[] }) {
  return (
    <ul className="divide-y divide-border">
      {users.map((u) => (
        <li key={u.user_id} className="flex items-center gap-3 px-4 py-3">
          <span
            aria-hidden
            className="inline-grid h-9 w-9 shrink-0 place-items-center rounded-full bg-primary/20 text-xs font-semibold"
          >
            {initialsOf(u.actor_name, u.actor_email)}
          </span>
          <div className="min-w-0 flex-1">
            <div className="font-medium truncate">{u.actor_name || u.actor_email || "Unknown"}</div>
            {u.actor_email && u.actor_name && (
              <div className="text-xs text-muted-foreground truncate">{u.actor_email}</div>
            )}
            <div className="mt-1 flex flex-wrap items-center gap-1">
              {(Object.entries(u.by_type) as [AuditEventType, number][])
                .filter(([, n]) => n > 0)
                .map(([type, n]) => {
                  const meta = TYPE_META[type];
                  if (!meta) return null;
                  return (
                    <span
                      key={type}
                      className={`inline-flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded-full border font-medium ${meta.badge}`}
                    >
                      <meta.Icon className="h-2.5 w-2.5" />
                      {n}
                    </span>
                  );
                })}
            </div>
          </div>
          <div className="shrink-0 text-right">
            <div className="text-sm font-semibold tabular-nums">{u.count}</div>
            <div className="text-[10px] text-muted-foreground" title={absTime(u.last_at)}>
              {relTime(u.last_at)}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

// Drill-down popup for a KPI card. Fetches once per open (no polling so the
// list doesn't shift under the user); renders the event list or the active-user
// roster depending on the card. Lists exactly match the card numbers because
// the backend reproduces /summary's rolling-24h test.
export function AuditDrilldownDialog({
  card,
  onOpenChange,
}: {
  card: AuditDrilldownCard | null;
  onOpenChange: (open: boolean) => void;
}) {
  const isMobile = useIsMobile();
  const fetchFn = useServerFn(getAuditDrilldown);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AuditDrilldownResponse | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const open = card !== null;

  // Retain the last-opened card so the close (fly-out) animation still has a
  // target after the parent clears `card` to null. All DISPLAY state derives
  // from this; only `open` and the fetch follow the live `card` prop.
  const [shownCard, setShownCard] = useState<AuditDrilldownCard | null>(card);
  useEffect(() => {
    if (card) setShownCard(card);
  }, [card]);

  useEffect(() => {
    if (!card) return;
    let active = true;
    setLoading(true);
    setError(null);
    setData(null);
    fetchFn({ data: { card } })
      .then((res) => {
        if (active) setData(res);
      })
      .catch((e) => {
        if (active) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [card, reloadKey, fetchFn]);

  const meta = shownCard ? CARD_META[shownCard] : null;
  const title = meta?.title ?? "";
  const count = data?.count;
  const subtitle =
    typeof count === "number"
      ? `Last 24 hours · ${count} ${count === 1 ? "item" : "items"}`
      : "Last 24 hours";

  const body = (
    <div className="min-h-[160px]">
      {loading ? (
        <div className="grid place-items-center py-12 text-muted-foreground">
          <Spinner className="h-5 w-5" />
        </div>
      ) : error ? (
        <div className="py-10 flex flex-col items-center justify-center gap-3 text-center px-6">
          <p className="text-sm text-muted-foreground">{error}</p>
          <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
            Retry
          </Button>
        </div>
      ) : !data || data.count === 0 ? (
        <div className="py-12 flex flex-col items-center justify-center gap-3 text-center px-6">
          <ScrollText className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground max-w-xs">{meta?.empty}</p>
        </div>
      ) : data.card === "active_users" ? (
        <ActiveUserList users={data.users} />
      ) : (
        <AuditEventList events={data.events} />
      )}
    </div>
  );

  if (isMobile) {
    return (
      <Drawer open={open} onOpenChange={onOpenChange} shouldScaleBackground={false} autoFocus>
        <DrawerContent className="max-h-[85vh]">
          <DrawerHeader>
            <DrawerTitle className="flex items-center gap-2">
              {meta && <meta.Icon className="h-4 w-4 text-primary" />}
              {title}
            </DrawerTitle>
            <DrawerDescription>{subtitle}</DrawerDescription>
          </DrawerHeader>
          <div className="overflow-y-auto pb-4">{body}</div>
        </DrawerContent>
      </Drawer>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-2xl p-0 gap-0"
        flyTarget={shownCard ? `[data-kpi="${shownCard}"]` : undefined}
        onCloseAutoFocus={(e) => e.preventDefault()}
      >
        <DialogHeader className="p-5 pb-3">
          <DialogTitle className="flex items-center gap-2">
            {meta && <meta.Icon className="h-4 w-4 text-primary" />}
            {title}
          </DialogTitle>
          <DialogDescription>{subtitle}</DialogDescription>
        </DialogHeader>
        <div className="max-h-[70vh] overflow-y-auto border-t border-border">{body}</div>
      </DialogContent>
    </Dialog>
  );
}
