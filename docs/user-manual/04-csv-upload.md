# 04 — CSV Upload

If you already have a stack of dossiers as files (e.g., generated through the `/eliss` Claude skill on someone's laptop), you can bulk-import them rather than re-generating from scratch.

## When to use this

| Use upload when... | Don't use upload when... |
| --- | --- |
| You have existing HTML dossiers from `/eliss` runs | You want to research a new prospect — use **Create Dossier** instead |
| You're migrating leads from another tool that exports as CSV | You want fresh data — re-generation is better |
| You need to backfill historical leads into the dashboard | You want to bulk-research 100 new prospects — upload doesn't do that; each requires a separate Create Dossier |

## What you can upload

**Two formats:**

1. **A single HTML file** — an `ELISS_*.html` file produced by `/eliss` or the Catalyst app's renderer.
2. **A ZIP of multiple HTML files** — for batch imports.

The system parses the HTML to extract the scoring fields and DMU, then stores both the parsed data and the original HTML.

CSV-only uploads (where you have only structured data without the rendered HTML) are **not supported at v1.0.0**. The HTML is the source of truth.

## The upload flow

1. Click **Upload** in the top nav.

   > _Screenshot placeholder: `./screenshots/upload-page.png`_

2. Drag and drop your file(s) onto the dropzone, or click to browse.

3. **Optional:** Add notes to attach to all uploaded leads (e.g., "imported from Q1 2025 laptop runs").

4. Click **Upload**.

5. The page shows progress per file:
   - Green check — uploaded and parsed.
   - Yellow warning — uploaded but with parse warnings (some fields couldn't be extracted; the lead still gets created with what was parseable).
   - Red X — upload failed (file is not a valid ELISS dossier HTML). Hover for details.

6. After all files finish, the **Done** button takes you to **Leads** where the new entries appear.

## What gets parsed

The parser (`functions/api/lib/parser.js`) extracts:
- `lead_name`, `lead_title`, `company`, `email`
- `composite_score`, `tier`, all four dimension scores + maxes + confidences
- `icp_rating`, `icp_reason`
- `verdict_headline`, `verdict_insight`, `verdict_next`
- `executive_brief`
- `demo_playbook` (if present)
- `report_date`, `eliss_version`
- Top-level buying signals (positive + negative) for `lead_signals` rows.

Things the parser **does not** preserve:
- Per-section internal structure (the Tab 2 narrative is preserved as the full HTML, not broken into structured fields).
- Source URLs as a separate table — they live in the HTML.

## Naming and dedup

The upload does **not** deduplicate. If you upload the same file twice, you get two lead rows.

The filename pattern from `/eliss` is `ELISS_<Company>_<Last>_<YYYY-MM-DD>.html`. Uploaded files keep their original filename in `leads.filename`. Stratus stores them under `dossiers/<your-user-id>/<filename>`.

## File size and counts

| Limit | Value |
| --- | --- |
| Single file size | 6 MB (Express body parser ceiling) |
| ZIP size | 6 MB |
| Files per ZIP | ~50 typical (depends on individual file sizes) |
| Total upload session | Limited only by browser memory; large batches in chunks |

For larger backfills, split into multiple ZIPs and run them sequentially.

## When parsing partially fails

Sometimes the parser warns: "Couldn't extract `composite_score`." This happens when:
- The file is an older `/eliss` version with a different HTML structure.
- The file was hand-edited and the score field was changed in a way the parser doesn't recognize.

The lead is still created — with the missing fields blank. You can manually edit (admin only) or just live with the gaps. The original HTML is preserved in full so all the information is still accessible via the iframe.

## What you can't do

- Upload a `.json` dossier directly. JSON is an intermediate format; the system always reads HTML.
- Upload a PDF — the Catalyst app is HTML-only.
- Modify a lead's data after upload via re-upload — the upload always creates a new row.

## Audit trail

Each uploaded lead's `eliss_version` reflects what was in the source file. If you upload a dossier from `/eliss` v7.4.1, the lead's `eliss_version` is `7.4.1` — even if your Catalyst app is currently using v7.4.2 for new generations.

The dashboard mixes uploaded and generated leads. The **Status** column says `Done` for both — there's no visual distinction between "generated here" and "imported from upload" at v1.0.0.

## Up next

→ [Admin tasks](./05-admin-tasks.md) — for admins. Skip if you're not one.
