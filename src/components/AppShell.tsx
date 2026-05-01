import type { ReactNode } from "react";
import { Link, useLocation } from "@tanstack/react-router";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { LayoutDashboard, FileSearch, Upload, LogOut, Radar, Shield } from "lucide-react";

export function AppShell({ children }: { children: ReactNode }) {
  const { user, signOut, isAdmin } = useAuth();
  const loc = useLocation();
  const isActive = (p: string) => loc.pathname === p || (p !== "/" && loc.pathname.startsWith(p));

  const navItem = (to: string, label: string, Icon: typeof LayoutDashboard) => (
    <Link
      to={to}
      className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-colors ${
        isActive(to)
          ? "bg-primary/15 text-primary"
          : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
      }`}
    >
      <Icon className="h-4 w-4" />
      {label}
    </Link>
  );

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card/40 backdrop-blur sticky top-0 z-10">
        <div className="mx-auto max-w-7xl px-4 h-14 flex items-center gap-6">
          <Link to="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-md bg-primary/15 grid place-items-center">
              <Radar className="h-4 w-4 text-primary" />
            </div>
            <div className="leading-tight">
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">ELISS</div>
              <div className="text-sm font-semibold -mt-0.5">Intel Hub</div>
            </div>
          </Link>
          <nav className="flex items-center gap-1">
            {navItem("/", "Dashboard", LayoutDashboard)}
            {navItem("/leads", "Leads", FileSearch)}
            {navItem("/upload", "Upload", Upload)}
            {isAdmin && navItem("/admin", "Admin", Shield)}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <div className="text-xs text-muted-foreground hidden sm:block">
              {(user?.user_metadata as Record<string, string> | undefined)?.display_name ?? user?.email}
            </div>
            <Button variant="ghost" size="sm" onClick={signOut}>
              <LogOut className="h-4 w-4 mr-2" /> Sign out
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
    </div>
  );
}