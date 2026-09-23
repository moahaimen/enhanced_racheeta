# Mobile (Flutter) — not started

Phase 11 of `../master_plan` builds a new Flutter application here.

Constraints already decided (see `../docs/DECISIONS.md`):

- Consumes exactly the same `/api/v1/` API as the web app. No mobile-only endpoints.
- One API client, one session (access + refresh token), secure token storage.
- `GET /api/v1/me` is the only source of identity, role and permissions. Never
  store `doctor_id` / `hospital_id` style identifiers client-side.
- Every backend-connected button shows a circular progress indicator and is
  disabled while the request is running (mandatory loading rule).

The legacy Flutter app may be read for UI ideas only; nothing is copied from it.
