const express = require("express");
const { selectAll } = require("../lib/db");

const router = express.Router();

// ZCQL caps 20 cols per SELECT — split into two passes and merge by ROWID.
const STATS_COLS_A = [
  "ROWID", "lead_name", "lead_title", "composite_score", "tier",
  "confidence", "icp_rating", "verdict_headline", "company",
  "fit_score", "intent_score", "timing_score", "budget_score",
  "fit_max", "intent_max", "timing_max", "budget_max", "CREATEDTIME",
];
const STATS_COLS_B = [
  // email is included so the dashboard can detect duplicate dossiers
  // (multiple snapshots of the same person re-scored over time) and
  // surface a small report_date pill to disambiguate the rows.
  "ROWID", "fit_conf", "intent_conf", "timing_conf", "budget_conf", "report_date", "email",
];

router.get("/", async (req, res) => {
  try {
    const zcql = req.catalystApp.zcql();
    // Org-wide dashboard: every authenticated viewer sees aggregate stats over all leads.
    // ZCQL needs a non-empty WHERE; use a tautology rather than dropping the clause.
    const where = `WHERE ROWID IS NOT NULL`;

    const partA = await selectAll(
      zcql,
      `SELECT ${STATS_COLS_A.join(", ")} FROM leads ${where}`,
      "leads",
    );
    const partB = await selectAll(
      zcql,
      `SELECT ${STATS_COLS_B.join(", ")} FROM leads ${where}`,
      "leads",
    );

    const indexB = new Map(partB.map((r) => [r.ROWID, r]));
    const leads = partA.map((a) => {
      const b = indexB.get(a.ROWID) || {};
      return {
        ...a,
        ...b,
        id: String(a.ROWID),
        created_at: a.CREATEDTIME ?? null,
      };
    });

    const signals = await selectAll(
      zcql,
      `SELECT signal_type, label, points FROM lead_signals
        WHERE lead_id IN (SELECT ROWID FROM leads ${where})`.replace(/\s+/g, " "),
      "lead_signals",
    ).catch(async () => {
      // Fallback: nested SELECT not supported — collect lead IDs and chunk
      const ids = partA.map((r) => r.ROWID).filter(Boolean);
      if (!ids.length) return [];
      const out = [];
      for (let i = 0; i < ids.length; i += 300) {
        const chunk = ids.slice(i, i + 300);
        const rows = await selectAll(
          zcql,
          `SELECT signal_type, label, points FROM lead_signals WHERE lead_id IN (${chunk.join(", ")})`,
          "lead_signals",
        );
        out.push(...rows);
      }
      return out;
    });

    // ZCQL returns numeric (int/decimal) columns as strings. Coerce here so
    // every consumer gets typed numbers — without this, `sum + score` in JS
    // string-concatenates ("82"+"91" = "8291", divided by 2 = 4146 instead of 87).
    const LEAD_NUM = [
      "composite_score", "fit_score", "intent_score", "timing_score", "budget_score",
      "fit_max", "intent_max", "timing_max", "budget_max",
    ];
    const SIGNAL_NUM = ["points"];
    const toNum = (v) => (v === null || v === undefined || v === "" ? null : Number(v));
    for (const l of leads) for (const k of LEAD_NUM) if (k in l) l[k] = toNum(l[k]);
    for (const s of signals) for (const k of SIGNAL_NUM) if (k in s) s[k] = toNum(s[k]);

    res.json({ leads, signals });
  } catch (err) {
    console.error("stats error:", err);
    res.status(500).json({ error: err.message || "stats failed" });
  }
});

module.exports = router;
