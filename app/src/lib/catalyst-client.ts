/**
 * Wrapper around the Catalyst Web SDK (window.catalyst).
 * The auto-injected /__catalyst/sdk/init.js ships api_domain: "" which yields
 * broken URLs like /app/null/... so we re-init explicitly with the IN
 * data-center API URL.
 */

declare global {
  interface Window {
    catalyst?: any;
    I18N?: any;
    __catalyst_initialized__?: boolean;
  }
}

// Environment-aware config. The same build is deployed to both the Development
// and Production Web Client Hosting; the dev URL carries a ".development."
// segment while production does not. Detecting the environment at runtime lets
// one build initialize the Catalyst SDK with the correct per-environment ZAID,
// org id and storage domains (a hardcoded dev ZAID breaks prod login with an
// "Untrusted Domain" error).
const IS_DEV =
  typeof window !== "undefined" &&
  window.location.hostname.includes(".development.");

const PROJECT_ID = "31210000000133001";
const ZAID = IS_DEV ? "50042133518" : "50042142947";
const ORG_ID = IS_DEV ? "60066539659" : "50042142947";
const ENV = IS_DEV ? "Development" : "Production";

// IN data center.  api_domain is left empty so the SDK uses the page origin
// (Catalyst Web Client Hosting proxies /baas/* on the same domain).
const AUTH_DOMAIN = "https://accounts.zohoportal.in";
const API_DOMAIN =
  typeof window !== "undefined" ? window.location.origin : "";

const CDN_URL = "https://static.zohocdn.com/catalyst/sdk/js/4.5.0/catalystWebSDK.js";

let loadPromise: Promise<any> | null = null;

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) return resolve();
    const s = document.createElement("script");
    s.src = src;
    s.async = false;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(s);
  });
}

async function ensureSDKDefined(): Promise<void> {
  if (typeof window.catalyst !== "undefined") return;
  await loadScript(CDN_URL);
  const start = Date.now();
  while (typeof window.catalyst === "undefined" && Date.now() - start < 3000) {
    await new Promise((r) => setTimeout(r, 50));
  }
  if (typeof window.catalyst === "undefined") {
    throw new Error("Catalyst Web SDK failed to load");
  }
}

function initOnce(): void {
  if (window.__catalyst_initialized__) return;
  if (!window.catalyst || typeof window.catalyst.initApp !== "function") return;
  try {
    window.catalyst.initApp(
      {
        project_Id: PROJECT_ID,
        zaid: ZAID,
        auth_domain: AUTH_DOMAIN,
        is_appsail: false,
        stratus_domain: IS_DEV ? "-development.zohostratus.in" : ".zohostratus.in",
        nimbus_domain: IS_DEV ? "-development.nimbuspop.com" : ".nimbuspop.com",
        api_domain: API_DOMAIN,
      },
      { org_id: ORG_ID, environment: ENV },
    );
    window.__catalyst_initialized__ = true;
  } catch (e) {
    console.warn("[catalyst] initApp failed:", e);
  }
}

export function loadCatalystSDK(): Promise<any> {
  if (loadPromise) return loadPromise;
  loadPromise = (async () => {
    if (typeof window === "undefined") throw new Error("SSR not supported");
    await ensureSDKDefined();
    initOnce();
    return window.catalyst;
  })();
  return loadPromise;
}

export async function catalystAuth() {
  const sdk = await loadCatalystSDK();
  return sdk.auth;
}

export async function renderSignInForm(elementId: string) {
  const sdk = await loadCatalystSDK();
  const service_url = `${window.location.origin}/app/index.html`;
  // Cache-bust the iframe CSS so theme changes ship without a hard refresh.
  const css_url = `${window.location.origin}/app/login-iframe.css?v=35`;
  const params = {
    service_url,
    css_url,
  };
  if (typeof sdk.auth.signIn === "function") {
    try {
      await sdk.auth.signIn(elementId, params);
    } catch (e) {
      console.warn("[catalyst] signIn iframe render failed:", e);
      throw e;
    }
  }
}

export async function isAuthenticated(): Promise<boolean> {
  try {
    const sdk = await loadCatalystSDK();
    if (typeof sdk.auth?.isUserAuthenticated === "function") {
      return !!(await sdk.auth.isUserAuthenticated());
    }
    return false;
  } catch {
    return false;
  }
}

export async function getCurrentUser(): Promise<any | null> {
  try {
    const sdk = await loadCatalystSDK();
    if (typeof sdk.auth?.isUserAuthenticated === "function") {
      const ok = await sdk.auth.isUserAuthenticated();
      if (!ok) return null;
    }
    let raw: any = null;
    if (typeof sdk.auth?.getCurrentProjectUser === "function") {
      raw = await sdk.auth.getCurrentProjectUser();
    } else if (typeof sdk.userManagement?.getCurrentProjectUser === "function") {
      raw = await sdk.userManagement.getCurrentProjectUser();
    }
    // The 4.5.0 web SDK wraps the response as `{status, content, message}`;
    // older builds return the user object flat. Unwrap so downstream
    // consumers always see fields like `user_id` / `email_id` at the top
    // level (matches the `CatalystUser` type in lib/auth.tsx).
    if (raw && typeof raw === "object" && "content" in raw && raw.content) {
      return raw.content;
    }
    return raw;
  } catch {
    return null;
  }
}
