# DOCON safety document automation

Drop this folder into the website repo and point Cursor at `cursor/CURSOR_PROMPT.md`.

This package replaces the old static manuals (UC Davis heat plan, university IIPP appendix, GC-sized SSSP copied job-to-job) with:

- **Company programs** written once for DOCON / US Interior Specialties
- **Project packets** generated when a job is created
- **Scope flags** so Mammoth interiors does not inherit pile-driving chapters

## Folder

```
safety-automation/
  README.md
  data/
    company.schema.json
    project.schema.json
    company.seed.json          ← edit phones/email here
    project.mammoth.sample.json
  engine/
    tokens.md
    merge-rules.md
  templates/
    company/                   ← IIPP, WVPP, heat, HazCom, Code of Safe Practices
    project/                   ← site card, SSSP, orientation
    forms/                     ← PTP, inspection, toolbox, incident, chemicals
  cursor/
    CURSOR_PROMPT.md
```

## What is generated for each new project

| File | Filled from |
|---|---|
| Site Safety Card (1 page) | All project emergency + people fields |
| Orientation acknowledgment | Project name/address |
| SSSP | Company name + only `scope.* = true` chapters |
| Daily PTP / inspection / toolbox | Project header |
| Incident packet | Project header (restricted) |
| Chemical inventory | `project.chemicals[]` |

Company IIPP / WVPP / Heat / HazCom are linked, not pasted into every SSSP.

## Required before a packet can be Published

Superintendent name + phone, muster point, hospital name + phone, who calls 911, 911 directions, project city/address.

## What you still type once

In `data/company.seed.json` add the IIPP administrator email if you want it on documents.

On each new job, the admin form is the only input. Do not hand-edit generated PDFs; change the project record and regenerate.

## Legal note

Templates follow current Cal/OSHA structure (IIPP §3203, WVPP Labor Code 6401.9, heat §3395/3396, HazCom §5194, construction §1509). They are an operations system, not a law-firm opinion. Have Cal/OSHA Consultation or counsel review the first published IIPP/WVPP/heat set before you rely on them in an inspection.
