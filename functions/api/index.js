const express = require("express");
const { attachCatalyst, requireUser, loadRole, requireAdmin, requireSuperAdmin } = require("./lib/auth");

const app = express();
app.use(express.json({ limit: "6mb" }));
app.use(express.urlencoded({ extended: true, limit: "6mb" }));

app.use(attachCatalyst);

// BUILD_ID is bumped on every deploy via the code change itself, so we can
// confirm a fresh function image is serving traffic.
const BUILD_ID = "2026-05-28-prod-ready";
app.get("/health", (req, res) => res.json({ ok: true, ts: new Date().toISOString(), build: BUILD_ID }));

// PUBLIC routes — must be mounted BEFORE requireUser. Self-signup is the
// only path here; everything else needs an authenticated Catalyst user.
app.use("/auth/signup", require("./routes/signup"));

// All other routes require an authenticated Catalyst user
app.use(requireUser);
app.use(loadRole);

app.use("/auth", require("./routes/auth"));
app.use("/me", require("./routes/me"));
app.use("/leads", require("./routes/leads"));
app.use("/dossiers", require("./routes/dossiers"));
app.use("/stats", require("./routes/stats"));

// Super-admin-only: global generation settings. MUST be mounted before the
// `/admin` router below — Express matches `/admin` as a prefix, so the broad
// requireAdmin gate would otherwise swallow `/admin/settings` (and 404 it).
// This path is gated ONLY by requireSuperAdmin, not requireAdmin.
app.use("/admin/settings", (req, res, next) => requireSuperAdmin(req, res, next), require("./routes/settings"));

// Admin-only routes
app.use("/admin", (req, res, next) => requireAdmin(req, res, next), require("./routes/admin"));

app.use((err, req, res, next) => {
  console.error("unhandled:", err);
  res.status(500).json({ error: err?.message || "internal error" });
});

module.exports = app;
