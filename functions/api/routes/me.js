const express = require("express");
const { isHeavyAllowed } = require("../lib/featureFlags");
const { logEvent } = require("../lib/audit");

const router = express.Router();

router.get("/", async (req, res) => {
  // heavyAllowed lets the client gate the ELISS-Heavy UI per-user (hide the
  // 5-tap toggle for non-allowlisted users). It is NOT a security boundary —
  // routes/dossiers.js re-checks the same allowlist server-side and fails
  // closed regardless of what the client sends. Never let this throw: a
  // featureFlags failure must still return the rest of the profile.
  let heavyAllowed = false;
  try {
    heavyAllowed = await isHeavyAllowed(req.userId, req.catalystAdminApp || req.catalystApp);
  } catch (err) {
    console.warn("me: isHeavyAllowed check failed (defaulting false):", err.message);
  }
  res.json({
    userId: req.userId,
    email: req.user?.email_id ?? null,
    firstName: req.user?.first_name ?? null,
    lastName: req.user?.last_name ?? null,
    role: req.role,
    isAdmin: req.isAdmin,
    isSuperAdmin: req.isSuperAdmin,
    roles: [req.role],
    heavyAllowed,
  });
});

router.get("/role", (req, res) => {
  res.json({
    userId: req.userId,
    role: req.role,
    isAdmin: req.isAdmin,
    isSuperAdmin: req.isSuperAdmin,
    roles: [req.role],
  });
});

// POST /me/session-start — login beacon for the Audit Report.
//
// Catalyst Native Auth exposes no server-side "login happened" hook (the
// session is cookie-based and every request looks the same), so the client
// fires this exactly once per browser session — guarded by a sessionStorage
// flag in app/src/lib/auth.tsx — right after auth resolves. The body is
// ignored; the actor is taken only from the authenticated session, so a
// caller can never forge a login for someone else. Always 200 so a flaky
// beacon never surfaces an error in the UI; the audit write is best-effort.
router.post("/session-start", (req, res) => {
  logEvent(req, {
    eventType: "login",
    action: "session_start",
    metadata: { ua: String(req.get("user-agent") || "").slice(0, 250) },
  });
  res.json({ ok: true });
});

// Self-service password reset for the logged-in user. The email is taken
// ONLY from the authenticated session (req.user), never the request body, so
// a caller can only ever trigger a reset for their own account — no
// enumeration or abuse surface. Catalyst owns the actual reset: this sends
// its standard reset email; the user sets the new password on Catalyst's
// hosted page and is redirected back to the app. Mirrors the signupConfig
// shape used in routes/signup.js (registerUser also needs admin-scoped creds).
router.post("/reset-password", async (req, res) => {
  try {
    const email = req.user?.email_id;
    if (!email) return res.status(400).json({ error: "No email on account" });
    const userMgmt = (req.catalystAdminApp || req.catalystApp).userManagement();
    const resetConfig = {
      platform_type: "web",
      redirect_url: `${req.protocol}://${req.get("host")}/app/index.html`,
    };
    await userMgmt.resetPassword(email, resetConfig);
    res.json({ ok: true, email });
  } catch (err) {
    console.error("reset-password error:", err);
    res.status(500).json({ error: err?.message || "Reset failed" });
  }
});

module.exports = router;
