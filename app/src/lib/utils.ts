import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Parse a date string from the Catalyst API safely across browsers.
 *
 * Catalyst emits non-ISO datetimes (e.g. "2026-05-13 03:42:25:744" with
 * colons in the ms position, or "2026-05-04 00:00:00" SQL datetime).
 * Chrome's V8 lenient-parses these; Safari/iOS WebKit's JavaScriptCore
 * returns Invalid Date, then throws RangeError on subsequent .toLocale*
 * calls. Normalize first.
 *
 * Returns null for empty input or unparseable strings so callers branch
 * explicitly instead of rendering "Invalid Date" or NaN.
 */
export function safeDate(
  input: string | number | Date | null | undefined,
): Date | null {
  if (input == null || input === "") return null;
  if (input instanceof Date) return isNaN(input.getTime()) ? null : input;
  if (typeof input === "number") {
    const d = new Date(input);
    return isNaN(d.getTime()) ? null : d;
  }
  const s = String(input).trim();
  if (!s) return null;
  // Handle the digit-based Catalyst datastore formats that Safari rejects.
  if (/^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}:\d{2}([:.]\d+)?)?$/.test(s)) {
    let iso = s
      // "YYYY-MM-DD HH:MM:SS:NNN" → "YYYY-MM-DDTHH:MM:SS.NNN"
      .replace(/^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2}):(\d+)/, "$1T$2.$3")
      // "YYYY-MM-DD HH:MM:SS" → "YYYY-MM-DDTHH:MM:SS"
      .replace(/^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})/, "$1T$2")
      // "YYYY-MM-DD" → "YYYY-MM-DDT00:00:00"
      .replace(/^(\d{4}-\d{2}-\d{2})$/, "$1T00:00:00");
    if (!/Z|[+-]\d{2}:?\d{2}$/.test(iso)) iso += "Z";
    const d = new Date(iso);
    if (!isNaN(d.getTime())) return d;
  }
  // Fallback: Catalyst's userManagement() returns English-formatted strings
  // like "May 13, 2026 07:36 PM" which both V8 and JavaScriptCore parse
  // natively. Anything else (already-ISO inputs, RFC 2822, etc.) also lands
  // here.
  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}
