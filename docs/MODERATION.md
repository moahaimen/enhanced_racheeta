# Moderation and Contact-Information Protection

Owner decision: no direct phone/e-mail/WhatsApp/Telegram exchange through
recruitment content. Communication stays inside Racheeta.

## Detector (`backend/apps/moderation/contact_leak.py`)

`ContactLeakDetector.scan(text) -> list[Finding(category, excerpt)]` with
categories:

| Category | What it catches |
| --- | --- |
| PHONE | Iraqi and international numbers, Arabic-Indic and Persian digits, separators (spaces, dashes, dots, parentheses), `+964`, `00964`, `07xx` |
| EMAIL | RFC-like addresses, also with spelled-out `(at)` / `[dot]` |
| WHATSAPP | "whatsapp", "واتساب", "واتس", `wa.me` links |
| TELEGRAM | "telegram", "تلغرام", "تيليجرام", `t.me`, `@handle` next to the word |
| URL | http(s) links and bare domains (e-mail domains are removed first so an address is reported once as EMAIL) |

`validate_no_contact_info(value)` raises a DRF `ValidationError` with code
`contact_information_not_allowed`; the envelope carries the code under
`codes.<field>` and the message lists the categories found.

## Where it is enforced

| Content | Fields |
| --- | --- |
| Employer | `description` |
| Job post | `title`, `description`, `responsibilities`, `requirements`, `workplace_text`, `detailed_specialty` |
| Seeker profile | `professional_title`, `professional_summary`, `detailed_specialty`; experience `description`; credential `name`/`issuer`; skill names |
| Application | `cover_text` |
| Interview request | `location_text`, `note` (ONLINE meeting details are exchanged only inside Racheeta) |
| Invitation | `message` |
| Recruitment message | `body` |
| Saved candidate | `note` |

Validation happens in the serializers (write time), so leaked contact data is
never stored. As a second line, `submit_job_for_review` re-scans the job and
persists `moderation_flags` (field, category, excerpt) which the admin console
shows as "possible contact details" before approval.

## Human review

- Jobs are published only after Super Admin approval (`PENDING_ADMIN_REVIEW → PUBLISHED`), with reject/suspend/restore and a note to the employer.
- Employers are verified by Super Admin; recruitment can be suspended per organisation.
- Every decision is written to `audit_event` (`apps/audit`), queryable at `GET /api/v1/admin/audit`.

## Web

Typed codes are localised (`apiErrors.contact_information_not_allowed`) both
as field errors (`useFormErrors`) and as action errors (`toErrorMessage`), so a
user sees the Arabic/English explanation next to the offending field.
