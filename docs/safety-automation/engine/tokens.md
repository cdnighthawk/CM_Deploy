# Merge tokens

Templates use Handlebars-style tokens. The generator merges `company.seed.json` + the project record + computed fields.

## Company

| Token | Source |
|---|---|
| `{{company.legalName}}` | DOCON, INC. |
| `{{company.dba}}` | US Interior Specialties |
| `{{company.shortName}}` | DOCON |
| `{{company.displayName}}` | computed: `{{legalName}} dba {{dba}}` |
| `{{company.admin.name}}` | IIPP administrator |
| `{{company.admin.title}}` | |
| `{{company.admin.phone}}` | |
| `{{company.admin.email}}` | |
| `{{company.phone.office}}` | |
| `{{company.phone.safety}}` | |
| `{{company.afterHoursPhone}}` | |
| `{{company.address.block}}` | formatted primary address |
| `{{company.languages}}` | joined list |

## Project

| Token | Source |
|---|---|
| `{{project.name}}` | |
| `{{project.number}}` | |
| `{{project.client}}` | |
| `{{project.gc}}` | |
| `{{project.role}}` | subcontractor / prime |
| `{{project.address.block}}` | formatted |
| `{{project.address.city}}` | |
| `{{project.accessNotes}}` | |
| `{{project.startDate}}` | |
| `{{project.endDate}}` | |
| `{{project.crewSize}}` | |
| `{{project.languages}}` | |
| `{{project.superintendent.name}}` | |
| `{{project.superintendent.phone}}` | |
| `{{project.pm.name}}` | |
| `{{project.pm.phone}}` | |
| `{{project.ppeList}}` | bullet list |
| `{{project.gcRules}}` | |
| `{{project.notes}}` | |

## Emergency

| Token | Source |
|---|---|
| `{{emergency.muster}}` | |
| `{{emergency.muster2}}` | |
| `{{emergency.who911}}` | |
| `{{emergency.whoCalOsha}}` | |
| `{{emergency.hospital.name}}` | |
| `{{emergency.hospital.address}}` | |
| `{{emergency.hospital.phone}}` | |
| `{{emergency.hospital.directions}}` | |
| `{{emergency.clinic.name}}` | |
| `{{emergency.clinic.phone}}` | |
| `{{emergency.fire}}` | |
| `{{emergency.police}}` | |
| `{{emergency.calOsha.name}}` | |
| `{{emergency.calOsha.phone}}` | |
| `{{emergency.cellOk}}` | Yes / No |
| `{{emergency.radio}}` | |
| `{{emergency.directions911}}` | |

## Climate / scope

| Token | Source |
|---|---|
| `{{climate.outdoor}}` | Yes / No |
| `{{climate.indoor}}` | Yes / No |
| `{{climate.elevation}}` | |
| `{{climate.heatRisk}}` | |
| `{{climate.cold}}` | Yes / No |
| `{{climate.smoke}}` | Yes / No |
| `{{climate.notes}}` | |
| `{{scope.*}}` | boolean — used in `{{#if scope.scaffolds}}` blocks |

## Computed (engine must generate)

| Token | Rule |
|---|---|
| `{{doc.title}}` | template title + project name |
| `{{doc.version}}` | increment on regenerate if company template changed or project fields changed |
| `{{doc.generatedAt}}` | ISO timestamp |
| `{{doc.effectiveDate}}` | project.startDate or today |
| `{{doc.nextReview}}` | company review rule |
| `{{doc.missingFields}}` | array of empty required fields — block “final” PDF if not empty |
| `{{calOsha.342Text}}` | static legal sentence |
| `{{heat.shadeTrigger}}` | 80°F |
| `{{heat.highHeatTrigger}}` | 95°F |
| `{{heat.indoorTrigger}}` | 82°F |
| `{{heat.indoorControlTrigger}}` | 87°F |

## Incomplete-field rule

If any of these are blank, mark the packet **DRAFT — NOT FOR MOBILIZATION**:

- project.superintendent.name + phone
- emergency.musterPoint
- emergency.hospital.name + phone
- emergency.whoCalls911
- emergency.directionsFor911
- project.address.line1 or city
