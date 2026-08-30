# Document generation rules

## Packet produced on "Create Project"

Always generate:

1. `00-project-site-card.pdf` — one page, phone-readable
2. `01-orientation-acknowledgment.pdf`
3. `02-emergency-directions.pdf` (filled Appendix E)
4. `03-sssp.pdf` — only chapters where `scope.*` is true
5. `04-daily-ptp.pdf` (blank form with header filled)
6. `05-inspection-checklist.pdf` (checklist items filtered by scope)
7. `06-toolbox-roster.pdf`
8. `07-incident-packet.pdf`
9. `08-chemical-inventory.pdf` (from project.chemicals; empty table if none)

Link, do not duplicate, the current company documents:

- IIPP
- WVPP
- Heat Illness Prevention Plan (company)
- Hazard Communication Program
- Code of Safe Practices

Company docs regenerate only when company profile or template version changes — not on every project.

## Conditional SSSP chapters

| Chapter | Include when |
|---|---|
| Interiors / housekeeping / PPE | always |
| Ladders | scope.ladders |
| Scaffolds | scope.scaffolds |
| Aerial lifts | scope.aerialLifts |
| Powder-actuated tools | scope.powderActuatedTools |
| Silica | scope.silicaCuttingGrinding |
| Hot work | scope.hotWork |
| Electrical / GFCI | scope.electricalTempPower |
| Occupied building | scope.occupiedBuilding |
| Public interface | scope.publicInterface |
| Confined space | scope.confinedSpace |
| Excavation | scope.excavation |
| Crane / hoist | scope.craneOrHoist |
| Steel | scope.steelErection |
| Demolition | scope.demolition |
| Lead | scope.leadPaint |
| PACM / asbestos | scope.asbestosPossible |
| Cold / ice / snow | climate.coldIceSnow |
| Wildfire smoke | climate.wildfireSmokePossible |
| Indoor heat addendum | climate.indoorWork |
| Outdoor heat addendum | climate.outdoorWork |

Never include tower crane, pile driving, or steel erection unless the matching scope flag is true.

## Versioning

- `company_docs.version` — integer, bump when template or company seed changes
- `project_packet.version` — integer per project, bump when project fields or included chapters change
- Store generated HTML/Markdown + PDF + the JSON snapshot used to generate it
- Employees always see `status = published`; drafts stay admin-only

## Access (Cal/OSHA IIPP 5-day / electronic access)

- Published IIPP + WVPP + heat plan available to logged-in employees with print + download
- That meets “unobstructed electronic access” if employees already use the portal for work
- Project packet available to employees assigned to that project

## Privacy

Never publish on a page other employees can see:

- OSHA 301 / medical detail
- Violent incident log names
- Drug-test results
- Witness statements with personal data

Those stay in the restricted incident module.

## Regeneration

`POST /api/projects/:id/regenerate`

- Re-merge all templates with current JSON
- If required fields still missing, output watermark DRAFT
- Email superintendent a link to the new packet
