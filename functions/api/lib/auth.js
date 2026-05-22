const catalyst = require("zcatalyst-sdk-node");
const { selectOne, selectAll, catalystDateTime } = require("./db");

// Throttle for the per-user last_seen_at write. Authenticated routes hit
// this middleware on every request — the pill alone polls every 10s — so
// without throttling we'd hammer the Data Store. 60s resolution is more
// than enough for an "active in the last X minutes" admin view.
const LAST_SEEN_THROTTLE_MS = 60_000;

function attachCatalyst(req, res, next) {
  try {
    req.catalystApp = catalyst.initialize(req);
    // Admin-scope app for Stratus + Data Store writes that require elevated access.
    req.catalystAdminApp = catalyst.initialize(req, { scope: "admin" });
    next();
  } catch (err) {
    console.error("catalyst.initialize failed:", err);
    res.status(500).json({ error: "Catalyst init failed" });
  }
}

async function requireUser(req, res, next) {
  try {
    const userMgmt = req.catalystApp.userManagement();
    const user = await userMgmt.getCurrentUser();
    if (!user || !user.user_id) {
      return res.status(401).json({ error: "unauthenticated" });
    }
    req.userId = String(user.user_id);
    req.user = user;
    next();
  } catch (err) {
    console.error("requireUser failed:", err);
    res.status(401).json({ error: "unauthenticated" });
  }
}

async function loadRole(req, res, next) {
  try {
    const zcql = req.catalystApp.zcql();
    // ORDER BY ROWID ASC pins the survivor when duplicate user_roles rows
    // exist (post-signup race elsewhere de-dupes but can't guarantee it).
    // Matches the surviving-row rule in functions/api/routes/auth.js.
    // We also pull ROWID + last_seen_at so we can stamp activity below
    // without a second SELECT.
    const row = await selectOne(
      zcql,
      `SELECT ROWID, role, last_seen_at FROM user_roles WHERE user_id = '${req.userId}' ORDER BY ROWID ASC`,
      "user_roles",
    );

    // Catalyst platform admin (App Administrator in the Catalyst Console)
    // is used ONLY as a bootstrap fallback when no user_roles row exists —
    // the self-heal block below then writes the row so subsequent calls
    // stop relying on this path. Once a row exists, user_roles is the
    // single source of truth: a Catalyst "App Administrator" with an
    // explicit user_roles.role = 'user' is treated as a user.
    const platformRoleName =
      req.user?.role_details?.role_name ||
      req.user?.role_name ||
      "";
    const isPlatformAdmin = /admin/i.test(String(platformRoleName));

    req.role = row?.role ?? (isPlatformAdmin ? "admin" : "user");
    req.isAdmin = req.role === "admin";

    const nowStamp = catalystDateTime(new Date());
    const adminDatastore = (req.catalystAdminApp || req.catalystApp).datastore();

    if (isPlatformAdmin && !row) {
      // Self-heal: a verified platform admin with no user_roles row gets
      // one written so subsequent calls (and the Admin UI's "Admins"
      // count, role badges) reflect reality. Cannot privilege-escalate
      // since the write only fires when platform role already grants admin.
      // Seed last_seen_at on the same write — saves an immediate update.
      try {
        await adminDatastore
          .table("user_roles")
          .insertRow({ user_id: req.userId, role: "admin", last_seen_at: nowStamp });
      } catch (e) {
        console.warn("loadRole self-heal insert failed:", e?.message);
      }
    } else if (row?.ROWID) {
      // Stamp last_seen_at, throttled. Date.parse handles both ISO and
      // Catalyst's "May 15, 2026 11:12 PM" format on V8 — if either is
      // unparseable we treat it as 0 and write anyway. Fire-and-forget
      // so the middleware doesn't block on a Data Store roundtrip; a
      // missed write is harmless, the next call will catch up.
      const last = row.last_seen_at ? Date.parse(String(row.last_seen_at)) : 0;
      if (!last || (Date.now() - last) > LAST_SEEN_THROTTLE_MS) {
        adminDatastore
          .table("user_roles")
          .updateRow({ ROWID: row.ROWID, last_seen_at: nowStamp })
          .catch((e) => console.warn("last_seen_at update failed:", e?.message));
      }
    }

    next();
  } catch (err) {
    console.error("loadRole failed:", err);
    res.status(500).json({ error: "role lookup failed" });
  }
}

async function requireAdmin(req, res, next) {
  if (!req.isAdmin) return res.status(403).json({ error: "admin role required" });
  next();
}

module.exports = { attachCatalyst, requireUser, loadRole, requireAdmin };
