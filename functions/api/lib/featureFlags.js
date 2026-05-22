/**
 * Feature-flag gate for routes that should be invisible to non-allowlisted users.
 *
 * Two-tier lookup:
 *   1. `HEAVY_ALLOWLIST` env var — comma-separated ZUIDs. Survives Catalyst
 *      Cache's 48h TTL ceiling, so it works as the long-lived "owner" entry
 *      without a scheduled refresh.
 *   2. Catalyst Cache segment (env: `FEATURE_FLAGS_SEGMENT_ID`) — used when
 *      admins want to grant/revoke without a redeploy. Optional: missing
 *      segment ID just falls through to env-var-only.
 *
 * Returns false on any error — feature stays hidden by default. Never throws.
 */

function _envAllowlist() {
  const raw = process.env.HEAVY_ALLOWLIST || "";
  return new Set(raw.split(",").map((s) => s.trim()).filter(Boolean));
}

async function isHeavyAllowed(userId, catalystApp) {
  if (!userId) return false;
  const uid = String(userId);

  // Tier 1: env var (cheap, no I/O)
  if (_envAllowlist().has(uid)) return true;

  // Tier 2: Catalyst Cache segment (optional)
  const segmentId = process.env.FEATURE_FLAGS_SEGMENT_ID;
  if (!segmentId || !catalystApp) return false;
  try {
    const segment = catalystApp.cache().segment(segmentId);
    // Key shape: `heavy:<zuid>` → value "1" / "true" / any truthy string.
    // Scoped keys keep one segment usable for other future flags.
    const item = await segment.getValue(`heavy:${uid}`);
    const v = item && typeof item === "object" ? item.cache_value : item;
    const s = v == null ? "" : String(v).trim().toLowerCase();
    return s === "1" || s === "true" || s === "yes";
  } catch (_e) {
    // Cache miss or transient error — fail closed; the env-var owner still
    // works, but ad-hoc allowlist additions are temporarily unavailable.
    return false;
  }
}

module.exports = { isHeavyAllowed };
