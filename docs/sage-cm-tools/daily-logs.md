# Daily logs

Status: complete
Sage CM module: Documentation
Official help: https://help.sagecm.intacct.com/Content/Modules/Documentation/DailyLog/DailyLogAddManually.htm

## Purpose

A daily log is the official narrative of one calendar day on a project: who was on site, what equipment and materials arrived, weather and site conditions, visitors, and progress activities. Superintendents use it for delay backup (weather COs), quantity tracking (especially Unit Price billing), and a dated file of photos/PDFs.

## Where it lives

- **Project Home** → Documentation → **Daily Logs** (list by date).
- **Actions → Add Manually** creates the header; sections are filled on the date’s detail form.
- **Documentation Overview** → Documentation Calendar (daily log date).
- **Mobile:** Daily logs R, E, A, D.
- **TeamLink:** not a first-class TeamLink editor; files can be linked; not listed as a portal create feature.

## Who uses it

- Superintendents and PMs create and complete logs (Recorded By = firm + PM/superintendent/engineer).
- Field staff add visitors, deliveries, equipment, workforce, weather, activities from web or mobile.
- Accounting uses Unit Price activity quantities when generating prime invoices; PO deliveries can later summarize in the PO-to-Bill wizard.
- External inspectors/owners appear as visitors, not as authors.

## Prerequisites

- Project and **Prime Contract** (required on add).
- Recorded By company/contact in the **project directory**.
- Optional: cost database labor/equipment/work items; labor and equipment timecards; POs; prime contract SOV or Unit Price items; approved COs; job cost codes; schedule tasks; Settings → Feature Settings → Documentation → **Daily Log Activity Type**.
- Project address country drives Fahrenheit vs Celsius for weather defaults (WorldWeatherOnline API).

## What the user fills out

### Header (Actions → Add Manually)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project number | No | Project picker | Defaults from current project; can update |
| Prime Contract | Yes | Prime contract | Selected on add |
| Daily Log Date | No | Date | Defaults to today |
| Recorded By Company | Yes (help: select) | Directory company | e.g. your firm |
| Recorded By Contact | Yes (help: select) | Directory contact | PM, superintendent, or engineer |
| Notes | No | Text | Header notes |
| Import Previous Day | No | Checkbox | Then pick Date and sections to copy |
| Import Date | If import | Date | Prior log day |
| Import: Activities | No | Checkbox | Prior-day activities |
| Import: Weather and Site Conditions | No | Checkbox | Prior-day weather rows |
| Import: Workforce | No | Checkbox | Prior-day workforce |
| Import: Equipment | No | Checkbox | Prior-day equipment |
| With Quantities | No | Checkbox | Applies to the sections selected above |

### Visitors (Add / Import Items)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Company | Yes (manual) | Text / directory | Manual entry or import from project directory |
| Contact | Yes (manual) | Text | Visitor name |
| Time of Visit | Yes | Time | Required on import from directory as well |
| Purpose | No | Text | Why they were on site |

### Major Material Deliveries

Reporting only — **no job cost impact**. Can import PO items (later PO-to-Bill) or cost-database work items.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Description | Yes | Text | e.g. concrete, steel, lumber |
| Quantity | Yes | Number | |
| Units | No | Text | e.g. Ea, FT, CuYd |
| Time of delivery / Receive Time | No | Time | |
| Location / Delivery Location | No | Text | Jobsite location |
| Comments | No | Text | |
| Supplier + PO (import) | If import PO | Pickers | Filter Information |

### Major Equipment (All Trades - Owned or Rented)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Company | Yes | Directory company | Owner or renter of the equipment |
| Equipment Description | Yes | Text | e.g. Bobcat, Backhoe, Dump Truck |
| Quantity | Yes | Number | Pieces on site |
| RT Hours / Hrs. Per Day | Yes (help: enter) | Number | Average run time per piece; Total RT Hours = Qty × RT Hours |

Import paths: firms/equipment last 2 weeks; equipment timecard summary for day + prime; cost-database equipment items.

### Workforce (All Trades)

Each row must include company, number of workers, and work hours. Total Hours = Quantity × Hours per worker.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Company | Yes | Directory company | Your firm or subcontractor |
| Labor Type / Code | No | Cost-database labor item | Magnifying-glass lookup |
| Quantity | Yes | Number | Headcount for that company/labor type/day |
| Hours per worker (Hrs) | Yes | Number | Average hours |
| Comments | No | Text | |

Import paths: project directory companies; firms referenced last 2 weeks; labor timecard summary for day + prime (qty = employee count, hours = total hours / count); cost-database labor items.

### Weather and Site Conditions

Defaults come from WorldWeatherOnline for the project location.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Time | No | Time | Defaults to current time |
| Temperature | No | Number | F or C from project address country; forecast default |
| Wind Conditions | No | Text | e.g. 23 mph NW; forecast default |
| Weather Conditions | No | Dropdown | Options **not enumerated in help** |
| Site Conditions | No | Dropdown | Options **not enumerated in help** |

### Activities

More general than schedule task updates. Categorize by type (org-wide) or location (project-specific, free text). Quantity required, default 0.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Activity Type | No | Dropdown | Settings → Feature Settings → Documentation → Daily Log Activity Type |
| Location | No | Text | e.g. lobby, 2nd floor, room 301 |
| Activity / Activity Description | Yes | Text | Progress narrative |
| Quantity | Yes | Number | Default 0 |
| Units | Yes with qty | Text | |
| Daily Quantity / Daily Log Qty | If import | Number | Editable on Unit Price, cost-code, and multi-type imports |

Import paths: prime contract SOV (lump sum — quantities **cannot** copy to prime invoice); prime contract Unit Price items (quantities **can** summarize into prime invoices); approved CO items; job cost codes; multiple activity types; scheduling activities (pick Schedule + tasks).

### Linked files (add wizard step 2 or Linked files on the record)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Local files | No | Upload | Up to 48 files / 500 MB; background process + email confirmation |
| Link Existing Files | No | Photos / Drawings & Specs / All Other Records | Same project/lead only |

## What Sage CM saves

- **Header record:** One daily log per project/date (list is by date). Prime contract, recorded-by company/contact, notes, daily log date.
- **Line / child records:** Visitors; major material deliveries; major equipment; workforce; weather/site condition rows; activities. Import-previous-day copies selected sections (optionally with quantities).
- **System-generated values:** Total Hours (workforce), Total RT Hours (equipment); weather defaults from API; activity quantity default 0.
- **Files / attachments:** Linked images/PDFs on the log; can link Photos library items.
- **Audit / workflow fields:** Recorded By; daily log date drives alerts. Delivery rows have no job cost effect until PO-to-Bill / invoice wizards use them.

## Statuses and lifecycle

Sage help does not name Draft/Approved for daily logs. Lifecycle:

1. Add header (date, prime, recorded by).
2. Optionally skip files, then add section rows.
3. Log appears on Documentation Calendar / Home Alerts by **daily log date**.
4. Unit Price activity quantities can later roll into prime invoices; PO deliveries into PO-to-Bill.

## Dates that drive alerts

- **Daily log date** — Documentation Calendar and Home Alerts.

Weather Time, delivery Time, and Time of Visit do not appear on the alerts table.

## Relationships

- **Upstream:** Project, prime contract, directory, cost database, timecards, POs, COs, job cost codes, schedules, weather API.
- **Downstream:** WO import “Include Daily Log Quantity” on PO items; Unit Price activities → prime invoice quantities; PO deliveries → PO-to-Bill; photos linked both ways.
- **Does not** post job cost by itself.

## Reports and exports

- Daily log detail / weather-and-site-condition summary (help cites weather summary as CO backup).
- Documentation Calendar.
- Mobile field update.

## USIS / CM_Deploy mapping

USIS `daily_reports` is one row per project per calendar date with JSON sections — similar shape, fewer structured child tables and no Sage prime-contract / recorded-by / import-previous-day / Unit Price billing.

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Daily log header + date | `daily_reports` (`project_id`, `report_date`, unique) | partial |
| Status | `daily_reports.status` `draft` \| `complete`; `completed_at` | partial (Sage status names not in help) |
| Weather | `sections.weather` (`conditions`, `temp_f`, `notes`) | partial |
| Workforce | `sections.manpower` (array) | stub |
| Equipment | `sections.equipment` (array) | stub |
| Deliveries | `sections.deliveries` (array) | stub |
| Work performed / activities | `sections.work_performed` (string) | partial |
| Delays | `sections.delays` | implemented (Sage activity/weather used for delay backup; no Delays field in Sage add help) |
| Photos | `sections.photos`; `field_photos.daily_report_id` | partial |
| Notes | `sections.notes` | partial |
| Prime contract / recorded by | none | none |
| Visitors | none | none |
| Field API | `GET/PUT /api/v1/projects/:id/daily-reports`, `/daily-reports/:id` | partial |
| Daily pretask (safety) | `daily_pretasks` / `usis-daily-pretask.html` | none (different tool; optional `daily_report_id`) |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Documentation/DailyLog/DailyLogAddManually.htm
  - https://help.sagecm.intacct.com/Content/Modules/Documentation/DailyLog/DailyLogAddManually_Visitors.htm
  - https://help.sagecm.intacct.com/Content/Modules/Documentation/DailyLog/DailyLogAddManually_MajorMaterialDeliveries.htm
  - https://help.sagecm.intacct.com/Content/Modules/Documentation/DailyLog/DailyLogAddManually_MajorEquipment.htm
  - https://help.sagecm.intacct.com/Content/Modules/Documentation/DailyLog/DailyLogAddManually_Workforce.htm
  - https://help.sagecm.intacct.com/Content/Modules/Documentation/DailyLog/DailyLogAddManually_WeatherAndSiteConditions.htm
  - https://help.sagecm.intacct.com/Content/Modules/Documentation/DailyLog/DailyLogAddManually_Activities.htm
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
- Local files reviewed
  - `backend/app/models/field_ops.py`
  - `backend/app/models/safety.py`
  - `backend/app/api/_field_routes.py`
