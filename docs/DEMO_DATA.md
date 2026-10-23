# Demo data (staging presentation dataset)

`seed_demo_data` turns an empty staging environment into a plausible, **clearly fictional** Iraqi
healthcare ecosystem for presentations; `clear_demo_data` removes it again, and only it. Decision
record: ADR-063. **Never run this against production** (it refuses unless `DEMO_DATA_ENABLED=true`,
a variable you set on the staging service only).

> Status: the tooling is implemented and tested (Phase 12B). It has **not** been run on Railway
> staging: that happens only after review and merge (see §7).

## 1. Commands

```bash
# inside the staging service shell (Railway: service → shell, or `railway ssh`)
DEMO_DATA_ENABLED=true DEMO_PASSWORD='<a password you choose>' python manage.py seed_demo_data
python manage.py seed_demo_data --dry-run          # what it would create; writes nothing
python manage.py clear_demo_data --dry-run         # exactly what would be deleted; writes nothing
python manage.py clear_demo_data --yes             # delete the demo data (one transaction)
```

Both commands print counts and never print a credential. `seed_demo_data` is idempotent (a second
run adds nothing; day-relative appointment slots top up for new days). The lifecycle is
`empty → seed → rich demo → clear → clean → seed again`, covered by tests.

## 2. Logging in as the demo roles

All demo accounts share **one password that you choose at seed time** via the `DEMO_PASSWORD`
variable (at least 12 characters; set it as a Railway variable or inline for the one command; it is
never in git). Alternatively `--generate-password` prints a random one **once** to your terminal.
Accounts use the reserved, undeliverable domain `@demo.racheeta.invalid`; none is an administrator
(the seeder never creates staff). Suggested demonstration logins:

| Role | Email | What you see |
| --- | --- | --- |
| Patient | `patient-sara@demo.racheeta.invalid` | upcoming/completed appointments, notifications, a conversation, reviews to write |
| Doctor | `dr-karim-saadi@demo.racheeta.invalid` | provider dashboard, ratings, received bookings, availability, marketplace products |
| Hospital | `dijla-hospital@demo.racheeta.invalid` | facility dashboard, practitioners, recruiter workspace with jobs and applicants |
| Pharma company | `company-dijla-pharma@demo.racheeta.invalid` | company dashboard, products, recruiter workspace |
| Equipment company | `company-sharq-devices@demo.racheeta.invalid` | company dashboard with six products, job postings |
| Real-estate agent | `seller-mansour-properties@demo.racheeta.invalid` | seller dashboard with six listings |
| Job seekers | `seeker-ahmad@…`, `seeker-sara@…`, … (10) | résumé profile, applications in different states |

Your own administrator account (not touched by either command) shows the admin dashboard
aggregates over this data. Treat the shared password as staging-only; do not reuse a real password.

## 3. What the platform supports → what is seeded

| Area | Seeded (exact, after one run) | Notes |
| --- | --- | --- |
| Accounts | 70 (6 patients, 36 provider accounts, 13 company accounts, 10 job seekers, 5 sellers) | no admins; email-verified; shared password |
| Practitioners | 27 (14 specialties incl. cardiology, pediatrics, dermatology, ophthalmology, ENT, orthopedics, neurology, psychiatry, dentistry, gynecology, general, radiology, physiotherapy, nursing) | across Baghdad, Basra, Mosul, Erbil, Sulaymaniyah, Najaf, Karbala, Kirkuk, Anbar, Babil; all VERIFIED + visible |
| Facilities | 9 (2 hospitals, 5 medical centers: general, dental, imaging, physiotherapy, eye; laboratory; pharmacy) | 16 practitioner–facility memberships |
| Services | 72 (2 per provider, IQD prices, durations) | |
| Availability | 280 future slots (day-relative; skips Fridays; Asia/Baghdad times) | |
| Reservations | 85: completed (67, each reviewed), confirmed, pending, cancelled, rejected, no-show | upcoming ones created through the real booking/confirm/cancel services |
| Reviews | 67 with varied ratings (3–5; provider means ≈ 3.7–4.8) | through the real `create_review` service |
| Offers | 5 | through the real `create_offer` service |
| Notifications | 63 (27 unread, 36 read) | only the existing reservation events exist |
| Conversations | 5 (18 messages) | reservation context only (the only kind the product allows) |
| Pharmaceutical companies | 6 | `MedicalCompany` has no type field: pharma vs equipment is expressed in name, description and products |
| Medical-equipment/consumables companies | 7 | diagnostic, monitoring, laboratory, furniture, imaging, rehabilitation, consumables |
| Product categories | 10 (with audience rules) | categories are admin-managed reference data, not seeded by migrations; a real category with the same slug is reused and never owned |
| Marketplace products | 49 (price, brand, model, description; one "price on request") | generic catalogue entries, no medical claims |
| Employers | 10 (6 facilities, 4 companies), all VERIFIED + public | |
| Jobs | 24: 21 published, 1 closed, 1 pending review, 1 draft | GP, specialists, pharmacists, nurses, lab/radiology/anaesthesia technicians, biomedical/device/maintenance engineers, sales engineer, medical rep, hospital IT, data analyst, reception, physiotherapist, dentist, midwife |
| Job seekers / applications | 10 profiles (experience, education, skills, languages) / 16 applications in all states + 12 recruitment messages | |
| Real estate | 5 sellers (owners/agents) / 19 published listings (clinics, apartments, medical buildings, pharmacy, laboratory, medical center, hospital building, device showroom, investment land) | rent and sale, 8 governorates |

**Not seeded, and why:** advertising campaigns (the price per day is an administrator-defined
setting with no seeded value, and the seeder will not invent prices); images (see §6); billing
subscriptions; push devices; job-application notifications and company-related chat (the product has
only reservation notifications/conversations).

Display names use the pattern `Arabic | English` because provider, company, product, job and
listing titles are single-language fields. Every description ends with an explicit notice that the
record is a fictional demonstration. Names, organisations and brands are invented; no real patient
data exists anywhere in the dataset.

## 4. How ownership is identified (the safety mechanism)

No existing model has a "synthetic" marker, and guessing from e-mail domains or names cannot prove
"only demo data". The one schema addition is `demo.DemoRecord` (table `demo_record`: model label,
primary key, optional idempotency key):

* while `seed_demo_data` runs, a `post_save` receiver in **that process** records every row it
  INSERTS — the objects it creates **and** their side effects (notifications, audit events,
  transitions, memberships, tokens). The seeder is a separate process, so a web request can never be
  recorded by mistake; a row is registered only if it was inserted by the seeder;
* named objects also carry a stable key (`provider:dr-karim-saadi`, `product:12`, …) so a second run
  finds them instead of creating them again;
* each phase commits separately and registers its rows immediately after, so even a seed that fails
  half way leaves a clearable, consistent state.

## 5. Why cleanup cannot delete real data

`clear_demo_data` works in **one transaction** (all or nothing) and is fail-closed:

1. **Roots are only registered rows.** Reference data (governorates, cities, specialties, billing
   plans) is never registered and is only ever referenced.
2. **Everything the deletion would reach is verified before it is deleted.** For each layer Django's
   deletion collector lists every row that would be deleted or modified (CASCADE, SET NULL). A row
   outside the registry is accepted only if it is an auto-created many-to-many link row, or a
   "demo-internal" row — one whose every reference to a non-reference model points at a registered or
   to-be-deleted row (e.g. a booking made while demonstrating, an empty chat conversation, the login
   tokens and audit entries of a demo account).
3. **Anything else aborts the whole operation** and names the offending rows: a real user who
   booked a demo provider, a real candidate who applied to a demo job, a real review of a demo
   provider… Nothing has been changed when it refuses (tests assert the database is byte-for-byte
   the same).
4. PROTECT foreign keys are respected by deleting in dependency layers; nothing is force-deleted.
5. It needs `--yes` (or `--dry-run`), and a real account that merely has a demo-looking e-mail is
   not registered and survives (tested).

Residual: rows that other tools created about demo objects through *generic* (non-foreign-key)
links and that are not reachable from a demo account — for example a billing account created lazily
for a demo employer — are left in place rather than guessed at. None is created by the seeder.

## 6. Images

`ProviderProfile.image_url` is an external URL field (the web falls back to a type icon via
`Avatar`); companies, products, jobs and listings have **no image field** at all, and the platform
has no upload/storage mechanism. No image was seeded, no external image was referenced, nothing
paid was introduced. Placeholders appear as the application's own icon fallbacks.

## 7. Deployment boundary

Seeding staging happens only after: independent review → owner merge authorisation → merge → CI →
deploy of the accepted commit to staging → set `DEMO_DATA_ENABLED=true` (and `DEMO_PASSWORD`) on the
**staging** service → run `seed_demo_data`. Remove both variables afterwards if you do not want
the commands usable. Production must never have `DEMO_DATA_ENABLED` set.

## 8. Marketplace observation (no change made)

What the **existing** marketplace supports: companies (verified) publish products with title,
description, brand, model, price (or on request) and an active switch, in admin-managed categories;
**visibility is B2B and targeted** — only an authenticated, verified *provider* account sees the
products, and only those in categories whose audience rules match the provider's type/specialty
(web route `/marketplace`, product detail, company workspace for the company side). Categories are
public. There is no public storefront, no public company directory, no search across products, no
images/specifications fields, no cart, checkout, orders or payments. Recorded as an observation
only; whether a dedicated storefront redesign is wanted is a separate decision.

## 9. Known limitations

* Single-language model fields → `Arabic | English` composite names; cards in Arabic wrap them on
  two lines.
* `Profession` has no biomedical engineer, sales, IT or analyst values → those jobs use `OTHER` and
  say what they are in title and description.
* Seeded jobs, applications and verification states are written directly (the services that publish
  jobs and accept applications charge plan quotas and need an administrator); the same fields,
  snapshots and transition rows are written, and the reason is stated at each call in
  `apps/demo/seeder.py`.
* Provider/company names use ordinary Iraqi given names with generic family names; a coincidence
  with a real person or business cannot be excluded, which is why every record carries the
  demonstration notice.
* Slots are generated for the next ~12 days; re-run the seeder (idempotent) before a demo if the
  environment has been idle for weeks.
