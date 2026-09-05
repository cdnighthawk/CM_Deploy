# Cursor Implementation Brief — Field app: hall-dispatch new-hire packet

**Date:** 2026-09-05  
**For:** FinishWorks Field / Expo chat (`mobile/` in `CM_Deploy`, or `FinishWorksField`)  
**Website / API repo:** `CM_Deploy` (this file lives there)  
**Production API:** `https://www.usiscm.com`  
**Shared auth/chrome:** `backend/API_FIELD.md`  
**Website reference UI:** `W3CRM-v3.0-13_September_2025/gulp/src/apply/` + `gulp/src/assets/js/usis-hire-*.js`  
**Status:** Authoritative for the **phone new-hire** slice. Paste this whole file into the field/phone chat as the ticket.

---

## Paste this into the other chat (starter)

```
Implement the FinishWorks Field new-hire packet from docs/CURSOR_IMPLEMENT_FIELD_HIRE.md.

USIS gets employees dispatched from the union hall. All paperwork happens on the job, on the phone. HR does not create a packet or send an invite token.

Build in mobile/ (Expo) unless this workspace is the native Android repo — same API either way.

Do not implement People → Hiring, /api/hires, or /api/public/hire/<token>. Those are the rejected office-invite model.

Reuse existing Bearer auth and /api/v1/hr/me/* hire-wizard routes. Default hire_path to union_dispatch. Never send hire PII to Grok or any AI bus.
```

---

## 0. What this ticket is

A painter/finisher is **dispatched from the hall to a job**. The superintendent (or the worker) opens FinishWorks Field on a phone **on site** and finishes hiring paperwork before they punch.

This is **not** office hiring. HR does not click “New hire,” does not email a token, and does not fill the packet first. HR’s website job is **after** the packet exists: review the queue at `usis-hr-applications.html`, then payroll.

```
Hall dispatches worker to job
        ↓
Phone: create account (or sign in) → union dispatch path
        ↓
Phone: employment application → I-9 §1 + photos → W-4 + e-sign → union card + dispatch photos
        ↓
HR website reviews → marks Hired
        ↓
Existing User can punch when eligible
```

Website already has this flow as a **public web wizard** (`/apply.html` → `/apply/*.html`). The phone must do the **same union-dispatch checklist**, not a second data model.

---

## 1. Hard product rules

1. **Paperwork happens in the field.** Super sits the dispatch down with the company phone/tablet. No “go home and click the email.”
2. **HR does not create the packet.** Do not call `POST /api/hires`, do not build invite email, do not open `usis-people-hiring.html`.
3. **Union dispatch is the only path on the phone.** Immediately `POST /api/v1/hr/me/hire-wizard/path` with `{ "hire_path": "union_dispatch" }`. Do **not** ask “standard vs union.” Do **not** build job-offer accept screens.
4. **One person table.** After register, they are a `User` with the applicant role. Do not invent a local employee store. SSN / DOB stay on the hire row (encrypted server-side). Never write SSN into SecureStore except what the wizard GET already returns to the owner for resume-later.
5. **Bearer JWT only.** `Authorization: Bearer <access_token>`. No website session cookie. `current_user()` on the API already accepts mobile JWT, so `/api/v1/hr/me/*` works from the phone.
6. **Zero hire PII in AI.** No Grok, no ChatBot, no `aiReviewBus`, no “fill my W-4.”
7. **Reuse chrome.** Primary `#1F4E5F`, paper `#FFFFFF`, page `#F4F6F8`. Same login/refresh/logout as `API_FIELD.md`.
8. **Do not rebuild** drawings, punch, daily log, Receive, pretask, website apply HTML, or HR review.

If an older doc (`docs/hiring_onboarding_cursor.md`) says HR invites a token at `/public/hire/<token>` or “do not collect this packet in FinishWorks Field,” **this file wins**.

---

## 2. Where to build

| If the workspace is… | Do this |
|---|---|
| `CM_Deploy` | Add screens under `mobile/` (Expo Router). Follow `mobile/README.md`, `mobile/AGENTS.md` (Expo SDK 54 docs). |
| Native `FinishWorksField` | Same API + screens; match existing Android navigation. Do not add a second auth stack. |

Production `EXPO_PUBLIC_API_BASE` / Android base: `https://www.usiscm.com`.

Existing Expo home is Projects + drawings + pretask (`mobile/app/(app)/`). Add a **Hire** destination on the signed-in home (and a gated entry before projects if `hire-wizard` says the packet is not complete). Do not bury it in a project dropdown — a dispatch may not be on a job in the app yet.

---

## 3. Auth (create account on the phone)

Hall dispatches often have **no USIS login**.

### 3.1 Register

`POST /api/v1/auth/register`

```json
{ "email": "...", "password": "...", "first_name": "...", "last_name": "...", "phone": "..." }
```

- Password ≥ 8 characters.
- `USIS_ALLOW_SELF_REGISTER` is `1` on Render. If 403, show “Registration is closed — ask the office.”
- 409 = email already exists → send them to Sign in.
- Register returns a **browser session**, not JWT. Immediately:

`POST /api/v1/auth/mobile/login` `{ "email", "password", "device_label": "FinishWorks Field" }`

Save `access_token` + `refresh_token` the same way `mobile/src/api/auth.ts` already does. Then `GET /api/v1/hr/me/hire-wizard`.

### 3.2 Sign in

Existing `POST /api/v1/auth/mobile/login` · refresh · logout. Add a **Create account** link on the login screen for this ticket.

On **401**, refresh once; if that fails, wipe tokens, keep cached reads, block writes (`API_FIELD.md`).

---

## 4. Phone screens (union dispatch only)

Visible stepper, large targets, one step per screen. English. Resume later = same login.

| # | Screen | Complete when |
|---|---|---|
| 0 | Account | Signed in |
| 1 | Path (silent) | `hire_path === "union_dispatch"` |
| 2 | Employment application | Wizard `tasks.application.status === "complete"` |
| 3 | Form I-9 Section 1 | `i9.status === "signed"` |
| 4 | Form W-4 | `w4.status === "signed"` |
| 5 | Union card photo | `union_card` task complete (optional in API; **require at least one photo on the phone**) |
| 6 | Union dispatch photo | `union_dispatch` task complete (same — require one photo) |
| 7 | Done | Show “HR has your packet. You may still need to show original I-9 documents to your supervisor.” |

Lock later steps until prerequisites pass (server already returns `tasks[].locked`). If the user opens a locked step, bounce them to `firstAllowed` from the wizard payload.

**Do not build on the phone (v1):** job offer, DE-4, DE-34, direct deposit, CA pamphlets, I-9 Section 2 examiner UI, payroll zip, People directory.

I-9 Section 2 still requires a human looking at **original** documents. Photos in this app are copies only. v1 leaves §2 on the HR website. Do not auto-complete §2 from camera images.

---

## 5. API contract (already live)

All hire routes are under `/api/v1`. Prefix below is relative to that.

`GET /hr/me/hire-wizard` is the source of truth: `user`, `hire_path`, `path_selection_required`, `application`, `i9`, `w4`, `union`, `tasks`, `progress`, `review`, `disclaimer`, `official_links`.

### 5.1 Path

`POST /hr/me/hire-wizard/path`

```json
{ "hire_path": "union_dispatch" }
```

409 if already set. If an old test user is `standard`, do not try to change it in v1 — show “This account is on the office application track. Use the website or a new email.”

### 5.2 Application

`POST /hr/me/hire-application`

```json
{ "application": { "...allowed keys..." } }
```

Wrap the payload in `application`. Saving **submits for HR review** (`submitted_at`). Allowed keys (ignore extras):

`address_line1`, `address_line2`, `city`, `state`, `postal_code`, `country`, `middle_initial`, `position_applying_for`, `preferred_start_date`, `desired_compensation`, `how_heard_about_position`, `work_authorized_us`, `requires_sponsorship`, `education_level`, `education_school`, `education_degree`, `education_graduation_year`, `employment_history` (array, up to 4 employers), `skills_experience`, `certifications_licenses`, `emergency_contact_name`, `emergency_contact_phone`, `emergency_contact_relationship`, `drivers_license_number`, `drivers_license_state`, `felony_conviction`, `felony_explanation`, `signature_certified`, `signature_date`, `signature_full_name`, `prior_employer_summary`

`work_authorized_us` / `requires_sponsorship` / `felony_conviction` are yes/no style strings (`"yes"` / `"no"`). Dates as the website sends them (application prefers display dates; I-9 uses `YYYY-MM-DD`).

SSN, DOB, citizenship, filing status belong on **I-9 / W-4**, not as the main application story — the website shows that note. Prefill I-9/W-4 from wizard `i9.prefill` / `w4.prefill` after application save.

Copy field labels from `gulp/src/apply/application.html`. Keep required markers.

### 5.3 I-9 Section 1

Order: save draft → optional photos → preview → sign.

- `POST /hr/me/i9-section1` `{ "section1": { ... }, "mark_complete": true }`
- `GET /hr/me/i9-section1/preview` → PDF bytes
- `POST /hr/me/i9-section1/documents` multipart: `file` + `slot` = `list_a` \| `list_b` \| `list_c` (max 3 per slot, 10 MB, jpg/png/webp/heic/pdf)
- `POST /hr/me/i9-section1/sign` `{ "certify": true, "typed_full_name": "...", "signature_png_base64": "data:image/png;base64,..." }`

Section 1 required shape (see `backend/app/services/hr_i9_validate.py`):

- Name, address, city, state, zip, `date_of_birth` `YYYY-MM-DD`, SSN, `citizenship_status`: `citizen` \| `noncitizen_national` \| `lawful_permanent_resident` \| `alien_authorized`
- LPR: `uscis_a_number`. Alien authorized: I-94 or foreign passport + `work_authorization_expiration`
- `document_choice`: `list_a` **xor** `list_b_c`
- List A **or** List B + List C blocks: `document_type`, `issuing_authority`, `number`, `expiration` as required by validate

Sign: typed name must match the **account** first+last (`User`), not a nickname. `certify` must be JSON `true`. Signature pad PNG.

Union path: I-9 is locked until the application is submitted (`applicant_may_complete_i9_w4`).

### 5.4 W-4

- `POST /hr/me/w4` `{ "w4": { ... }, "mark_complete": true }`
- `GET /hr/me/w4/preview` → PDF
- `POST /hr/me/w4/documents` multipart `file` + `slot=supporting` (optional)
- `POST /hr/me/w4/sign` same certify / typed name / signature_png_base64 as I-9

W-4 fields (`hr_w4_validate.py`): `first_name`, `middle_initial`, `last_name`, `address`, `city`, `state`, `zip`, `ssn`, `filing_status` (`single` \| `married_joint` \| `head_of_household`), `multiple_jobs`, `higher_withholding`, `dependents_amount`, `other_income`, `deductions`, `extra_withholding`, `exempt_claim`.

Exempt cannot combine with steps 3–4 amounts or multiple-jobs checkboxes. Server signs W-4 only after I-9 is signed.

Use IRS-required step wording on the phone (do not collapse W-4 into three dropdowns). Official PDF link is in wizard `official_links.w4_pdf`.

### 5.5 Union photos

Only after W-4 is signed and path is `union_dispatch`.

- `POST /hr/me/hire-wizard/union-documents` multipart `file` + `document_kind` = `union_card` \| `union_dispatch`
- GET/DELETE file URLs are on the wizard `union.documents[]`

Phone: camera first, gallery fallback. Compress (max edge ~2560px, JPEG ~0.72) like other field photos. Never drop a photo — queue and retry.

### 5.6 Signed copies

`GET /hr/me/signed-forms/<kind>` for `i9` / `w4` after sign (download/preview). Owner only.

---

## 6. Do not call (wrong product)

| Path | Why |
|---|---|
| `/api/hires`, `/api/public/hire/<token>` | HR-created token packet. Rejected. May exist as local WIP — ignore. |
| `/hr/me/job-offer/*` | Office/standard path. Not hall dispatch. |
| Website cookie `/auth/login` | Field apps never use it. |

---

## 7. Offline

- Cache last `GET /hr/me/hire-wizard` per user (no SSN in logs).
- Queue POSTs + photo uploads. Replay must not double-sign (server 409 “already signed” = success).
- Do not queue register/login.
- Airplane mode: show cached step; block sign if the draft never reached the server.

---

## 8. Permissions / UX notes

- Applicant-only users are supposed to stay in the hire flow. If `GET /api/v1/projects` is empty or 403, **Hire still works**.
- After `review.hire_status` is `hired` or `rejected`, wizard is locked — read-only downloads.
- While `in_progress` / `submitted` / `under_review`, they may continue unsigned steps.
- Show `disclaimer` from the wizard GET on I-9 and W-4.

---

## 9. Website chat owns (not this ticket)

- HR applications queue and hire/reject
- I-9 Section 2 examiner
- Payroll / QuickBooks / DE 34
- Any new field-only APIs if register-should-return-JWT (optional nicety; v1 is register + mobile login)
- DE-4 / deposit / CA notices (not live)

If a hire route 404s, you are on the wrong base URL. Do not invent `/api/public/hire`.

---

## 10. Acceptance

1. Super opens Field → **Create account** for a dispatched worker (or they sign in) → lands in Hire, not a dead project list.
2. Path is union dispatch with no question asked.
3. Application saves; pull-to-refresh wizard shows application complete.
4. I-9: fill Section 1, photograph List B+C (or List A), certify, sign; 409 on second sign.
5. W-4: elections, preview, sign; blocked until I-9 signed.
6. Camera capture of union card and dispatch slip uploads and shows as complete.
7. Done screen tells them HR still reviews and originals may be required.
8. Same user on the **website** `/apply/complete.html` (or HR detail) sees the packet. No second row.
9. Airplane mode: photos queue; after network, one of each file, not duplicates if the server already has them.
10. No Grok, no invite token, no job-offer screen, no `/api/hires`.

---

## 11. Suggested commit (phone repo)

`feat(field): complete union-dispatch hire paperwork on the phone`

---

## 12. Files to read first (do not skip)

1. This file  
2. `backend/API_FIELD.md` (auth only)  
3. `backend/app/api/_hr_hire_wizard.py` — `GET /hr/me/hire-wizard`, application, I-9, W-4  
4. `backend/app/api/_hr_job_offer.py` — path POST only  
5. `backend/app/api/_hr_i9_documents.py`, `_hr_w4_documents.py`, `_hr_union_documents.py`  
6. `backend/app/services/hire_path.py`  
7. `gulp/src/apply/application.html`, `i9.html`, `w4.html`, `union.html`  
8. `gulp/src/assets/js/usis-hire-core.js` (step lock rules)  
9. `mobile/src/api/client.ts`, `mobile/src/api/auth.ts`, `mobile/app/(auth)/login.tsx`
