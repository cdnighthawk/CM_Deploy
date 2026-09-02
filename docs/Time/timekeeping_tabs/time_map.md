# Time → Map — mimic plan

**Route:** `/time/map`  
**Source:** BusyBusy Map  
**Parent:** `timekeeping_web_busybusy_cursor.md` §4.5

## Job

See people who are **on the clock** and the job geofence. GPS is verification, not a tracker product.

## What the screen actually does

- Full-bleed Google map (campus / river / Greenhouse Ln area).
- Toggle Map / Satellite.
- Green pins labeled with initials: AR, SH, CC, AM.
- Right rail: “Last Known Locations,” layers Employees (on) and Projects (off), filters Employee / Position / Project.
- “Updated just now.”
- No breadcrumb trail in this shot — current points only.

Pins are last GPS on an open punch, not a driven route.

## Mimic (intent)

- Discover existing map library first (Leaflet / OSM / already-paid Google). Do not add a new billing account if one exists.
- Layers:
  1. Clocked-in people (initials or avatar + name on click).
  2. Project geofences (circle or polygon) — off by default on the company map, on by default when opened from Field → Time.
  3. Selected employee + date **pings** (polyline of `TimeBreadcrumb`). Label it “pings,” never “route.”
- Click pin → Live row / card.
- Off-clock people are **not** on the map. `track_off_clock` stays false.
- Geofence editor is on the **project** (Field → Time or Job information), not a drawing tool on this company map.

## Do not copy

- Assuming Google Maps.
- Projects layer as a dump of every historic job pin.
- Live-tracking animation.
- Auto clock-in when a pin enters a fence.
- Crow-flies path presented as the drive.

## Acceptance

- Four open punches with GPS → four pins after a poll.
- Clock-out removes the pin on next poll.
- Breadcrumb request for a date while they were out returns empty.
- Block-mode fence still does not punch them; it only 409s a mobile clock-in unless supervisor override.
