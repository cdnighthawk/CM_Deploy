# {{project.name}} — SITE SAFETY CARD

**{{company.displayName}}**  
Packet version {{doc.version}} · Generated {{doc.generatedAt}}  
{{#if doc.missingFields}}**DRAFT — NOT FOR MOBILIZATION.** Missing: {{doc.missingFields}}{{/if}}

| | |
|---|---|
| Project no. | {{project.number}} |
| Address | {{project.address.block}} |
| Access | {{project.accessNotes}} |
| Role | {{project.role}} |
| Client / GC | {{project.client}} / {{project.gc}} |
| Dates | {{project.startDate}} – {{project.endDate}} |
| Typical crew | {{project.crewSize}} |
| Languages | {{project.languages}} |

## People

| Role | Name | Phone |
|---|---|---|
| Superintendent | {{project.superintendent.name}} | {{project.superintendent.phone}} |
| Project manager | {{project.pm.name}} | {{project.pm.phone}} |
| IIPP / Cal/OSHA caller | {{emergency.whoCalOsha}} | {{company.admin.phone}} |
| Calls 911 on this job | {{emergency.who911}} | |
| First aid | {{cp.firstAid.name}} | {{cp.firstAid.phone}} |

## Emergency

**Muster:** {{emergency.muster}}  
**Secondary:** {{emergency.muster2}}

**What to tell 911:** {{emergency.directions911}}

| Resource | Detail |
|---|---|
| Hospital | {{emergency.hospital.name}} · {{emergency.hospital.address}} · {{emergency.hospital.phone}} |
| Directions | {{emergency.hospital.directions}} |
| Clinic | {{emergency.clinic.name}} · {{emergency.clinic.phone}} |
| Fire / police | {{emergency.fire}} · {{emergency.police}} |
| Cal/OSHA district | {{emergency.calOsha.name}} · {{emergency.calOsha.phone}} |
| Cell reliable? | {{emergency.cellOk}} |
| Radio | {{emergency.radio}} |

Serious injury, illness, or death: treat the person, then {{company.admin.name}} reports to Cal/OSHA within **8 hours** (8 CCR 342).

## Climate

Outdoor work: {{climate.outdoor}} · Indoor work: {{climate.indoor}} · Elevation: {{climate.elevation}} ft  
Heat risk: {{climate.heatRisk}} · Ice/snow: {{climate.cold}} · Smoke: {{climate.smoke}}  
{{climate.notes}}

Shade present above **80°F**. High-heat procedures at **95°F**. Indoor cool-down below **82°F** when indoor heat applies.

## PPE on this job

{{project.ppeList}}

## GC / extra rules

{{project.gcRules}}

## Company programs (current versions on the portal)

IIPP · Workplace Violence Prevention Plan · Heat Illness Prevention Plan · Hazard Communication · Code of Safe Practices

Report a hazard: superintendent, or {{company.admin.phone}}, or the portal form. No retaliation.
