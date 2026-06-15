// Server-side contract for the super-admin global generation settings.
// The schema JSON is the single source of truth (also served to the React
// panel so its guidance text never drifts from validation). The Python
// generators do NOT read this file — they apply settings.get(key, <constant>)
// where the constant equals the `default` here, so an empty app_settings row
// is a perfect no-op.

const SCHEMA = require("./generation-settings.schema.json");

// Real Catalyst varchar widths for the clip_* columns on the `leads` table
// (mirrors COL_MAX in lib/storeDossier.js / eliss store_lead.py). A clip
// setting above the column width is pointless — the DB would silently
// truncate — so we clamp to these and warn. Verified against the live
// leads table schema.
const CLIP_COLUMN_WIDTHS = {
  clip_verdict_insight: 10000,
  clip_executive_brief: 10000,
  clip_demo_playbook: 10000,
};

const KEYS = Object.keys(SCHEMA.settings);

function defaults() {
  const out = {};
  for (const k of KEYS) out[k] = SCHEMA.settings[k].default;
  return out;
}

// Stored JSON (already validated on write) merged over defaults, so any key
// added to the schema after a row was written falls back to its default.
function mergeWithDefaults(stored) {
  const base = defaults();
  if (stored && typeof stored === "object") {
    for (const k of KEYS) {
      if (Object.prototype.hasOwnProperty.call(stored, k)) base[k] = stored[k];
    }
  }
  return base;
}

function isInt(v) {
  return typeof v === "number" && Number.isFinite(v) && Math.floor(v) === v;
}

// Validate a partial or full payload. Returns { ok, errors, clean } where
// clean holds only known keys coerced/clamped to safe values. Unknown keys
// and type mismatches are hard errors (400); clip_* over the column width is
// clamped (not an error) and surfaced as a warning by computeWarnings.
function validate(payload) {
  const errors = [];
  const clean = {};
  if (!payload || typeof payload !== "object") {
    return { ok: false, errors: [{ field: "_root", msg: "body must be an object" }], clean };
  }

  for (const [key, value] of Object.entries(payload)) {
    const spec = SCHEMA.settings[key];
    if (!spec) {
      errors.push({ field: key, msg: "unknown setting" });
      continue;
    }
    if (spec.type === "enum") {
      if (!spec.enum.includes(value)) {
        errors.push({ field: key, msg: `must be one of: ${spec.enum.join(", ")}` });
        continue;
      }
      clean[key] = value;
    } else if (spec.type === "bool") {
      if (typeof value !== "boolean") {
        errors.push({ field: key, msg: "must be a boolean" });
        continue;
      }
      clean[key] = value;
    } else if (spec.type === "int") {
      if (!isInt(value)) {
        errors.push({ field: key, msg: "must be an integer" });
        continue;
      }
      if (value < spec.min || value > spec.max) {
        errors.push({ field: key, msg: `must be between ${spec.min} and ${spec.max}` });
        continue;
      }
      let v = value;
      const colWidth = CLIP_COLUMN_WIDTHS[key];
      if (colWidth && v > colWidth) v = colWidth; // clamp, not reject
      clean[key] = v;
    } else {
      errors.push({ field: key, msg: "unsupported setting type" });
    }
  }

  // Cross-field: a thinking budget is only meaningful when its toggle is on,
  // and must leave room under the corresponding max_tokens. We validate the
  // EFFECTIVE state (payload merged over defaults) so a partial PUT that flips
  // only one of the pair is still checked.
  const eff = mergeWithDefaults({ ...defaults(), ...clean });
  checkThinking(eff, "light_thinking_enabled", "light_thinking_budget", "light_max_tokens", clean, errors);
  checkThinking(eff, "heavy_parent_thinking_enabled", "heavy_parent_thinking_budget", "heavy_parent_max_tokens", clean, errors);

  return { ok: errors.length === 0, errors, clean };
}

function checkThinking(eff, enabledKey, budgetKey, maxTokensKey, clean, errors) {
  // Only enforce when this PUT touches the toggle or the budget.
  if (!(enabledKey in clean) && !(budgetKey in clean)) return;
  if (eff[enabledKey] === true) {
    if (eff[budgetKey] < 1024) {
      errors.push({ field: budgetKey, msg: "must be at least 1024 when extended thinking is enabled" });
    } else if (eff[budgetKey] >= eff[maxTokensKey] - 1024) {
      errors.push({ field: budgetKey, msg: `must be at least 1024 below ${maxTokensKey} (${eff[maxTokensKey]})` });
    }
  }
}

// Non-blocking advisories for a fully-merged settings object. These never
// reject a save; they tell the super-admin what they're risking. The big one
// is Catalyst's 15-min (900s) Job ceiling for the Heavy pipeline.
function computeWarnings(s) {
  const warnings = [];

  // Heavy wall-clock budget: subagent fan-out (bounded by subagent timeout) +
  // parent synthesis + render must fit 900s. Opus parent and/or parent
  // thinking make the synthesis leg materially slower.
  const heavyHeadroomRisk =
    s.heavy_subagent_timeout_s >= 700 ||
    (s.heavy_subagent_timeout_s >= 600 &&
      (s.heavy_parent_model === "claude-opus-4-8" || s.heavy_parent_thinking_enabled === true));
  if (heavyHeadroomRisk) {
    warnings.push({
      field: "heavy_subagent_timeout_s",
      level: "warn",
      msg: "Heavy fan-out + parent synthesis + render must finish inside Catalyst's 15-min Job ceiling. A 600s+ subagent timeout combined with an Opus parent and/or parent extended-thinking can push a HOT dossier past it. Consider lowering the subagent timeout if Heavy jobs start timing out.",
    });
  }

  // Resume budget: when a Heavy job runs the parent IN-PROCESS, the deferral
  // deadline + the parent timeout + render must all fit under the 900s ceiling
  // with margin. If they can't, the parent is more likely to be killed mid-call
  // than cleanly deferred. (Checkpoint+resume still protects the tokens, but a
  // clean deferral is cheaper than a kill + sweep recovery.)
  if (
    s.heavy_auto_resume_enabled !== false &&
    Number(s.heavy_synthesis_deadline_s) +
      Number(s.heavy_parent_timeout_s) +
      Number(s.heavy_render_timeout_s) >
      860
  ) {
    warnings.push({
      field: "heavy_synthesis_deadline_s",
      level: "warn",
      msg: "Deferral deadline + parent timeout + render timeout exceed ~860s, leaving little margin under Catalyst's 900s ceiling. Lower the deferral deadline (or the parent timeout) so a long parent synthesis is handed to a resume job rather than killed mid-call.",
    });
  }

  if (s.heavy_parent_model === "claude-opus-4-8") {
    warnings.push({
      field: "heavy_parent_model",
      level: "info",
      msg: "Opus 4.8 on the parent synthesis produces the richest dossiers but costs ~3-5x per Heavy run versus Sonnet.",
    });
  }

  // Sharded synthesis advisories. In "auto" the gate shards only when a serial
  // parent wouldn't fit; "sharded" always parallelizes. Either way, in-process
  // sharded completion needs room under the 900s ceiling, else it defers to a
  // (waste-free) resume job.
  if (s.heavy_synthesis_mode && s.heavy_synthesis_mode !== "monolithic") {
    const reserve = Number(s.heavy_shard_timeout_s) + 240 + Number(s.heavy_render_timeout_s) + 30;
    if (s.heavy_auto_resume_enabled !== false && Number(s.heavy_synthesis_deadline_s) > 900 - reserve) {
      warnings.push({
        field: "heavy_synthesis_deadline_s",
        level: "info",
        msg: `When synthesis shards, it needs ~${reserve}s of in-job budget. With the deferral deadline at ${s.heavy_synthesis_deadline_s}s, a slow fan-out hands the shards to a (waste-free) resume job rather than finishing in one job. Lower the deadline below ${900 - reserve}s for more single-job completion.`,
      });
    }
    if (s.heavy_synthesis_mode === "sharded") {
      warnings.push({
        field: "heavy_synthesis_mode",
        level: "info",
        msg: "'sharded' runs ~10 Anthropic calls per dossier (spine + 8 shards + narrative) on EVERY run. Input is mostly prompt-cached, but output tokens rise modestly. 'auto' incurs this only when a dossier wouldn't otherwise fit the 900s ceiling.",
      });
    }
  }
  if (s.light_model === "claude-opus-4-8") {
    warnings.push({
      field: "light_model",
      level: "info",
      msg: "Opus 4.8 on the single-call Light engine costs ~3-5x with limited quality lift versus Sonnet for the Light flow.",
    });
  }

  if (s.heavy_subagent_web_search_max_uses >= 12) {
    warnings.push({
      field: "heavy_subagent_web_search_max_uses",
      level: "warn",
      msg: "12 searches per subagent (~48 across the fan-out) raises the chance a subagent hits its timeout before returning a fragment.",
    });
  }

  for (const key of Object.keys(CLIP_COLUMN_WIDTHS)) {
    if (s[key] >= CLIP_COLUMN_WIDTHS[key]) {
      warnings.push({
        field: key,
        level: "info",
        msg: `Capped at the ${CLIP_COLUMN_WIDTHS[key]}-char column width — raising further has no effect (the rendered dossier HTML is uncapped regardless).`,
      });
    }
  }

  return warnings;
}

module.exports = {
  SCHEMA,
  KEYS,
  defaults,
  mergeWithDefaults,
  validate,
  computeWarnings,
  CLIP_COLUMN_WIDTHS,
};
