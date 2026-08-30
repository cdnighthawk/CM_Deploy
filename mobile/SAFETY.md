# Phone app — Daily Pre-Task Safety Plan

Implement the same Appendix E form the website now uses. Do **not** invent a second payload. Shared contract: `backend/API_FIELD.md` (Daily pretask) and `mobile/src/api/safety.ts`.

Paper source: USIS “Daily Pre-Task Safety Plan” (SSSP Appendix E). Sample fields: date, company (DOCON, INC), area of work, five pre-start checks, task / hazard / control rows, near miss, permits, concerns, quality follow-up, attendee print+signature, supervisor print+signature.

## When to show it

On the **project home**, add a **Daily pretask** card (same weight as Drawings). Opening it loads **today’s** plan for the signed-in crew lead:

`GET /api/v1/projects/:id/daily-pretasks?date=YYYY-MM-DD`

That get-or-creates a draft. Do not create a second row for the same project + date + user.

## Screen layout (mobile-first)

Single scroll. Large tap targets. Match website sections in this order:

1. Header: job name/number, date picker (default today), company name, area of work.
2. **Prior to the start of a task** — five checkboxes (`checklist` keys below).
3. **Task analysis** — repeating rows: JHA checkbox, Task, Hazards, Steps / tools. Start with 4 empty rows. **Add task** button.
4. Near miss Yes/No + notes. Required permits. Items/concerns. Previous-day quality. Present items.
5. **Attendees** — print name + signature. **Add attendee**.
6. Supervisor printed name + signature.
7. Sticky footer: **Save draft** and **Submit plan**.

## Signatures

Website accepts a typed name. On the phone:

- Use a signature pad (stroke → PNG data URL) for `attendees[].signature` and `supervisor_signature`.
- Also store `print_name` / `supervisor_name` as text.
- If the pad is skipped, fall back to typed name so a crew can still submit.

## Offline

- Queue PUT / submit like daily reports.
- Generate a `client_id` UUID on first local draft; send it on GET (`?client_id=`) and POST so retries do not duplicate.
- Last-write-wins on a **draft**. After `status: submitted`, the server returns **403** for field users — show “Submitted and locked” and disable edits.
- Dedupe key: `(project_id, work_date, crew_lead)` — the signed-in user is the crew lead.

## Submit rules (server-enforced)

Block Submit until:

- All five checklist boxes are true
- At least one task row has `task` text
- `area_of_work` is filled
- `supervisor_name` is filled

Show the server `error` string if submit fails.

## Auth / modules

Use the existing mobile Bearer tokens. The user needs **projects** access for get-or-create, and **safety or projects write** to save/submit. A 403 on `/api/v1/safety/summary` is OK on the phone — that list is for the office hub.

## Do not build in this pass

JHA library, incident wizard, AI photo review, PDF export that clones the paper layout. Those come later. The field job is: **file today’s Appendix E plan and keep it offline-safe**.

## Expo starting point

`mobile/src/api/safety.ts` is the typed client. Add `app/(app)/projects/[id]/pretask.tsx` and link it from the project home. Keep Expo API usage aligned with [SDK 54 docs](https://docs.expo.dev/versions/v54.0.0/).
