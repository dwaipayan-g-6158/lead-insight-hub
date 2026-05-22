const PAGE = 300;

function esc(v) {
  if (v === null || v === undefined) return "NULL";
  return String(v).replace(/'/g, "''");
}

function isoOrNull(v) {
  if (!v) return null;
  if (v instanceof Date) return v.toISOString();
  return String(v);
}

// Catalyst DateTime columns accept "YYYY-MM-DD HH:MM:SS" on input
// (responses are formatted differently — "YYYY-MM-DD HH:MM:SS:sss").
function catalystDateTime(v) {
  if (!v) return null;
  const d = v instanceof Date ? v : new Date(v);
  if (Number.isNaN(d.getTime())) return null;
  const pad = (n) => String(n).padStart(2, "0");
  return (
    `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}` +
    ` ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`
  );
}

// report_date may arrive as "YYYY-MM-DD" from the parser. Promote to full datetime.
function catalystDateOnly(v) {
  if (!v) return null;
  if (typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v)) {
    return `${v} 00:00:00`;
  }
  return catalystDateTime(v);
}

async function selectAll(zcql, base, table) {
  let off = 0;
  const out = [];
  while (true) {
    const r = await zcql.executeZCQLQuery(`${base} LIMIT ${off}, ${PAGE}`);
    const rows = r.map((x) => x[table]);
    out.push(...rows);
    if (rows.length < PAGE) break;
    off += PAGE;
  }
  return out;
}

async function selectOne(zcql, base, table) {
  const r = await zcql.executeZCQLQuery(`${base} LIMIT 0, 1`);
  if (!r.length) return null;
  return r[0][table];
}

module.exports = { PAGE, esc, isoOrNull, catalystDateTime, catalystDateOnly, selectAll, selectOne };
