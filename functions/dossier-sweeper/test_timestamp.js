'use strict';
/*
 * Regression test for the sweeper staleness timezone bug.
 *
 * Catalyst system columns CREATEDTIME / MODIFIEDTIME are emitted in the
 * PROJECT timezone (Asia/Kolkata, +05:30), NOT UTC. The original
 * parseCatalystTimestamp() appended "Z" (UTC), shifting every timestamp
 * +5.5h into the future, so `Date.now() - mtMs` was always negative and the
 * staleness gate `<= STALE_AFTER_MS` was always true → the ASC-sorted sweep
 * broke on the first row and NEVER marked anything stale. Orphaned dossier
 * rows hung at status=running forever.
 *
 * Run: node functions/dossier-sweeper/test_timestamp.js
 */

const assert = require('assert');

const STALE_AFTER_MS = 15 * 60 * 1000;

// ── OLD (buggy) — appended "Z" ──────────────────────────────────────────────
function parseOld(s) {
  if (!s) return null;
  const normalized = String(s).replace(' ', 'T').replace(/:(\d{3})$/, '.$1');
  const ms = new Date(normalized + 'Z').getTime();
  return Number.isNaN(ms) ? null : ms;
}

// ── NEW (fixed) — interpret in the project timezone offset ──────────────────
const CATALYST_TS_OFFSET = '+05:30'; // MUST mirror the constant in the fix
function parseNew(s) {
  if (!s) return null;
  const normalized = String(s).replace(' ', 'T').replace(/:(\d{3})$/, '.$1');
  const ms = new Date(normalized + CATALYST_TS_OFFSET).getTime();
  return Number.isNaN(ms) ? null : ms;
}

// A dossier row last modified at 16:39:30 UTC == 22:09:30 IST.
const MODIFIEDTIME_IST = '2026-06-17 22:09:30:577';
const TRUE_UTC_EPOCH = Date.parse('2026-06-17T16:39:30.577Z');

// "Now" = 40 minutes after the true modification → row IS stale (> 15 min).
const NOW = TRUE_UTC_EPOCH + 40 * 60 * 1000;

let passed = 0;
function check(name, fn) { fn(); passed++; console.log('  ✓', name); }

console.log('parseCatalystTimestamp timezone regression:');

// 1. The fixed parser yields the true UTC epoch.
check('fixed parse maps IST string to correct UTC epoch', () => {
  assert.strictEqual(parseNew(MODIFIEDTIME_IST), TRUE_UTC_EPOCH);
});

// 2. The OLD parser is 5.5h off (documents the bug).
check('old parse is +5.5h wrong', () => {
  assert.strictEqual(parseOld(MODIFIEDTIME_IST) - TRUE_UTC_EPOCH, 5.5 * 3600 * 1000);
});

// 3. With the OLD parser the staleness gate FAILS to flag a stale row.
check('OLD: stale row wrongly treated as fresh (bug reproduced)', () => {
  const age = NOW - parseOld(MODIFIEDTIME_IST);
  assert.ok(age < 0, 'old age should be negative (future)');
  assert.ok(age <= STALE_AFTER_MS, 'old gate => break => never swept');
});

// 4. With the NEW parser the staleness gate correctly flags the stale row.
check('NEW: stale row correctly detected as stale', () => {
  const age = NOW - parseNew(MODIFIEDTIME_IST);
  assert.strictEqual(age, 40 * 60 * 1000);
  assert.ok(age > STALE_AFTER_MS, 'new gate => processed as stale');
});

// 5. A genuinely fresh row (modified 2 min ago) is still left alone.
check('NEW: fresh row (2 min) not swept', () => {
  const freshIst = '2026-06-17 22:47:30:577'; // 17:17:30 UTC
  const ageFresh = NOW - parseNew(freshIst);
  assert.ok(ageFresh <= STALE_AFTER_MS, 'fresh row must not be swept');
});

console.log(`\nAll ${passed} assertions passed.`);
