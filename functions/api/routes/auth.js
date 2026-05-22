const express = require("express");
const { esc, selectAll } = require("../lib/db");

const router = express.Router();

// The AuthProvider fires `postSignupBootstrap` on every fresh login. React
// StrictMode can double-invoke that effect, and a user opening the app in
// two tabs simultaneously will issue parallel POSTs — both pass an existence
// check and both insert, leaving two rows per user_id. This handler is
// self-healing: it always reduces user_roles to one row per user_id within
// the request, regardless of how many concurrent calls produced duplicates.
router.post("/post-signup", async (req, res) => {
  try {
    const zcql = req.catalystApp.zcql();
    const datastore = req.catalystApp.datastore();
    const userId = req.userId;

    const dedup = async () => {
      const rows = await selectAll(
        zcql,
        `SELECT ROWID, role FROM user_roles WHERE user_id = '${esc(userId)}' ORDER BY ROWID ASC`,
        "user_roles",
      );
      if (rows.length > 1) {
        const dupeIds = rows.slice(1).map((r) => String(r.ROWID));
        // Best-effort: surviving row is the earliest ROWID — whichever concurrent
        // insert won. If a dupe was already swept by a sibling request, the
        // delete is a no-op; swallow errors so we never 500 over hygiene.
        await datastore
          .table("user_roles")
          .deleteRows(dupeIds)
          .catch((e) => console.warn("post-signup dedup delete failed:", e.message));
      }
      return rows[0] || null;
    };

    const pre = await dedup();
    if (pre) return res.json({ role: pre.role, alreadySet: true });

    // No row yet. The very first signup in the project becomes admin.
    const all = await selectAll(zcql, `SELECT ROWID FROM user_roles`, "user_roles");
    const role = all.length === 0 ? "admin" : "user";

    await datastore.table("user_roles").insertRow({ user_id: userId, role });

    // Read-back dedup: a parallel request may have inserted between our
    // existence check and insert. Collapse any duplicates we created.
    const post = await dedup();
    res.json({ role: post?.role ?? role, alreadySet: false });
  } catch (err) {
    console.error("post-signup error:", err);
    res.status(500).json({ error: err.message || "post-signup failed" });
  }
});

module.exports = router;
