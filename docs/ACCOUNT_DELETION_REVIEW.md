# Account lifecycle and deletion — review (release readiness)

**Date:** 2026-10-27 · **Commit audited:** `main` `83ac6dd2363c6ce256402885d3fea10c0249248b`
**Status: OWNER DECISION REQUIRED — nothing implemented.** This document records what the product
does today, what the stores require, the data-model consequences of each option, and a proposal.
It deliberately stops short of code: a destructive account-deletion feature must not be added
casually, and the repository specifies no retention policy yet.

## 1. What exists today

| Capability | Backend | Web | Mobile |
| --- | --- | --- | --- |
| Register / log in / refresh / log out | `POST /api/v1/auth/{register,login,refresh,logout}` | yes | yes |
| Read / edit own profile | `GET/PATCH /api/v1/me` | yes (`/profile`) | yes (Account tab) |
| Change password, reset by e-mail, verify e-mail | `/api/v1/auth/password-reset/*`, `/email-verification/*` | yes | yes |
| **Self-service account deletion** | **none** (no endpoint, no serializer, no service) | none | none |
| **Deletion request / deactivation request** | **none** | none | none |
| Administrator deactivation | Django admin → `Account.is_active = False` (tokens stop authenticating; `docs/OPERATIONS.md` §7) | — | — |
| Administrator hard delete | Django admin `delete` → blocked by `PROTECT` foreign keys wherever the account has activity (see §3) | — | — |
| Data export | none | — | — |
| Privacy policy / terms text | **not provided** (`docs/PRODUCTION_DEPLOYMENT.md` §1 #9, OWNER) | — | — |

Conclusion: the product has **no user-facing account deletion or deletion-request path**.

## 2. Why it matters for submission

* **Google Play — User Data policy, "Account deletion" requirement** (in force since 2024): an app
  that lets users create an account must (a) offer an in-app path to delete the account and
  (b) publish a web link that lets a user request deletion without reinstalling the app; both are
  declared in the Data Safety form. Without them the listing can be rejected or removed.
* **Apple App Store Review Guideline 5.1.1(v)**: apps supporting account creation must also offer
  account deletion inside the app (a request path is acceptable only for highly regulated cases).

Both are therefore **release blockers for the store submissions** (not for the staging demo or a
web-only release). They are also legal inputs: the deletion behaviour must match the privacy
policy the owner publishes.

## 3. Data-model consequences (what an account is connected to)

Foreign keys to `accounts.Account` on `main`, by behaviour on delete:

| `on_delete` | Where | Meaning for deletion |
| --- | --- | --- |
| `CASCADE` (7) | `providers.ProviderProfile.account`, `marketplace.MedicalCompany.account`, `jobs.JobSeekerProfile.account`, `jobs.EmployerMembership.account`, `real_estate.RealEstateSeller.account`, `notifications.Notification.account`, `notifications.PushDevice.account` | Deleting the account removes the profile and **everything hanging off it**: a provider's services, slots, offers, listings, a company's products, an employer's job postings and their applications — including other people's data (patients' bookings on that provider, candidates' applications to that employer). |
| `PROTECT` (10) | `reservations.Reservation.patient`, `chat.ConversationParticipant.account`, `chat.Message.sender`, `jobs.*.created_by`, `jobs.RecruitmentMessage.sender`, … | Deletion is **refused** while the person has any reservation, message, job posting or application history. A hard delete is therefore impossible for any active user without first destroying history that belongs to other parties too. |
| `SET_NULL` (11) | `audit.AuditEvent.actor`, reservation/job transition `actor`, `advertising.*.verified_by`, `billing.*` (activated_by / recorded_by style actor links) | History survives with the actor blanked — the audit trail loses *who*, keeps *what/when*. |

Other facts that constrain the design:

* **Reservations are two-party records.** A patient's cancelled/completed bookings are part of the
  provider's history and reporting; a provider's slots are referenced by patients' bookings.
* **Reviews** (`reviews.Review`) reference the reservation and the provider; deleting the author
  must not silently change a provider's public rating history.
* **Jobs**: applications, recruitment messages and employer membership rows are shared between the
  candidate and the organisation; `created_by` on postings is `PROTECT`.
* **Chat**: messages are `PROTECT` on sender — a conversation cannot lose one side's rows.
* **Audit** (`audit.AuditEvent`) is the security log; it must keep its events (actor may be nulled).
* **E-mail uniqueness** (`accounts_account_email_ci_unique`): a deleted person must be able to
  register again later; a soft-deleted row must therefore free the address.
* **Billing** (`billing.*`): subscriptions/credits are organisation-level; the account link is
  generic (`docs/DEMO_DATA.md` §5 notes the same for cleanup).
* **No legal retention requirement is documented.** Medical bookings in Iraq may carry
  record-keeping expectations for providers; this is a legal question for the owner, not an
  engineering default.

## 4. Options

| Option | What happens | Pros | Cons |
| --- | --- | --- | --- |
| A. **Hard delete** (`Account.delete()`) | cascades through profiles, products, postings, applications; refused by `PROTECT` whenever history exists | simplest wording for the policy | destroys other users' records; impossible for most real accounts; breaks ratings, reporting and audit |
| B. **Anonymise + deactivate (soft delete)** — *proposed* | one transaction: `is_active=False`; `email` → `deleted+<uuid>@deleted.invalid`; `full_name` → "Deleted account"; `phone_number`/`preferred_language` cleared; password unusable; refresh tokens blacklisted; push devices removed; unread notifications deleted; provider/company/seller profiles **unpublished** (`is_visible=False`, products/listings/postings closed) rather than deleted; reservations, reviews, messages, applications, audit kept with the anonymised actor; an `AuditEvent` records the deletion | satisfies "the person is gone" for everyone else; no third-party data destroyed; re-registration possible; reversible for a grace period if desired | the policy text must describe it honestly ("your profile is removed and your personal details are erased; transactional records you shared with providers are kept without your name") |
| C. **Request-only** (form/e-mail, handled manually) | a "Request deletion" screen + web page; an administrator runs B | smallest code change | Apple accepts request-only paths only in narrow cases; Google requires the in-app path to *initiate* deletion — a request flow usually still passes if deletion is then completed; slower for users; manual work |

## 5. Proposal (for the owner to accept, amend or reject)

1. Adopt **Option B** as the single server-side operation, exposed as `DELETE /api/v1/me`
   (re-authentication with the current password; capability `accounts.delete_self`; 202 and
   the session is terminated), implemented as a service in `apps/accounts/services.py` with its
   own audit event and tests for every `PROTECT`/`CASCADE` relation listed above.
2. Role-specific unpublishing in the same transaction (provider profile hidden and future slots
   cancelled with patient notifications; company products deactivated; listings unpublished; job
   postings closed and open applications marked withdrawn; employer memberships removed, refusing
   deletion if the person is the **only owner** of an organisation with other members until
   ownership is transferred).
3. Web (`/profile` → "Delete my account", confirm with password) and mobile (Account tab →
   "Delete account") screens, Arabic and English, plus a **public web page**
   `/account-deletion` describing the steps (the URL Google Play asks for).
4. Retention statement: transactional records kept for *N* years (OWNER/legal decides *N*), then a
   `prune_*` command extends `prune_expired_tokens`.
5. Optional 14-day grace period (`deleted_at`, login refused but reversible by support) — decide
   with the policy.

Estimated engineering size once the policy is fixed: backend service + endpoint + tests, two
client screens, one public page, documentation — a single bounded PR. **Not started.**

## 6. What the owner must decide before implementation

* Which option (B recommended), the retention period, and whether a grace period exists.
* The privacy-policy and terms text (the deletion wording must match; also required by both
  stores and by `docs/PRODUCTION_DEPLOYMENT.md` #9).
* The public account-deletion URL (needs the production domain).
* Whether providers/facilities (business accounts) may self-delete or must contact support.
