# Cursor prompt — paste this as the implementation spec

You are implementing DOCON safety-document automation on the company website.

Read the folder `safety-automation/` first. Do not invent new legal text. Use the Markdown templates in `templates/` and the JSON schemas in `data/`.

## Goal

When an admin creates or updates a **Project**, the site must:

1. Save a project JSON that validates against `data/project.schema.json`.
2. Merge company JSON (`data/company.seed.json`) + project JSON + computed fields.
3. Render every template in `templates/project/` and `templates/forms/` with Handlebars (or equivalent) conditionals.
4. Produce a Project Safety Packet (HTML + PDF) stored on the project.
5. Block a “Published / Ready to mobilize” status if required fields are empty (see `engine/tokens.md` incomplete-field rule). Watermark DRAFT instead.
6. Show employees the current **company** IIPP, WVPP, Heat Plan, HazCom, and Code of Safe Practices from `templates/company/` (regenerate those only when company profile or template version changes).
7. Give logged-in employees print + download of the current IIPP (Cal/OSHA electronic access).

## Do not

- Do not keep UC Davis, UAF, Chris Bardin, BlackBerry, or MSDS language.
- Do not include tower crane, pile driving, or steel chapters unless `scope.*` is true.
- Do not put incident medical detail or the violent-incident log on a public page.
- Do not treat Heat Index as the 80°F / 95°F legal trigger.

## Suggested stack (adapt to the existing repo)

- Next.js app router already on the site if present; otherwise add `/safety` routes.
- Postgres or the site’s existing DB.
- Tables: `company_profile` (single row), `safety_templates` (name, version, markdown), `projects`, `project_packets` (json_snapshot, html, pdf_url, version, status), `training_records`, `inspections`, `incidents` (restricted), `hazard_reports`.
- Handlebars or Liquid for merge.
- PDF: `@react-pdf/renderer` or Playwright print-to-PDF from the HTML packet.
- File storage: existing S3 / Supabase / Vercel blob.

## Admin UX — Create Project

Single form grouped as:

1. Identity (name, number, client, GC, role, dates)
2. Address + access notes + map pin optional
3. People (superintendent required, PM, competent persons)
4. Emergency (muster, 911 script, hospital, clinic, cell yes/no, radio, Cal/OSHA district)
5. Climate (outdoor, indoor, elevation, heat risk, ice, smoke)
6. Scope checkboxes (drive SSSP chapters)
7. PPE checklist
8. Chemicals (repeatable rows: name, manufacturer, SDS URL)
9. GC stricter rules + notes

On save: validate → merge → render → store packet → show preview → allow “Save draft” or “Publish” (publish blocked if missing required fields).

Button **Regenerate packet** on the project page.

## Employee UX

- `/safety` — company programs, current versions, download
- `/safety/projects/:id` — site card first (mobile), then packet PDFs, PTP / inspection / toolbox forms that submit back into the DB
- `/safety/report` — hazard / injury report (name optional for hazards)

## Seed

Load `data/company.seed.json` as the company profile.  
Load `data/project.mammoth.sample.json` as a sample project in DRAFT so the UI can be demoed. Hospital is prefilled; superintendent name is intentionally blank so the DRAFT watermark can be tested.

## Tests

- Creating a project with empty superintendent yields DRAFT watermark and no Publish.
- `scope.scaffolds=false` omits the scaffold chapter; `true` includes it.
- Company IIPP contains “five business days” and portal access language.
- Heat template contains 80 / 95 / 82 / 87 and does not mention UC Davis or four-employee shade.
- WVPP contains Violent Incident Log and annual review.

Implement the smallest vertical slice first: company profile + create project + HTML packet preview. Then PDF. Then employee access. Then forms that write back.
