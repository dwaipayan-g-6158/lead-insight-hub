
# ELISS Lead Intelligence Hub

A team-internal web app that stores ELISS dossier HTML files, parses each one into structured lead data, and turns the collection into a searchable dashboard with collective intelligence.

> **Note on Zoho Catalyst:** This will be built on Lovable Cloud (Supabase-based). The backend logic will be organized into clean server functions and a documented data schema so it can be ported to Catalyst Functions + Catalyst Data Store later.

---

## Pages

1. **Login** — email/password (single team).
2. **Dashboard** (home) — collective intelligence across all dossiers.
3. **Leads** — searchable, filterable list of every dossier.
4. **Lead Detail** — renders the original uploaded HTML in a sandboxed view, plus an extracted-data sidebar.
5. **Upload** — single file or bulk drag-and-drop of `.html` dossiers.

---

## Upload & parsing

- Drag-and-drop zone accepting one or many `.html` files.
- Each file is:
  - stored as-is in Storage (so the original beautiful dossier is preserved for viewing),
  - parsed server-side to extract structured fields,
  - inserted as a row in the `leads` table.
- Bulk upload shows per-file progress and a success/failure summary.
- Re-uploading the same lead (same name + company + date) updates the existing row instead of duplicating.

**Fields extracted from the HTML** (based on your sample):
- Lead name, title, company, email
- Report date, ELISS version
- Composite score (0–100), tier (HOT / WARM / COLD)
- Confidence level, ICP rating + reason
- 4 dimension scores: Fit, Intent, Timing, Budget (value, max, confidence)
- Verdict headline, executive brief, recommended next step
- Score attribution categories (compliance, security incident, AD pain, etc.)
- Compliance frameworks mentioned
- Competitive threats / trigger phrases
- What-if scenario deltas

---

## Dashboard (collective intelligence)

Top KPI strip:
- Total leads, HOT count, WARM count, COLD count, average composite score.

Charts & widgets:
- **Tier distribution** — donut of HOT / WARM / COLD.
- **Dimension averages** — bar chart of avg Fit, Intent, Timing, Budget across the pipeline.
- **Score histogram** — distribution of composite scores in 10-point buckets.
- **Pipeline by company** — table of companies with lead count + avg score, sortable.
- **Pipeline by industry / segment** — grouped bars (industry inferred from company metadata in dossier).
- **Top compliance frameworks** — frequency chart (CJIS, PCI-DSS, HB 3834, etc.) across all leads.
- **Top trigger signals** — most common attribution categories (e.g. "Security incident", "AD pain") and their average point contribution.
- **Competitive threats** — frequency of competitors mentioned (Sentinel, Defender XDR, etc.).
- **Time-based trends**:
  - New dossiers added per week.
  - Average score over time.
  - Tier mix over time (stacked area).

Each widget is clickable → drills into a filtered Leads list.

---

## Leads page

- **Search bar** (prominent, top): full-text search across lead name, company, title, email, executive brief, and verdict headline. Debounced, instant results.
- Filters: tier, score range, company, compliance framework, date range.
- Sort: score (desc default), date added, company, name.
- Each row: name, title @ company, tier pill, composite score, date, → opens Lead Detail.

---

## Lead Detail page

- Left/main: the original HTML dossier rendered in a sandboxed `<iframe srcdoc>` so it looks **exactly** like the file you uploaded (preserves the beautiful styling, SVGs, radar chart, etc.).
- Right sidebar: extracted summary (score, tier, dimensions, key signals, next step) with quick-copy buttons.
- Top bar: "Open original", "Download HTML", "Delete".

---

## Auth

- Email/password login required for all pages except `/login`.
- Single team — every signed-in user sees every lead.
- First user to sign up becomes the team (no role split needed for v1).

---

## Technical details

- **Stack**: TanStack Start + Lovable Cloud (Supabase). Tailwind + shadcn/ui for the admin UI. Recharts for charts.
- **DB tables**:
  - `leads` — one row per dossier with all extracted structured fields + `storage_path` to the raw HTML.
  - `lead_signals` — normalized rows for compliance frameworks, attribution categories, competitive threats, scenarios (one-to-many from `leads`) so dashboard aggregations are fast.
- **Storage bucket**: `dossiers` (private), HTML served to the client only after auth via signed URL or a server function that streams the file.
- **Parsing**: server function using a lightweight HTML parser (`node-html-parser`) — runs on upload, extracts via the consistent class names in the ELISS template (`verdict-score`, `verdict-tier`, `dim-name`, `dim-score`, `attr-leg-cat`, `attr-leg-pts`, `lead-name`, `lead-sub`, `exec-brief`, etc.).
- **Search**: Postgres full-text search index (`tsvector`) on lead text fields for fast, robust matching; falls back to `ilike` for partial matches on name/company.
- **Rendering original HTML**: `<iframe sandbox="allow-same-origin" srcdoc={html}>` to keep dossier scripts/styles isolated from the app shell.
- **Portability for Catalyst later**: all DB writes go through 4–5 server functions (`uploadDossier`, `listLeads`, `getLead`, `getDashboardStats`, `deleteLead`). These are pure functions over the schema and translate 1:1 to Catalyst Functions; the schema translates to Catalyst Data Store tables.

---

## Out of scope for v1

- Editing extracted data by hand (re-upload the dossier instead).
- Multi-team / per-user lead ownership.
- Pushing dossiers in via API (can be added later as `/api/public/dossier` with a shared secret).
- Exporting dashboard as PDF.
