# Pay applications — implementation status

**Cursor was in Plan mode**, which only allows editing markdown/canvas files. Creating `.py`, `.html`, and `.js` sources was **blocked**.

## What to do

1. **Switch the chat to Agent mode** (or turn off Plan mode for this session).
2. Send: **“Implement the AIA G702 / pay applications plan”** or **“Build pay applications”**.

Then the agent can add, in the repo:

- `backend/migrations/versions/0026_pay_applications.py` — enum `pay_application_status`, tables `pay_applications`, `pay_application_lines`
- `backend/app/models/pay_application.py` — SQLAlchemy models + `Project.pay_applications` relationship
- `backend/app/api/_pay_application_service.py` — list/get/create/patch/delete, line replace, G702 rollup (L3–L9) from SOV lines + prior apps
- `backend/app/api/v1.py` — routes under `/api/v1/projects/<id>/pay-applications`
- `backend/tests/test_pay_applications_api.py`
- `gulp/src/construction/project-detail.html` — **Invoicing** tab + pane markup
- `gulp/src/assets/js/project-detail-pay-apps.js` — Textura-style register + Summary | SoV sub-tabs
- `Plan/20. Site map and navigation.txt` — one line for the new tab
- `npx gulp build`

Authoritative product spec remains: [aia_g702_invoicing_tools_e987b004.plan.md](file:///c:/Users/CharlesDossett/.cursor/plans/aia_g702_invoicing_tools_e987b004.plan.md).
