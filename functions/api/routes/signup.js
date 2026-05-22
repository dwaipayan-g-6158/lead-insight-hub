const express = require("express");
const { notifyAdminsOfSignup } = require("../lib/mailer");

const router = express.Router();

// Public self-signup endpoint. Mounted at /auth/signup BEFORE requireUser
// in functions/api/index.js so it stays reachable without an auth cookie.
//
// Gate: email must end with one of ALLOWED_SIGNUP_DOMAINS (comma-separated
// env var, lowercased on read). Domain check runs BEFORE registerUser so
// non-allowed emails never produce a Catalyst user record — no ghost
// cleanup, no privilege-escalation surface.
//
// Admins invited via the existing POST /admin/users path are NOT subject
// to this gate (admins are trusted to invite anyone, including externals).

function parseAllowedDomains() {
  const raw = process.env.ALLOWED_SIGNUP_DOMAINS || "";
  return raw
    .split(",")
    .map((d) => d.trim().toLowerCase().replace(/^@/, ""))
    .filter(Boolean);
}

function formatAllowedList(domains) {
  if (domains.length === 0) return "an authorized";
  if (domains.length === 1) return `@${domains[0]}`;
  if (domains.length === 2) return `@${domains[0]} or @${domains[1]}`;
  return domains.slice(0, -1).map((d) => `@${d}`).join(", ") + `, or @${domains[domains.length - 1]}`;
}

router.post("/", async (req, res) => {
  try {
    const body = req.body || {};
    const first_name = String(body.first_name || "").trim();
    const last_name = String(body.last_name || "").trim();
    const email_id = String(body.email_id || "").trim().toLowerCase();

    if (!first_name) {
      return res.status(400).json({ error: "first_name is required" });
    }
    if (!email_id || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email_id)) {
      return res.status(400).json({ error: "A valid email is required" });
    }

    const allowed = parseAllowedDomains();
    if (allowed.length === 0) {
      // Defensive: misconfigured env should refuse, not silently allow all.
      console.error("signup: ALLOWED_SIGNUP_DOMAINS is empty — refusing.");
      return res.status(503).json({
        error: "Self-signup is temporarily unavailable. Please contact an administrator.",
      });
    }
    const domain = email_id.split("@")[1] || "";
    if (!allowed.includes(domain)) {
      return res.status(403).json({
        error: `Self-signup is restricted to ${formatAllowedList(allowed)} email addresses.`,
      });
    }

    // Use the admin-scoped Catalyst app — userManagement.registerUser
    // requires project-admin credentials and signup is unauthenticated so
    // there's no user context on req.catalystApp anyway.
    const app = req.catalystAdminApp || req.catalystApp;
    const userMgmt = app.userManagement();

    // Mirror the admin invite flow at functions/api/routes/admin.js:185–200:
    // Catalyst sends its standard invite email; the user clicks the link
    // to set their password and lands at redirect_url.
    const signupConfig = {
      platform_type: "web",
      redirect_url: `${req.protocol}://${req.get("host")}/app/index.html`,
    };
    const userDetails = { first_name, last_name, email_id };

    let created;
    try {
      created = await userMgmt.registerUser(signupConfig, userDetails);
    } catch (e) {
      const msg = String(e?.message || "");
      if (/already.*exist|duplicate|EMAIL_ID_ALREADY/i.test(msg)) {
        return res.status(409).json({
          error: "An account with this email already exists. Try signing in instead.",
        });
      }
      console.error("signup registerUser failed:", e);
      return res.status(500).json({ error: "Signup failed. Please try again." });
    }

    const u = created?.user_details || created || {};
    const newUid = String(u.user_id ?? u.zuid ?? u.id ?? "");

    // Fire-and-forget admin notification — mail failures must never block
    // the user-facing 201. Catch is inside the helper.
    notifyAdminsOfSignup(app, {
      user_id: newUid,
      first_name: u.first_name ?? first_name,
      last_name: u.last_name ?? last_name,
      email_id: u.email_id ?? email_id,
    }).catch((e) => console.warn("notifyAdminsOfSignup error (non-fatal):", e?.message));

    return res.status(201).json({
      ok: true,
      message: "Check your email to activate your account.",
      email: u.email_id ?? email_id,
    });
  } catch (err) {
    console.error("signup error:", err);
    return res.status(500).json({ error: err.message || "Signup failed" });
  }
});

// Lightweight discovery endpoint the frontend uses to populate the helper
// text on the form ("Use your @zohocorp.com email") without hardcoding the
// allowlist on the client. Server remains the source of truth.
router.get("/config", (req, res) => {
  const allowed = parseAllowedDomains();
  res.json({ allowed_domains: allowed.map((d) => `@${d}`) });
});

module.exports = router;
