// Super-admin global generation settings. Mounted at /admin/settings behind
// requireSuperAdmin (index.js) — the only gate; regular admins get 403.
//
// Storage: a single GLOBAL-scope row in the app_settings table holding the
// full settings object as JSON in settings_json. The lowest-ROWID row is the
// singleton (mirrors the survivor rule in loadRole). Both Python generators
// read this row at job start and apply each value over their existing
// constant, so an empty/absent row is a perfect no-op.
const express = require("express");
const { selectOne, esc, catalystDateTime } = require("../lib/db");
const {
  SCHEMA,
  defaults,
  mergeWithDefaults,
  validate,
  computeWarnings,
} = require("../lib/generationSettings");

const router = express.Router();
const TABLE = "app_settings";

async function readSingleton(zcql) {
  // ORDER BY ROWID ASC pins the survivor if a duplicate ever appears.
  return selectOne(
    zcql,
    `SELECT ROWID, settings_json, updated_by, updated_at FROM ${TABLE} ORDER BY ROWID ASC`,
    TABLE,
  );
}

function parseStored(row) {
  if (!row || !row.settings_json) return {};
  try {
    const obj = JSON.parse(row.settings_json);
    return obj && typeof obj === "object" ? obj : {};
  } catch (_e) {
    return {}; // corrupt JSON => fall back to defaults rather than 500
  }
}

// GET /admin/settings — current effective settings + the full schema (so the
// UI renders labels/help/tradeoff/bounds/recommended) + live warnings.
router.get("/", async (req, res) => {
  try {
    const zcql = req.catalystApp.zcql();
    const row = await readSingleton(zcql);
    const stored = parseStored(row);
    const effective = mergeWithDefaults(stored);
    res.json({
      schema: SCHEMA,
      defaults: defaults(),
      settings: effective,
      warnings: computeWarnings(effective),
      meta: {
        updatedBy: row?.updated_by ?? null,
        updatedAt: row?.updated_at ?? null,
        hasRow: !!row,
      },
    });
  } catch (err) {
    console.error("settings GET error:", err);
    res.status(500).json({ error: err?.message || "failed to load settings" });
  }
});

// PUT /admin/settings — validate, upsert the singleton, return the new
// effective settings + warnings. Accepts a partial body (only changed keys);
// missing keys keep their stored/default value.
router.put("/", async (req, res) => {
  try {
    const { ok, errors, clean } = validate(req.body);
    if (!ok) {
      return res.status(400).json({ error: "validation failed", fields: errors });
    }

    // Writes to app_settings need the admin-scoped app (same as user_roles).
    const zcql = req.catalystApp.zcql();
    const datastore = (req.catalystAdminApp || req.catalystApp).datastore();

    const row = await readSingleton(zcql);
    const stored = parseStored(row);
    const merged = { ...stored, ...clean }; // partial update over what's stored
    const effective = mergeWithDefaults(merged);

    // Persist only known keys, in canonical (full) effective form so the row
    // is always a complete, valid object the Python side can read directly.
    const payload = {
      settings_json: JSON.stringify(effective),
      updated_by: req.user?.email_id ?? req.userId ?? "",
      updated_at: catalystDateTime(new Date()),
    };

    if (row?.ROWID) {
      await datastore.table(TABLE).updateRow({ ROWID: row.ROWID, ...payload });
    } else {
      await datastore.table(TABLE).insertRow(payload);
    }

    res.json({
      ok: true,
      settings: effective,
      warnings: computeWarnings(effective),
      meta: { updatedBy: payload.updated_by, updatedAt: payload.updated_at },
    });
  } catch (err) {
    console.error("settings PUT error:", err);
    res.status(500).json({ error: err?.message || "failed to save settings" });
  }
});

module.exports = router;
