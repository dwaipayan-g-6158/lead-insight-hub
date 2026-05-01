import { supabase } from "@/integrations/supabase/client";

/**
 * Installs a one-time global fetch interceptor that attaches the current
 * Supabase access token to TanStack server function calls.
 *
 * Without this, `requireSupabaseAuth` middleware rejects every server fn
 * call with 401.
 */
let patched = false;

export function patchFetchWithAuth() {
  if (patched || typeof window === "undefined") return;
  patched = true;

  const origFetch = window.fetch.bind(window);

  window.fetch = async (input, init) => {
    try {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;

      if (url?.includes("/_serverFn/")) {
        const { data } = await supabase.auth.getSession();
        const token = data.session?.access_token;
        if (token) {
          const headers = new Headers(
            init?.headers ?? (input instanceof Request ? input.headers : undefined),
          );
          if (!headers.has("authorization")) {
            headers.set("authorization", `Bearer ${token}`);
          }
          return origFetch(input, { ...init, headers });
        }
      }
    } catch {
      // fall through to original fetch
    }
    return origFetch(input, init);
  };
}
