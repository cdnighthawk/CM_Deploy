# Copilot help search

Status: complete
Sage CM module: General browser / Help
Official help: https://help.sagecm.intacct.com/Content/ReleaseNotes/April-2026/April-2026-WhatsNew-BE-copilot-help.htm

## Purpose

Copilot is a **semantic help search** panel inside Sage Construction Management. It answers natural-language questions about Sage CM using official help, with related-article links. It is not a project-data copilot, not a report writer, and not an RFI/submittal AI reviewer. April 2026 What’s New describes it as transforming how you find help, not how you query job cost.

## Where it lives

- Any Sage CM browser page: menu bar control opens a right-side Copilot panel.
- Search box at the **bottom** of the panel.
- Available globally (official: “from any page”).
- Not a Project Home tool, not TeamLink, not called out as a mobile-app feature on the fetched Copilot page.

## Who uses it

Any signed-in Sage CM user who can open the help control. No extra security role row named Copilot on the default roles table (not listed). Administrators and field users can search the same help corpus.

## Prerequisites

- Browser Sage CM (April 2026+ what’s-new feature).
- No project, prime, or cost code required.

## What the user fills out

There is no record form.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Natural-language query | Yes | Text | Typed in the panel search box |
| Follow related-topic links | No | Links | Intelligent recommendations |

Official benefits (not extra fields): natural language understanding of Sage terminology; fewer repeat searches; related article suggestions.

## What Sage CM saves

- Header record: none. Help states it returns an answer plus links. Persistence of query history is **not confirmed in help**.
- Line / child records: none.
- System-generated values: answer text + help URLs.
- Files / attachments: none.
- Audit / workflow fields: none.

Do not model a `copilot_queries` table from Sage help — it is not documented.

## Statuses and lifecycle

Stateless Q&A session in the panel. No draft/approved.

## Dates that drive alerts

None.

## Relationships

- Upstream: Sage help corpus (help.sagecm.intacct.com topics).
- Downstream: none. Does not create RFIs, timecards, or dashboards.
- Contrast USIS: construction AI assistant module (`permissions` code `ai`) and submittal AI review (`submittal_revisions.ai_*`) are product features Sage Copilot does not provide.

## Reports and exports

None. Users can open the linked help article and use the help site’s own print if present (not documented on the Copilot page).

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| In-app help search | none | none |
| AI assistant / Grok chat | module `ai` in `permissions/modules.py`; ChatBot drawer | implemented — different purpose |
| Submittal AI review | `submittal_revisions.ai_status`, `ai_findings` | implemented — Sage-only |
| Training videos hub (human help) | https://help.sagecm.intacct.com/Content/Training/TrainingVideos.htm | Sage-only |

## Sources

- https://help.sagecm.intacct.com/Content/ReleaseNotes/April-2026/April-2026-WhatsNew-BE-copilot-help.htm
- https://help.sagecm.intacct.com/Content/ReleaseNotes/April-2026/April-2026-WhatsNew.htm
- https://help.sagecm.intacct.com/Content/Training/TrainingVideos.htm
- Local: `backend/app/permissions/modules.py`, `backend/app/models/submittal.py`
