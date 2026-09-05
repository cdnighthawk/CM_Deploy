# Hiring / new-hire packet mapping

Website product **USIS CM**. Staff UI is W3CRM + Bootstrap 5. Public packet is Flask, same family as `/public/rfp/<token>`.

| Concept | Repo home |
|---------|-----------|
| Employee directory | `User` in `backend/app/models/auth.py` — do not clone |
| Time / clock | `EmployeeTimeProfile` (`is_clock_eligible` false until start date) |
| Hire PII, W-4, I-9, DE-4, bank | `HirePacket` + children in `backend/app/models/hiring.py` |
| Encryption | `backend/app/services/hire_crypto.py` (Fernet / `TOKEN_ENCRYPTION_KEY`) |
| Workflow | `process_key = new_hire` in `backend/app/api/_workflow_service.py` |
| Staff API | `/api/hires` (`backend/app/api/hires_bp.py`) |
| Public API | `/api/public/hire/<token>` |
| Public page | `/public/hire/<token>` (`backend/app/templates/public/hire.html`) |
| Staff pages | `/people/hiring`, `/people/directory` → `usis-people-*.html` |
| PDFs | Working copies via `backend/app/services/hire_pdf.py` until official blanks are mapped |
| Documents | `UploadCategory.HR_HIRE` path `hr/hires/<packet_id>/` — not a project folder |
| QuickBooks | No `EmployeeAdd`. Optional ListID paste on payroll tab |
| AI | None. Hire PII is never sent to Grok / Local Llama / `aiReviewBus` |

CSV for payroll clerks includes SSN and is HR-restricted. Time-card CSV must never include SSN.
