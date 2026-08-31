# Cursor Implementation Brief — Field app: Receive and verify materials

**Date:** 2026-08-31  
**For:** FinishWorks Field / Android chat (`FinishWorksField` or `mobile/`)  
**Website / API repo:** `CM_Deploy` (this file lives there)  
**Production API:** `https://www.usiscm.com`  
**Shared contract:** `backend/API_FIELD.md`  
**Status:** Authoritative for the **phone receive** slice only.

Paste this whole file into the Android chat as the ticket. Do not invent office, buyer, or AP screens.

---

## 0. What this ticket is

USIS order tracking is three systems:

1. **When to buy** — website. Order-by date = schedule install start minus lead time on the PO. Office only.
2. **Receive and verify** — **this ticket. Phone only.**
3. **Pay** — email to `invoices@gousis.com` creates the bill. Office AP. Phone does not create bills.

If the order-by date changes, the **website** emails the supplier and tracks confirmation. The phone does not send those mails and does not track supplier confirms.

The superintendent uses the phone for two field jobs:

- **Expected deliveries** — what is coming, by date, plus carrier tracking once it has shipped.
- **Receive** — at the dock: how many showed up, condition, photos, accept / short / damaged.

Office (website) stores shipment rows on the PO (`purchase_order_shipments`: carrier, tracking number, tracking URL, promised/actual ship, estimated/actual delivery, status). The phone **reads** those rows. The phone does **not** create or edit shipments.

---

## 1. Hard scope

**Build**

- A **Receive** destination on the field app (bottom nav or a visible child row under the open job — **not a dropdown** to reach another page).
- Under Receive, a visible child row (not a dropdown): **Deliveries · Receive**.
- **Deliveries:** expected arrivals grouped by date; tracking once the shipment has shipped.
- **Receive:** dock list + qty / condition / photos for open PO qty.
- Offline cache of the deliveries list. Offline queue + retry for receipts and photos.
- Auth and chrome already used by the field app.

**Do not build**

- Order-by list, lead-time math, schedule editing
- Supplier “confirm new date” mail or status
- Bills, `invoices@gousis.com`, three-way match UI, approve pay
- Creating or editing POs, **shipments**, tracking numbers, or vendors (office enters ship/tracking)
- Website project-detail Procurement tab
- New auth, new design system, React/MUI on the website

If an API the list below is **404**, keep the UI and queue writes. `CM_Deploy` now implements the `/api/v1` field wrappers. Do **not** fall back to website cookie login or `/auth/login`.

---

## 2. Auth and chrome (already locked)

Same as `backend/API_FIELD.md`:

- `Authorization: Bearer <access_token>`
- `POST /api/v1/auth/mobile/login` · refresh · logout
- On **401**, refresh once; if that fails, wipe tokens, keep cached reads, block writes
- Tokens: primary `#1F4E5F`, paper `#FFFFFF`, page `#F4F6F8`
- Do not use the website session cookie

---

## 3. Product rules

1. **Receive happens on the phone.** Office does not “receive” for the field.
2. A receipt is qty + condition against **PO line items**. Short and damaged are first-class, not a note-only hack.
3. Photos are required for **damaged**. Optional for accept. Strongly encouraged for short.
4. Posting a receipt updates website fulfillment (`qty_received`, `fulfillment_status`). That unlocks AP to match a bill. The phone does not show pay.
5. One receipt can cover some lines only (partial).
6. `client_id` (device UUID) on create. Replay returns the existing receipt. Do not double-post on retry.
7. **Deliveries are read-only on the phone.** Expected date comes from `estimated_delivery_date` (fallback: PO `needed_on_site_date`). Tracking (carrier, number, URL, status) shows only after the shipment has shipped (`in_transit`, `out_for_delivery`, `delivered`, `exception`). Before that, show the date and “Not shipped.”
8. Tapping a tracking number / URL opens the carrier page (`tracking_url` if present). Do not scrape carriers or invent live map tracking.

---

## 4. Field API contract (what Android calls)

Website already posts receipts at `POST /api/purchase-orders/<commitment_id>/receipts` (session). **Field apps do not use that path.** Use `/api/v1` below. These wrap the same `create_purchase_order_receipt` service.

### 4.1 Dock list

`GET /api/v1/projects/:projectId/receivables`

Query: `due=today|week|open` (default `open`).

```json
{
  "entity": "project_receivables",
  "items": [
    {
      "commitment_id": "<uuid>",
      "po_number": "PO-104-012",
      "title": "Hollow metal frames",
      "vendor_name": "ABC Supply",
      "needed_on_site_date": "2026-09-12",
      "promised_ship_date": "2026-09-08",
      "fulfillment_status": "in_transit",
      "qty_ordered": "24",
      "qty_received": "8",
      "qty_open": "16",
      "line_count": 3,
      "has_open_qty": true
    }
  ]
}
```

Show only rows with `has_open_qty: true` unless the user opens history.

### 4.1b Deliveries (expected + tracking)

`GET /api/v1/projects/:projectId/deliveries`

Query: `from=YYYY-MM-DD` `to=YYYY-MM-DD` (default: today through +14 days). Include in-transit / out-for-delivery even if the estimated date is outside the window.

```json
{
  "entity": "project_deliveries",
  "items": [
    {
      "shipment_id": "<uuid>",
      "commitment_id": "<uuid>",
      "po_number": "PO-104-012",
      "title": "Hollow metal frames",
      "vendor_name": "ABC Supply",
      "expected_date": "2026-09-08",
      "shipment_status": "in_transit",
      "shipped": true,
      "carrier": "UPS",
      "tracking_number": "1Z999AA10123456784",
      "tracking_url": "https://www.ups.com/track?tracknum=1Z999AA10123456784",
      "promised_ship_date": "2026-09-04",
      "actual_ship_date": "2026-09-04",
      "estimated_delivery_date": "2026-09-08",
      "actual_delivery_date": null,
      "last_note": "Left origin facility",
      "qty_on_shipment": "12"
    }
  ]
}
```

`shipment_status` values (server): `pending` · `in_transit` · `out_for_delivery` · `delivered` · `exception` · `cancelled`. Hide `cancelled`. `shipped` is true when status is `in_transit`, `out_for_delivery`, `delivered`, or `exception`.

When `shipped` is false: show expected date, vendor, PO, “Not shipped.” Do not show a fake tracking number.

When `shipped` is true: show carrier, tracking number, status chip, and a **Track** action if `tracking_url` is set. If `tracking_url` is null but `tracking_number` is set, show the number as copyable text.

`GET /api/v1/projects/:projectId/purchase-orders/:commitmentId/receive` must also return `shipments[]` (same shipment objects) so the receive screen can show “this truck” and optionally send `shipment_id` on the receipt.

### 4.2 Receive detail

`GET /api/v1/projects/:projectId/purchase-orders/:commitmentId/receive`

```json
{
  "entity": "purchase_order_receive",
  "item": {
    "commitment_id": "<uuid>",
    "project_id": "<uuid>",
    "po_number": "PO-104-012",
    "title": "Hollow metal frames",
    "vendor_name": "ABC Supply",
    "needed_on_site_date": "2026-09-12",
    "fulfillment_status": "in_transit"
  },
  "lines": [
    {
      "id": "<commitment_line_item uuid>",
      "description": "3-0 x 7-0 HM frame",
      "quantity": "12",
      "qty_received": "4",
      "qty_open": "8",
      "unit": "EA"
    }
  ],
  "shipments": [
    {
      "shipment_id": "<uuid>",
      "shipment_status": "in_transit",
      "shipped": true,
      "carrier": "UPS",
      "tracking_number": "1Z999AA10123456784",
      "tracking_url": "https://www.ups.com/track?tracknum=1Z999AA10123456784",
      "estimated_delivery_date": "2026-09-08"
    }
  ],
  "receipts": []
}
```

### 4.3 Post a receipt

`POST /api/v1/projects/:projectId/purchase-orders/:commitmentId/receipts`

```json
{
  "client_id": "<device uuid>",
  "shipment_id": "<uuid or null>",
  "received_on": "2026-08-31",
  "packing_slip_ref": "PS-8831",
  "condition": "accepted",
  "notes": "All crates upright",
  "photo_ids": ["<photo uuid>"],
  "lines": [
    {
      "commitment_line_item_id": "<uuid>",
      "quantity": "8",
      "notes": null
    }
  ]
}
```

`condition` (required):

| Value | Meaning | Receipt status on server |
|---|---|---|
| `accepted` | Qty good, condition good | `posted` |
| `short` | Less than expected | `posted` (qty as counted) |
| `damaged` | Arrived but not usable as ordered | `posted`; notes + photos required |
| `held_unapproved` | Received but do not count toward pay yet | `draft` (existing website flag) |

Success **201**:

```json
{
  "entity": "purchase_order_receipt",
  "id": "<receipt uuid>",
  "commitment_id": "<uuid>",
  "status": "posted",
  "held_unapproved": false,
  "fulfillment_status": "partially_received",
  "created": true
}
```

Replay of the same `client_id` → **200** `{ created: false, ...same id }`.

Errors: `400` missing lines / damaged without photos; `403` no field write; `404` PO not on this project; `409` all qty already received (unless `held_unapproved`).

### 4.4 Photos (already exists)

Do **not** invent a receipt-file upload.

1. `POST /api/v1/projects/:id/photos` multipart (`file`, `taken_at`, `lat`, `lon`, `caption`)
2. Compress first (max edge 2560px, JPEG ~0.72)
3. Put returned `id` values in `photo_ids` on the receipt
4. `PATCH /api/v1/photos/:id` may later accept `commitment_id` / `receipt_id` — if 400, still send `photo_ids` on the receipt body

---

## 5. Screens

**Receive children (always visible, not a dropdown)**  
**Deliveries · Receive**

**Deliveries**  
Group by `expected_date` (Today / Tomorrow / weekday date). Each row: vendor, PO #, qty on shipment, status.  
- Not shipped: date + “Not shipped.”  
- Shipped: carrier, tracking #, status chip, **Track** (opens `tracking_url`).  
Empty: “No deliveries in this window.” Pull to refresh. Tapping a shipped/arriving row can open Receive detail for that PO.

**Receive list**  
Rows: vendor, PO #, qty left, needed-on-site. Sort: needed-on-site, then vendor. Empty: “Nothing to receive.”

**Receive detail**  
Header: vendor + PO #. If shipments exist, show the latest shipped tracking line (read-only) and pass that `shipment_id` on post when the crew is receiving that truck. Qty steppers, condition chips, notes, packing slip, photos. Primary: **Post receipt**.

**Do not** add dropdowns to jump to Drawings, RFIs, or Daily log from this flow. Those stay on the existing field destinations.

---

## 6. Offline

- Cache last dock list **and** deliveries list per `project_id`
- Queue `POST .../receipts` and photo uploads (WorkManager)
- Never drop a photo
- `client_id` is required so a retry does not create a second receipt
- After sync, refresh the dock list

---

## 7. Permissions

Treat like daily reports: user must be on the project. If GET receivables is 403, hide Receive or show “No access.” Do not show dollar amounts or invoice status even if a payload includes them.

---

## 8. Acceptance

1. Super opens a job → **Receive → Deliveries** → sees expected arrivals grouped by date. Unshipped rows have no tracking. In-transit rows show carrier + tracking and **Track** opens the carrier URL.
2. Super opens **Receive** (dock list) → sees only open-qty POs.
3. Posts a full accept with qty = open → row leaves the open list; website PO `qty_received` goes up after API exists.
4. Posts short → row stays with remaining qty.
5. Damaged without a photo → blocked on device.
6. Airplane mode: photo + receipt queue; after network, one receipt (not two). Cached deliveries still show last known tracking.
7. No Order-by, Confirm, Pay, or shipment-edit screens shipped.
8. No website session login.

---

## 9. Coordination with the website chat

`CM_Deploy` owns:

- Auto order-by (schedule − PO lead time)
- Supplier date-change email + confirmation status
- `invoices@gousis.com` → vendor bill
- Entering / updating shipment carrier, tracking, and dates on the website PO
- Implementing `/api/v1/.../receivables`, `/deliveries`, and `.../receipts` (wrapping existing shipment rows + `create_purchase_order_receipt`)

If those GET/POST routes are not live yet, Android still ships the UI against this contract. Do not call `/api/purchase-orders/...` from the phone.

---

## 10. Suggested commit (Android repo)

`feat(field): show expected deliveries and receive PO materials on the phone`
