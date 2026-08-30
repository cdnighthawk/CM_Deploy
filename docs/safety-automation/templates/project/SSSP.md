# PROJECT SAFETY PLAN (SSSP)

**{{company.displayName}}**  
**Project:** {{project.name}} ({{project.number}})  
**Address:** {{project.address.block}}  
**Effective:** {{project.startDate}}  
**Version:** {{doc.version}}  
{{#if doc.missingFields}}**DRAFT — NOT FOR MOBILIZATION.** Missing: {{doc.missingFields}}{{/if}}

This packet is the site overlay to the company IIPP, WVPP, Heat Plan, HazCom program, and Code of Safe Practices. Those company documents are incorporated by reference and are not rewritten here.

Where a general contractor rule is stricter, follow the GC rule. Where Cal/OSHA is stricter than this packet, follow Cal/OSHA.

---

## 1. Project facts

See the Site Safety Card in this packet for people, 911 directions, hospital, muster, PPE, and climate.

**Scope on this job (generated from project flags):**

{{#if scope.interiors}}- Interiors / finishes{{/if}}
{{#if scope.ladders}}- Ladders{{/if}}
{{#if scope.scaffolds}}- Scaffolds{{/if}}
{{#if scope.aerialLifts}}- Aerial / scissor lifts{{/if}}
{{#if scope.powderActuatedTools}}- Powder-actuated tools{{/if}}
{{#if scope.silicaCuttingGrinding}}- Cutting, grinding, or drilling that can produce silica or heavy dust{{/if}}
{{#if scope.hotWork}}- Hot work{{/if}}
{{#if scope.electricalTempPower}}- Temporary power / GFCI{{/if}}
{{#if scope.occupiedBuilding}}- Occupied building{{/if}}
{{#if scope.publicInterface}}- Public or visitor interface{{/if}}
{{#if scope.confinedSpace}}- Confined space (permit required before entry){{/if}}
{{#if scope.excavation}}- Excavation / trenching (not performed unless a competent person and permit are in place){{/if}}
{{#if scope.craneOrHoist}}- Crane or hoist{{/if}}
{{#if scope.steelErection}}- Steel erection{{/if}}
{{#if scope.demolition}}- Demolition{{/if}}
{{#if scope.leadPaint}}- Lead{{/if}}
{{#if scope.asbestosPossible}}- Possible asbestos / PACM{{/if}}

Tasks not listed are **out of scope**. Do not start them until the project record is updated and this packet is regenerated.

## 2. Accountability

- Superintendent: daily inspections, PTP, toolbox every 10 working days, water and shade, stop-work.
- Employees: follow the Code of Safe Practices, wear listed PPE, report hazards and injuries the same shift.
- {{company.admin.name}}: Cal/OSHA serious-injury notification, program access, incident review.

## 3. Daily rhythm

1. Weather and site access check (heat, ice, smoke, cell service).
2. Written PTP with the crew. If the task changes in a major way, write a new PTP.
3. Confirm water, shade or cool-down area, first-aid kit, fire extinguisher, and communication.
4. Work. Any employee may stop imminent-danger work.
5. End-of-shift housekeeping.
6. Record inspections, talks, and incidents the same day.

## 4. Emergency and crisis

Follow the Site Safety Card. Building evacuation uses the muster point on that card. Medical emergency: first aid + 911. Fire: pull alarm if present, 911, muster. Severe weather: superintendent decides shelter or release.

Do not speak for the company to the media. Refer to {{company.admin.name}}.

{{#if climate.outdoorWork}}
## 5. Outdoor heat (this job)

Company Heat Illness Prevention Plan applies. On this site:

- Thermometer or reliable local temperature is checked when heat is reasonably expected.
- Shade method: canopies / building shadow / A/C trailer as available; superintendent places shade as close as practicable above 80°F.
- Observation method: superintendent or designee watches this crew (typical size {{project.crewSize}}).
- 911 caller: {{emergency.who911}}.
- Cell reliable: {{emergency.cellOk}}. Backup: {{emergency.radio}} / runner per 911 directions.
- High-heat pre-shift meeting is required at 95°F.

{{climate.notes}}
{{/if}}

{{#if climate.indoorWork}}
## 6. Indoor heat (this job)

If an indoor work area reaches 82°F, open a cool-down area below 82°F (A/C trailer or equivalent) and record the temperature on the PTP or inspection. Company indoor procedures in the Heat Plan apply.
{{/if}}

{{#if climate.coldIceSnow}}
## 7. Cold, ice, and snow (this job)

- Clear access and work platforms of ice before work.
- Wear traction devices when walking surfaces are packed snow or ice.
- Warm-up breaks in a heated space when shivering or numbness starts.
- No work on elevated surfaces that cannot be cleared or guarded.
- Vehicle and delivery plans account for road closures. Confirm hospital route daily in winter.
{{/if}}

{{#if climate.wildfireSmokePossible}}
## 8. Wildfire smoke

When air quality is unhealthy or a smoke advisory is issued, the superintendent checks current AQI, reduces heavy dust-producing work, moves work indoors if possible, and follows company respiratory rules if voluntary or required respirators are issued. Stop work if the superintendent determines the air is not safe for the task.
{{/if}}

## 9. Hazard communication (this job)

Chemicals on this job are listed in the packet chemical inventory. SDS are in the portal and/or job binder. Do not bring a new product on site until the superintendent adds it and the SDS is filed.

{{#if scope.ladders}}
## 10. Ladders

Inspect before use. Face the ladder. Three points of contact. No top two steps on stepladders. Extension ladders 3 feet above the landing and secured. No metal ladders near energized parts. Remove damaged ladders from service.
{{/if}}

{{#if scope.scaffolds}}
## 11. Scaffolds

Competent person: see Project record. Daily inspection and tag before use (green / yellow / red). Access by ladder or designed frame — no climbing cross-braces. Users trained. Each trade’s competent person inspects before that trade uses the scaffold.
{{/if}}

{{#if scope.aerialLifts}}
## 12. Aerial and scissor lifts

Only trained operators. Gate closed. Stand on the floor of the platform. Travel only per manufacturer (typically not elevated on boom lifts). Fall protection as required by the lift type and Cal/OSHA. Do not use as a crane unless the manufacturer allows it.
{{/if}}

{{#if scope.powderActuatedTools}}
## 13. Powder-actuated tools

Only carded operators. Tool unloaded until ready to fire. Inspect daily. Post the required warning sign. PPE: eyes, hearing, hard hat. Store in a locked container.
{{/if}}

{{#if scope.silicaCuttingGrinding}}
## 14. Silica and dust

Use Table 1 / wet methods, shrouded tools with HEPA, or another method that keeps dust down. No dry sweeping of silica dust. No compressed air to blow dust. Common dust masks are not silica protection. Training required before the task. Competent person: see Project record.
{{/if}}

{{#if scope.hotWork}}
## 15. Hot work

Hot-work permit before welding, cutting, or open flame. Fire watch as required. Extinguisher at the work. Screens to protect others. Flame arrestors on gas hoses.
{{/if}}

{{#if scope.electricalTempPower}}
## 16. Electrical / temporary power

GFCI on temporary 15/20-amp 120-volt construction circuits. Cords inspected; damaged cords out of service. Lockout by authorized employees only when servicing equipment.
{{/if}}

{{#if scope.occupiedBuilding}}
## 17. Occupied building

Coordinate noisy, dusty, or path-blocking work with the GC and occupants. Control debris. Do not block exits. Secure tools. Follow building fire-watch and after-hours rules.
{{/if}}

{{#if scope.publicInterface}}
## 18. Public interface

Barricade the work. High-visibility clothing when exposed to vehicles or the public. Hard-hat area posted. Visitors check in with the superintendent.
{{/if}}

{{#if scope.confinedSpace}}
## 19. Confined space

No entry until a competent person evaluates the space and a permit is issued if required. Attendant, air monitor, and rescue plan in place before entry.
{{/if}}

{{#if scope.excavation}}
## 20. Excavation

Competent person, utility locate, protective system as required. No entry into an unprotected trench.
{{/if}}

{{#if scope.asbestosPossible}}
## 21. Presumed asbestos

Stop work. Warn others. Barricade. Notify the superintendent and GC. Do not disturb. Licensed contractor only for repair or cleanup.
{{/if}}

{{#if scope.leadPaint}}
## 22. Lead

Do not disturb painted surfaces assumed to contain lead until tested or the controlling employer provides the assessment. Follow 8 CCR 1532.1 if we perform trigger tasks.
{{/if}}

## 23. Injury reporting on this job

1. First aid / 911.
2. Notify superintendent the same shift.
3. Superintendent notifies {{company.admin.name}}.
4. Complete incident, employee, and witness forms.
5. §342 call if the case is serious.

Near misses use the same incident form and are treated as prevention, not punishment.

## 24. Subcontractors to {{company.shortName}}

If {{company.shortName}} holds lower-tier contractors on this job, they receive this packet, name a competent person, submit SDS, and attend orientation before they start.

## 25. Documents in this packet

Site card · Orientation sign-off · Emergency directions · Daily PTP · Inspection checklist · Toolbox roster · Incident forms · Chemical inventory · Links to current company IIPP / WVPP / Heat / HazCom / Code of Safe Practices
