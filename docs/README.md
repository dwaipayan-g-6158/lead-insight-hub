# Lead Insight Hub — Documentation

B2B lead-intelligence SaaS on Zoho Catalyst. Takes prospect intake (name, email, LinkedIn URL, company URL) and returns a scored ELISS dossier rendered as HTML.

This documentation set is the single source of truth for engineers, ops, sales reps, and product owners. Read the section that matches your role.

---

## I'm a... developer or IT support

Start with **Architecture**. Read in order:

1. [System Overview](./architecture/01-system-overview.md) — 5-minute tour, context diagram, environment IDs.
2. [Frontend (Vite + React)](./architecture/02-frontend-vite-react.md) — SPA routes, components, API client.
3. [API Function (Express)](./architecture/03-api-function.md) — REST surface, middleware, lib helpers.
4. [ELISS Generator — Light](./architecture/04-eliss-generator-light.md) — 7-stage Python Job Function pipeline.
5. [ELISS Generator — Heavy](./architecture/05-eliss-heavy-generator.md) — 4-subagent fan-out variant.
6. [Data Model](./architecture/06-data-model.md) — Tables, columns, foreign keys, bigint rules.
7. [Integrations](./architecture/07-integrations.md) — Anthropic, RocketReach, OTX, Stratus, Catalyst Auth.
8. [Catalyst Deployment](./architecture/08-catalyst-deployment.md) — `catalyst.json`, deploy commands, env-var discipline.
9. [`/eliss` Skill, Explained](./architecture/09-eliss-skill-explained.md) — How the upstream skill maps to this Catalyst port.
10. [Security & RBAC](./architecture/10-security-and-rbac.md) — `user_roles`, `requireAdmin`, the App Administrator gotcha.

---

## I'm a... sales rep, marketer, or end user

Start with the **User Manual**. Read in order:

- [Getting Started](./user-manual/00-getting-started.md) — sign in, dashboard tour.
- [Creating a Dossier](./user-manual/01-creating-a-dossier.md) — intake modal, polling, heavy mode.
- [Reading the Dossier](./user-manual/02-reading-the-dossier.md) — Tab 1 widgets and Tab 2 narrative.
- [Managing Leads](./user-manual/03-managing-leads.md) — list view, filters, regenerate behavior.
- [CSV Upload](./user-manual/04-csv-upload.md) — bulk-load existing dossiers.
- [Admin Tasks](./user-manual/05-admin-tasks.md) — user management (admins only).
- [Troubleshooting](./user-manual/06-troubleshooting.md) — common failures, recovery steps.
- [FAQ](./user-manual/07-faq.md) — scoring, tiers, regenerate semantics.
- [Limitations & Assumptions](./user-manual/08-limitations-and-assumptions.md) — credits, rate limits, retention.

---

## I'm on... ops, on-call, or maintenance

Start with the **Maintenance Playbook**:

- [Change-Request Process](./maintenance/01-change-request-process.md)
- [Issue Triage](./maintenance/02-issue-triage.md)
- [Testing Strategy](./maintenance/03-testing-strategy.md)
- [Deployment Runbook](./maintenance/04-deployment-runbook.md) — non-interactive `catalyst deploy` commands.
- [Rollback Procedures](./maintenance/05-rollback-procedures.md)
- [Incident Response](./maintenance/06-incident-response.md)
- [Credentials & Rotation](./maintenance/07-credentials-and-rotation.md)

---

## What changed in this release?

- [Lead Insight Hub Changelog](./changelog/lead-insight-hub-CHANGELOG.md) — the Catalyst application.
- [ELISS Skill Changelog](./changelog/ELISS-CHANGELOG.md) — the upstream `/eliss` skill, with Catalyst-port carry/defer notes.

---

## Conventions

- **Code paths** are written `dir\file.ext:line` so Ctrl-clicking in VS Code jumps straight there.
- **Mermaid blocks** render natively on GitHub and in the VS Code Markdown preview (install the *Markdown Preview Mermaid Support* extension if needed).
- **ASCII context boxes** appear in plain markdown for component-level overviews.
- **Live IDs** referenced throughout: project `31210000000133001`, dev env `60066539659`, prod env `50042142947`, ZAID `50042133518`, DC `in`.

---

## Out of scope for these docs

- Zoho CRM, Deluge, Zoho Books, or other Zoho One products — this app uses only Catalyst.
- Internal Anthropic SDK tuning beyond what `lib/synth.py` and `lib/fanout.py` expose.
- RocketReach contract or billing — see the Vendor Inventory in `07-credentials-and-rotation.md` for the contract pointer.

Need a doc that isn't here? Open a follow-up in `qa-audit-2026-05-15/FOLLOWUPS.md` or message the on-call.
