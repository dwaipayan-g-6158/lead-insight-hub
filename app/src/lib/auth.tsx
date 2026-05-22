import { createContext, useContext, useEffect, useState, useRef, type ReactNode } from "react";
import {
  loadCatalystSDK,
  getCurrentUser,
  isAuthenticated,
  renderSignInForm,
} from "@/lib/catalyst-client";
import { getMyProfile, postSignupBootstrap } from "@/lib/api";

export type CatalystUser = {
  user_id: string | number;
  email_id?: string;
  first_name?: string;
  last_name?: string;
};

type AuthCtx = {
  user: CatalystUser | null;
  session: { userId: string } | null;
  loading: boolean;
  isAdmin: boolean;
  roleLoading: boolean;
  refreshRole: () => Promise<void>;
  refreshUser: () => Promise<void>;
  renderLoginInto: (elementId: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CatalystUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);
  const [roleLoading, setRoleLoading] = useState(true);
  const pollRef = useRef<number | null>(null);

  const fetchProfile = async (currentUser: CatalystUser | null) => {
    if (!currentUser) {
      setIsAdmin(false);
      setRoleLoading(false);
      return;
    }
    setRoleLoading(true);
    try {
      // Lazy-bootstrap a role row on first authenticated call.
      try {
        await postSignupBootstrap();
      } catch (e) {
        console.warn("[auth] post-signup bootstrap (best-effort) failed:", e);
      }
      // The Web SDK's user object can be sparse; the backend (Node SDK)
      // returns the full profile reliably. Merge the firstName / lastName /
      // email fields onto the in-memory user object so the header chip can
      // render them.
      const res = await getMyProfile();
      setIsAdmin(!!res?.isAdmin);
      setUser((prev) =>
        prev
          ? {
              ...prev,
              first_name: res?.firstName ?? prev.first_name,
              last_name: res?.lastName ?? prev.last_name,
              email_id: res?.email ?? prev.email_id,
            }
          : prev,
      );
    } catch (e) {
      console.warn("[auth] failed to load profile", e);
      setIsAdmin(false);
    } finally {
      setRoleLoading(false);
    }
  };

  const refreshUser = async () => {
    const u = await getCurrentUser();
    setUser(u);
    await fetchProfile(u);
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await loadCatalystSDK();
        const u = await getCurrentUser();
        if (cancelled) return;
        setUser(u);
        // Await fetchProfile BEFORE clearing `loading` so AuthGate doesn't
        // open the door to children with stale isAdmin=false. Pairs with
        // the roleLoading gate in AuthGate.tsx.
        await fetchProfile(u);
        if (!cancelled) setLoading(false);
      } catch (e) {
        console.warn("[auth] SDK init failed", e);
        if (!cancelled) {
          setLoading(false);
          setRoleLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, []);

  const renderLoginInto = async (elementId: string) => {
    await renderSignInForm(elementId);
    // Poll for authentication after iframe mounts.
    // 8 s cadence (was 3 s): the Catalyst SDK's isAuthenticated() hits
    // /baas/v1/.../project-user/current under the hood, which returns
    // 401 while the login iframe is on-screen. Each 401 emits a console
    // error and a network row — at 3 s that's ~20 errors per minute of
    // login-screen dwell. 8 s keeps user-perceived latency acceptable
    // (most logins resolve within one tick) while cutting the noise to
    // ~7 errors/min.
    if (pollRef.current) window.clearInterval(pollRef.current);
    pollRef.current = window.setInterval(async () => {
      try {
        if (await isAuthenticated()) {
          if (pollRef.current) {
            window.clearInterval(pollRef.current);
            pollRef.current = null;
          }
          await refreshUser();
        }
      } catch {}
    }, 8000);
  };

  const signOut = async () => {
    try {
      const sdk = await loadCatalystSDK();
      await sdk.auth.signOut(`${window.location.origin}/app/index.html`);
    } catch (e) {
      console.warn("[auth] signOut failed", e);
    }
    setUser(null);
    setIsAdmin(false);
  };

  const refreshRole = async () => {
    await fetchProfile(user);
  };

  const session = user ? { userId: String(user.user_id) } : null;

  return (
    <Ctx.Provider
      value={{
        user,
        session,
        loading,
        isAdmin,
        roleLoading,
        refreshRole,
        refreshUser,
        renderLoginInto,
        signOut,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used inside AuthProvider");
  return v;
}
