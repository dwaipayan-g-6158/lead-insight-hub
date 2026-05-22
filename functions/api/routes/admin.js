const express = require("express");
const { esc, selectAll, selectOne } = require("../lib/db");
const { getHtml, putHtml, deleteObject } = require("../lib/stratus");
const { parseDossier } = require("../lib/parser");
const {
  appendDossierRuntime,
  DOSSIER_RUNTIME_MARKER,
} = require("../lib/storeDossier");

const router = express.Router();

router.get("/users", async (req, res) => {
  try {
    const app = req.catalystApp;
    const userMgmt = app.userManagement();

    let usersList;
    if (typeof userMgmt.getAllUsers === "function") {
      usersList = await userMgmt.getAllUsers();
    } else if (typeof userMgmt.listUsers === "function") {
      usersList = await userMgmt.listUsers();
    } else {
      return res.status(500).json({ error: "userManagement list API unavailable" });
    }

    const users = Array.isArray(usersList) ? usersList : usersList?.users || [];

    const zcql = app.zcql();
    // user_roles is our canonical per-user record — pulls role AND the
    // last_seen_at timestamp stamped by the loadRole middleware on every
    // authenticated request. (Catalyst Native Auth does NOT expose a
    // last-login field on its user object, so we have to track it here.)
    const roleRows = await selectAll(zcql, `SELECT user_id, role, last_seen_at FROM user_roles`, "user_roles");
    const roleMap = new Map(roleRows.map((r) => [String(r.user_id), r.role]));
    const lastSeenMap = new Map(roleRows.map((r) => [String(r.user_id), r.last_seen_at ?? null]));

    // Map Catalyst user → admin-row shape. Catalyst Native Auth is
    // currently the only auth provider for this project; surface that as
    // an explicit "Catalyst" label so the admin table column reads as a
    // populated value instead of "—".
    // When a federated provider (Zoho SSO / Google) is wired up later,
    // pluck u.provider / u.identity_provider here.
    const out = users.map((u) => {
      const uid = String(u.user_id ?? u.zuid ?? u.id);
      const role = roleMap.get(uid) ?? "user";
      const confirmed =
        u.is_confirmed === true ||
        u.is_confirmed === "true" ||
        u.confirmed === true ||
        !!u.email_confirmed_at;
      const provider =
        u.provider ??
        u.identity_provider ??
        u.idp_name ??
        "Catalyst";
      return {
        id: uid,
        email: u.email_id ?? u.email ?? null,
        first_name: u.first_name ?? null,
        last_name: u.last_name ?? null,
        created_at: u.created_time ?? u.createdTime ?? null,
        last_sign_in_at: lastSeenMap.get(uid) ?? null,
        provider,
        confirmed,
        email_confirmed_at: confirmed
          ? u.email_confirmed_at ?? u.created_time ?? null
          : null,
        roles: [role],
        is_admin: role === "admin",
      };
    });

    res.json({ users: out, total: out.length, page: 1, perPage: out.length });
  } catch (err) {
    console.error("admin list users error:", err);
    res.status(500).json({ error: err.message || "admin list failed" });
  }
});

router.post("/users/:userId/role", async (req, res) => {
  try {
    const targetId = String(req.params.userId);
    const { role, grant } = req.body || {};
    if (!["admin", "user"].includes(role)) {
      return res.status(400).json({ error: "role must be admin or user" });
    }
    if (typeof grant !== "boolean") {
      return res.status(400).json({ error: "grant must be boolean" });
    }

    // SELECTs can ride on the user-scoped app — they work today and are
    // cheaper. WRITEs to user_roles require the admin-scope app: Catalyst
    // returns "No privileges to perform this action" otherwise (Bug 2).
    const app = req.catalystApp;
    const adminApp = req.catalystAdminApp || req.catalystApp;
    const zcql = app.zcql();
    const datastore = adminApp.datastore();

    if (role === "admin" && !grant) {
      const admins = await selectAll(
        zcql,
        `SELECT ROWID FROM user_roles WHERE role = 'admin'`,
        "user_roles",
      );
      if (admins.length <= 1) {
        return res.status(400).json({ error: "Cannot remove the last remaining admin." });
      }
    }

    const existing = await selectOne(
      zcql,
      `SELECT ROWID, role FROM user_roles WHERE user_id = '${esc(targetId)}'`,
      "user_roles",
    );

    const newRole = grant ? role : role === "admin" ? "user" : "user";

    if (existing) {
      if (existing.role !== newRole) {
        await datastore.table("user_roles").updateRow({ ROWID: existing.ROWID, role: newRole });
      }
    } else {
      await datastore.table("user_roles").insertRow({ user_id: targetId, role: newRole });
    }

    res.json({ ok: true });
  } catch (err) {
    console.error("admin setRole error:", err);
    res.status(500).json({ error: err.message || "setRole failed" });
  }
});

router.delete("/users/:userId", async (req, res) => {
  try {
    const targetId = String(req.params.userId);
    if (targetId === req.userId) {
      return res.status(400).json({ error: "You cannot delete your own account." });
    }

    // user_roles deleteRows requires admin scope (Bug 1). Without it the
    // Catalyst user delete succeeds but the row cleanup throws "No
    // privileges to perform this action", leaving an orphan row.
    const app = req.catalystApp;
    const adminApp = req.catalystAdminApp || req.catalystApp;
    const userMgmt = app.userManagement();
    const zcql = app.zcql();
    const datastore = adminApp.datastore();

    if (typeof userMgmt.deleteUser === "function") {
      await userMgmt.deleteUser(targetId);
    } else if (typeof userMgmt.delete === "function") {
      await userMgmt.delete(targetId);
    }

    const existing = await selectOne(
      zcql,
      `SELECT ROWID FROM user_roles WHERE user_id = '${esc(targetId)}'`,
      "user_roles",
    );
    if (existing) {
      // Path-param deleteRow(id) returns INVALID_URL_PATTERN when the table
      // is referenced by name; use the querystring bulk form instead.
      await datastore.table("user_roles").deleteRows([String(existing.ROWID)]);
    }

    res.json({ ok: true });
  } catch (err) {
    console.error("admin deleteUser error:", err);
    res.status(500).json({ error: err.message || "deleteUser failed" });
  }
});

router.post("/users", async (req, res) => {
  try {
    const body = req.body || {};
    const first_name = String(body.first_name || "").trim();
    const last_name = String(body.last_name || "").trim();
    const email_id = String(body.email_id || "").trim().toLowerCase();
    const role = body.role === "admin" ? "admin" : "user";

    if (!first_name) return res.status(400).json({ error: "first_name required" });
    if (!email_id || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email_id)) {
      return res.status(400).json({ error: "valid email_id required" });
    }

    // user_roles insertRow requires admin scope; on user-scoped credentials
    // it silently fails (caught as non-fatal below) and the chosen role —
    // most importantly role=admin — is never persisted, so the new user
    // shows up as "user" on next refresh.
    const app = req.catalystApp;
    const adminApp = req.catalystAdminApp || req.catalystApp;
    const userMgmt = app.userManagement();
    const datastore = adminApp.datastore();

    // Catalyst sends its standard invite email — the new user clicks the
    // link to set their own password. redirect_url is where they land
    // after activation; protocol+host auto-resolves Dev vs Prod.
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
        return res.status(409).json({ error: "A user with that email already exists." });
      }
      throw e;
    }

    const u = created?.user_details || created || {};
    const newUid = String(u.user_id ?? u.zuid ?? u.id ?? "");

    // Persist the chosen role so isAdmin works on next sign-in.
    if (newUid) {
      try {
        await datastore.table("user_roles").insertRow({ user_id: newUid, role });
      } catch (e) {
        // Non-fatal: GET /users defaults to "user" when no row exists.
        console.warn("user_roles insert failed (non-fatal):", e?.message);
      }
    }

    res.status(201).json({
      id: newUid,
      email: u.email_id ?? email_id,
      first_name: u.first_name ?? first_name,
      last_name: u.last_name ?? last_name,
      created_at: u.created_time ?? new Date().toISOString(),
      last_sign_in_at: null,
      confirmed: !!u.is_confirmed,
      email_confirmed_at: u.is_confirmed ? (u.created_time ?? null) : null,
      provider: "Catalyst",
      roles: [role],
      is_admin: role === "admin",
    });
  } catch (err) {
    console.error("admin create user error:", err);
    res.status(500).json({ error: err.message || "create user failed" });
  }
});

// One-off backfill: re-stamp every stored dossier's HTML with the trusted
// runtime block. Idempotent via DOSSIER_RUNTIME_MARKER — rows already
// carrying the marker are skipped. Safe to re-run on partial failures.
//
// Why this exists: the sanitizer historically stripped <script>, killing
// the tab/copy controller emitted by generate_report.py. The new
// sanitizer appends DOSSIER_RUNTIME_SCRIPT after stripping, but rows
// stored before that fix still carry stripped HTML.
//
// Strategy: write the patched HTML to a fresh storage_path (Date.now()
// prefix, same as parseAndStoreDossier re-uploads), then update the
// leads row to point at the new key. Stratus putObject is create-only,
// so we cannot overwrite in place; the new-path approach also gives an
// atomic switchover (no 404 window for in-flight signed URLs).
router.post("/restamp-tabs", async (req, res) => {
  try {
    const app = req.catalystApp;
    const zcql = app.zcql();
    const datastore = app.datastore();
    const limit = Math.max(1, Math.min(parseInt(req.query.limit || "500", 10), 200));
    const rows = await selectAll(
      zcql,
      `SELECT ROWID, user_id, filename, storage_path FROM leads WHERE storage_path IS NOT NULL LIMIT ${limit}`,
      "leads",
    );

    let patched = 0;
    let skipped = 0;
    let missing = 0;
    let failed = 0;
    const errors = [];

    for (const row of rows) {
      const oldKey = row.storage_path;
      if (!oldKey) {
        missing++;
        continue;
      }
      try {
        const html = await getHtml(app, oldKey);
        if (!html || typeof html !== "string") {
          missing++;
          continue;
        }
        if (html.includes(DOSSIER_RUNTIME_MARKER)) {
          skipped++;
          continue;
        }
        const patchedHtml = appendDossierRuntime(html);

        const userId = String(row.user_id || "unknown");
        const baseName = (row.filename || "dossier.html").replace(/[^a-zA-Z0-9._-]/g, "_");
        const prefix = `${userId}/${Date.now()}_restamp_`;
        const remainingChars = Math.max(50, 250 - prefix.length);
        const newKey = `${prefix}${baseName.slice(0, remainingChars)}`;

        await putHtml(app, newKey, patchedHtml);
        await datastore.table("leads").updateRow({ ROWID: row.ROWID, storage_path: newKey });
        patched++;
      } catch (err) {
        failed++;
        errors.push({ rowid: row.ROWID, key: oldKey, error: err?.message || String(err) });
      }
    }

    res.json({
      scanned: rows.length,
      patched,
      skipped,
      missing,
      failed,
      errors: errors.slice(0, 10),
    });
  } catch (err) {
    console.error("admin restamp-tabs error:", err);
    res.status(500).json({ error: err?.message || "restamp-tabs failed" });
  }
});

// One-shot backfill: re-parse stored HTML for any lead whose icp_rating
// column is NULL but whose Stratus HTML actually contains an .icp-label
// element. Idempotent — only touches rows still missing the field.
router.post("/backfill/icp", async (req, res) => {
  try {
    const app = req.catalystAdminApp || req.catalystApp;
    const zcql = app.zcql();
    const datastore = app.datastore();

    const rows = await selectAll(
      zcql,
      `SELECT ROWID, storage_path, filename, lead_name FROM leads WHERE icp_rating IS NULL`,
      "leads",
    );

    const results = [];
    for (const row of rows) {
      try {
        const html = await getHtml(app, row.storage_path);
        const parsed = parseDossier(html, row.filename || "");
        if (parsed.icp_rating) {
          await datastore.table("leads").updateRow({
            ROWID: row.ROWID,
            icp_rating: parsed.icp_rating,
            icp_reason: parsed.icp_reason,
          });
          results.push({ id: row.ROWID, lead: row.lead_name, set: parsed.icp_rating });
        } else {
          results.push({ id: row.ROWID, lead: row.lead_name, skipped: "no .icp-label in html" });
        }
      } catch (err) {
        results.push({ id: row.ROWID, lead: row.lead_name, error: err.message });
      }
    }

    res.json({
      scanned: rows.length,
      updated: results.filter((r) => r.set).length,
      results,
    });
  } catch (err) {
    console.error("backfill/icp error:", err);
    res.status(500).json({ error: err.message || "backfill failed" });
  }
});

module.exports = router;
