# BuildingConnected grouped estimates — parse spec for the injection tool

Copy this file onto the other computer, or paste the whole thing into that Cursor chat.

Reviewed against live `lead_estimates` on 2026-08-25. Gold-standard job: **BMW of Sherman Oaks / job 26060**.

Do not identify the group by project name or trade. Those collide. Use the parent/child flags.

---

## What a “group” is

BuildingConnected can nest many trade invites under one parent opportunity.

- **Group / parent** = the job. One row. Has the job number.
- **Child** = one nested trade invite under that job. Same or similar name. No job number.
- **Standalone** = a normal ungrouped invite. Not a parent, no parent id.

BMW of Sherman Oaks is 1 parent + 9 children. Most children are also named “BMW of Sherman Oaks”. Three children reuse the parent trade. Two children have no trade and no due date. Name matching will pick the wrong row.

---

## Fields to parse

Same data, three namings. Normalize on ingest.

| Meaning | BC API / CSV | Postgres `lead_estimates` | Desktop queue JSON (`CloudEstimate`) |
|---|---|---|---|
| This row’s BC id | `id` | `external_id` | not on queue item — keep if you already store it |
| Parent BC id | `parentId` | `external_parent_id` | `externalParentId` |
| Is the group row | `isParent` | `is_parent` | `isParent` |
| Nested child BC ids | `groupChildren` (string array) | `group_children` | **not on the queue payload today** |
| Job number | `number` | `number` | `number` |
| Project title | `name` | `name` | `name` |
| Trade | `tradeName` | `trade_name` | `tradeName` |
| Bid Board bucket | `workflowBucket` | `workflow_bucket` | `workflowBucket` |
| Archived | `isArchived` | `is_archived` | `isArchived` |
| CRM row id | — | `id` | `leadEstimateId` |

Treat empty string `parentId` / `externalParentId` as null.

---

## Classification (use this, in this order)

```
function classify(row):
  parentId = blankToNull(row.externalParentId ?? row.parentId ?? row.external_parent_id)
  isParent = bool(row.isParent ?? row.is_parent)
  bucket   = upper(row.workflowBucket ?? row.workflow_bucket ?? "")

  if parentId is not null:
      return CHILD          # nested trade under that parent BC id
  if isParent is true:
      return GROUP          # parent / group
  if "CHILD" in bucket:
      return CHILD          # belt-and-suspenders; parentId should already be set
  return STANDALONE
```

Then:

```
childrenOf(group) = all rows whose parentId == group.external_id
```

`groupChildren` on the parent is a list of those same child BC ids. Prefer `parentId` joins; use `groupChildren` only as a checksum.

### Do not use these as the group key

- `name` — children copy the parent title (or a close variant)
- `tradeName` — parent trade is often reused on one or more children
- `dueAt` — children can share the parent due date, or have none
- “first row” / “longest name” / “most recently updated”

### Job number is a hint, not the join key

On current data, **only the parent has `number`** (e.g. `26060`). Children have `number = null`. Use that as a display/sanity check. Join children with `parentId`, not with job number, because some parents also have a null number.

---

## What the injection tool should do

1. **Inject into one job, not ten.** The work item is the **GROUP** row. Children are trades under that job, not separate jobs.
2. **Queue / picker default:** show GROUP + STANDALONE only. Hide CHILD unless the user expands a group.
   The CRM already does this (`_not_grouped_child` in `backend/app/api/_lead_estimate_queries.py`). Desktop `GetEstimateQueueAsync` already omits children. If the injection tool pulls raw BC or a full `lead_estimates` dump, it must apply the same filter.
3. **If you show children,** label them `Child · {tradeName || "(no trade)"}` and keep them under the parent. Never list them as sibling jobs named the same as the parent.
4. **Display label for a group:** `{number} · {name}` (BMW = `26060 · BMW of Sherman Oaks`).
5. **Display label for a child:** `{parent.number} / {tradeName || "untitled child"}`.
6. **Blank children** (null trade, null due) are leftover group stubs. Do not inject takeoff into them. Do not treat them as the parent.
7. **Declined / archived children** (`workflowBucket` contains `DECLINED` or `ARCHIVED`, or `isArchived = true`): skip for injection. Keep them in the family tree as inactive.
8. **Id to persist on injected output:**
   - Job / group key = parent `external_id` (BC) and parent `leadEstimateId` (CRM uuid)
   - Optional trade key = child `external_id` if the user picked a specific trade
   - Do not key the job off child ids

---

## Desktop queue payload you already receive

From `desktop_queue_item` / `CloudEstimate`:

```json
{
  "leadEstimateId": "crm-uuid",
  "name": "BMW of Sherman Oaks",
  "number": "26060",
  "tradeName": "Toilet Partitions & Bathroom Accessories",
  "submissionState": "WILL_SUBMIT",
  "workflowBucket": "ACCEPTED_ACTIVE_PARENT",
  "isParent": true,
  "externalParentId": null,
  "isArchived": false
}
```

A child of that group looks like:

```json
{
  "name": "BMW of Sherman Oaks",
  "number": null,
  "tradeName": "Lockers",
  "workflowBucket": "ACCEPTED_ACTIVE_CHILD",
  "isParent": false,
  "externalParentId": "6a8d06780da70b2d9449e018"
}
```

If `isParent === true` → this is the group.  
If `externalParentId` is a non-empty string → this is a child of that BC id.  
If both empty/false → standalone.

`groupChildren` is **not** on the queue payload. If the injection tool needs the full family, either:

- request children by `externalParentId = parent.external_id`, or
- add `groupChildren` / `externalId` to the queue serializer (CRM change; do not invent them client-side).

---

## Worked example — BMW of Sherman Oaks

**GROUP**

| Field | Value |
|---|---|
| Role | Group |
| Job # | `26060` |
| Name | BMW of Sherman Oaks |
| Trade | Toilet Partitions & Bathroom Accessories |
| BC id | `6a8d06780da70b2d9449e018` |
| `isParent` | `true` |
| `parentId` | `null` |
| Bucket | `ACCEPTED_ACTIVE_PARENT` |
| Due | 2026-09-04 |

**CHILDREN** (`parentId` = `6a8d06780da70b2d9449e018`, `isParent` = false, `number` = null)

| BC id | Name | Trade | Due | Notes |
|---|---|---|---|---|
| `6a7e39f0a48bc96cb745ccfa` | BMW of Sherman Oaks | Toilet Partitions & Bathroom Accessories | 2026-09-04 | Same name + trade as parent |
| `6a7f839b2ddeb133ecb649cd` | BMW of Sherman Oaks | Toilet Partitions & Bathroom Accessories | 2026-09-11 | Duplicate trade |
| `6a7f7b7eb95b562ed2f6c245` | BMW Sherman Oaks | Toilet Partitions & Bathroom Accessories | 2026-09-11 | Name variant |
| `6a88c46b081d0100329534d6` | BMW Service Center Sherman Oaks | 10 28 00 Toilet, Bath, and Laundry Accessories | 2026-09-11 | Different title, same group |
| `6a7f83f5b95b56f907f6ca19` | BMW of Sherman Oaks | Fire Extinguishers & Cabinets | 2026-09-11 | |
| `6a7f83836f395109cf65f0d9` | BMW of Sherman Oaks | Lockers | 2026-09-11 | |
| `6a7f83e07d0b670feb939ff3` | BMW of Sherman Oaks | Wall & Corner Guards | 2026-09-11 | |
| `6a8d06780da70b24d349e017` | BMW of Sherman Oaks | *(null)* | *(null)* | Stub — do not inject |
| `6a8d0687cdc6762ee214aa01` | BMW of Sherman Oaks | *(null)* | *(null)* | Stub — do not inject |

Parent `groupChildren` equals those nine ids.

Acceptance check: given these ten rows, the parser must return **exactly one GROUP** (`6a8d06780da70b2d9449e018`) and **nine CHILD** rows. If it returns ten jobs, the parser is wrong.

---

## Other current Will Submit groups (same rules)

| Job # | Group name | Children |
|---|---|---|
| 26058 | DMV HQ Building West Renovation | 15 |
| 26063 | City Of Corona Park Revitalization | 14 |
| 26060 | BMW of Sherman Oaks | 9 |
| 26065 | ELAC Facilities M & O Replacement | 5 |
| 26070 | Fire Station 73 New Apparatus Bay And Gym | 5 |
| 26059 | Jordan Downs 4A Apartments | 5 |
| 26068 | TASK ORDER - Renovate Admin Space B1214 | 4 |
| 26069 | PHS New Greenhouse and Agriculture Building | 3 |
| 26066 | CHPL - Delhi Twp Branch Library | 2 |
| 26064 | Christ Hospital - Postpartum Renovation L8 | 2 |
| 26073 | City Park Revitalization [Bid Set, BID] | 2 |
| 26067 | SJMC Stockton - New Tower Expansion | 2 |
| 26074 | SDUSD Holly Drive Leadership Academy GMP #1 | 2 |
| — | Fire Station 1 Living Quarters Improvements | 2 |

38 active groups exist in the database. Largest archived-or-submitted nests go to 18 children (Cape Saint Claire Fire Station, job 25271).

---

## Existing CRM filter (match this if you query raw rows)

Hide a row from the live queue when it is a child:

- `workflow_bucket` contains `CHILD`, **or**
- `is_parent` is not true **and** `external_parent_id` is non-empty

Also hide archived / declined (`is_archived`, bucket contains `ARCHIVED` or `DECLINED`, `submission_state = DECLINED`).

Live Will Submit / Undecided boards also require `due_at IS NOT NULL AND due_at >= now()`.

Canonical implementation: `backend/app/api/_lead_estimate_queries.py` (`_not_grouped_child`).

---

## Implementation checklist for the other agent

- [ ] Classify with `isParent` + `externalParentId` only
- [ ] Default picker = parents + standalones
- [ ] Children nest under parent, labeled by trade
- [ ] Inject against the parent `leadEstimateId` / parent BC `external_id`
- [ ] Skip blank stubs and declined/archived children
- [ ] Unit test the BMW 10-row fixture above (1 group, 9 children)
