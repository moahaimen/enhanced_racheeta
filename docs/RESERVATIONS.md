# Reservations

Phase 4 implements free appointment booking on top of the verified provider and
service models from Phase 2. It does not depend on billing, payments, Redis,
Celery, FCM, or any other new infrastructure.

## Availability

A provider creates concrete `AvailabilitySlot` rows for one active
`ServiceOffering`. The slot end is derived from the service duration. New
slots must be in the future and cannot overlap another active slot for the same
provider. Slot creation locks the provider row so concurrent writers cannot
both pass the overlap check.

Public availability is returned only for providers that remain verified,
visible and attached to an active account, and only for active services. Slots
with a live PENDING or CONFIRMED reservation are excluded.

## Booking and concurrency

Patients book one availability slot. The booking transaction locks the slot,
provider, provider account and service before re-validating current visibility,
service activity, duration and time. A partial PostgreSQL unique constraint
allows at most one PENDING/CONFIRMED reservation for a slot, providing a final
database-level guard against double booking.

A cancelled/rejected/completed/no-show reservation is historical and no longer
occupies the live-slot uniqueness condition. Patient cancellation therefore
makes a still-future active slot bookable again.

## Reservation snapshots

Each reservation stores immutable snapshots of:

- provider display name;
- service title;
- price and currency;
- service duration;
- appointment start and end.

Historical reservation display therefore does not change when a provider later
renames a service or updates its price.

## State machine

Initial state is `PENDING`.

Provider transitions:
- PENDING -> CONFIRMED | REJECTED | CANCELLED
- CONFIRMED -> COMPLETED | CANCELLED | NO_SHOW

Patients may cancel their own PENDING or CONFIRMED reservation before the
appointment begins. Every transition appends `ReservationTransition` with
actor, previous state, next state, timestamp and optional reason.

## Notification hooks

`apps.reservations.hooks` exposes `reservation_created` and
`reservation_status_changed` Django signals. Services schedule them with
`transaction.on_commit`, so a rolled-back booking never emits an event.
Phase 9 may subscribe notification-record/FCM receivers. Phase 4 itself sends
no push messages and creates no notification infrastructure.

## API

Public:
- `GET /api/v1/providers/{provider_id}/availability`

Patient:
- `POST /api/v1/reservations`
- `GET /api/v1/reservations/me`
- `GET /api/v1/reservations/me/{id}`
- `POST /api/v1/reservations/me/{id}/cancel`

Provider:
- `GET|POST /api/v1/reservations/provider/availability`
- `DELETE /api/v1/reservations/provider/availability/{id}`
- `GET /api/v1/reservations/provider`
- `GET /api/v1/reservations/provider/{id}`
- `POST /api/v1/reservations/provider/{id}/transition`

The generated OpenAPI file remains the exact API contract.

## Web

- Provider public profiles display live available appointments and allow a
  signed-in PATIENT account to book.
- `/reservations` lists a patient's history and permits eligible cancellation.
- `/provider/reservations` lets provider accounts create/deactivate slots and
  manage received reservations.
- All backend actions use `ApiActionButton`; data loads use the shared async
  loading/error patterns.

## Mobile (Phase 11B)

The Flutter app (`mobile/`) offers the **patient** side only: find a provider, pick an appointment
from the provider's backend availability, see "My appointments" and cancel. It uses the endpoints in
the *API* section unchanged; the backend stays authoritative for every decision.

- **Booking.** The list is exactly what `GET /providers/{id}/availability?service&from&to`
  returned (a 30-day window starting now, in UTC); nothing is generated on the device. A listed slot
  is a snapshot: `POST /reservations` re-validates it. A taken slot (`slot_unavailable` /
  `slot_conflict`, 409) shows a localized message, clears the selection and refetches availability.
  `provider_unavailable` and `service_unavailable` have their own messages. A service without a
  duration cannot have slots, so *Book* is not offered for it.
- **No automatic retry.** `POST /reservations` has no idempotency key, so a repeat after an
  ambiguous failure could double-book. The app never retries it; the button shows progress and a
  second tap while pending is ignored; after a failure the user decides.
- **Cancellation.** *Cancel appointment* is offered from the documented rule (status PENDING or
  CONFIRMED and the start still ahead) as a **hint**. The API has no `can_cancel` field. The user
  confirms in a dialog (declining sends nothing); the backend's answer is final
  (`invalid_transition` → "can no longer be cancelled", then the true state is refetched).
- **Lists.** `GET /reservations/me` is paginated, newest appointment first. The screen groups the
  loaded items under *Upcoming* (live status, start ahead) and *Past and closed* as presentation
  only; there is no status filter in the API.
- **Reload after change.** After a booking or a cancellation the list, every opened detail and every
  availability snapshot are reloaded from the backend.
- **Account isolation.** All patient state is keyed on the signed-in account id; logout and
  account switching discard it and late responses of the old account are dropped.

### Timezone policy

The backend stores and returns UTC instants (`USE_TZ=True`, `TIME_ZONE=UTC`) and there is **no
provider or account timezone** in the API. The app therefore:

1. accepts only timestamps with an explicit offset (`Z` or `±hh:mm`); an offset-less value would be
   read as local time by `DateTime.parse`, so the response is rejected as unreadable;
2. keeps every instant as UTC internally and sends `from`/`to` as UTC (`...Z`);
3. converts to the **device's local time** only for display, including the calendar day used to
   group slots (a 21:30Z slot is the next local day for a UTC+3 reader), and says so on the booking
   screen ("Times are shown in your device's time zone").

It never labels UTC as local and never hardcodes a country. If the provider's own location time
ever matters, that needs a provider timezone field in the API first.

### Known gaps (not invented around)

No `can_cancel` field; no idempotency key on `POST /reservations`; no provider timezone; provider
images and coordinates are not rendered; no rescheduling; no status filter on `GET /reservations/me`.
`ReservationPatient.provider_id` is documented as always present but the backend nulls it when a
provider is deleted, so the app renders such a reservation from its snapshots.

## Mobile provider and facility (Phase 11C)

The Flutter app (`mobile/`) offers the **provider side** to accounts whose `/me` lists
`reservations.manage_received`: a dashboard, appointment availability, and the bookings the
provider received. It uses the endpoints in the *API* section unchanged; the backend stays
authoritative for every decision. Individual providers and facilities use the same endpoints (both
are `PROVIDER` accounts with a provider profile; a facility is a `FACILITY`-kind profile). The only
difference is the dashboard: the server's `GET /dashboards/` says whether to open the doctor or the
facility one, and a facility dashboard adds its own membership counts.

- **Availability.** A slot is created from an **active service that has a duration**, a date and a
  start time chosen in the device's time zone; the app sends the start as a UTC instant and the
  backend computes the end (start + duration). Overlap with another active slot (`slot_conflict`),
  "must start in the future" (`invalid_availability`) and unusable services (`service_unavailable`)
  are the backend's rules and have their own messages. Removing a slot calls
  `DELETE /reservations/provider/availability/{id}`; a slot used by a live reservation is refused
  (`slot_unavailable`, "a live booking uses this time"). Nothing is generated locally: the list is
  reloaded from the backend after each change. `GET /reservations/provider/availability` has no
  filter and includes inactive and past slots (soonest first), so the screen requests 100 per page and
  shows the **active, not-yet-ended** slots of the pages loaded so far, grouped by local day, with an
  explicit note and *Load more* when older entries fill the first pages.
- **Bookings.** `GET /reservations/provider` (paginated, newest appointment first) and
  `/reservations/provider/{id}`: patient name, service, local time, price, duration, the patient's
  note and the transition history, exactly the fields of the provider reservation schema.
- **Transitions.** `POST /reservations/provider/{id}/transition {status}`. The backend state machine
  (`PROVIDER_TRANSITIONS` and the time rules in `transition_as_provider`) is: PENDING → CONFIRMED
  (only before the appointment starts), REJECTED, CANCELLED; CONFIRMED → COMPLETED and NO_SHOW (only
  after it started), CANCELLED; nothing else. The app offers buttons from the current status and
  start time as a **hint**; a refusal (`invalid_transition`) is shown and the record refetched.
  Reject, cancel and no-show ask for confirmation. While one transition runs the others are locked.
  After a success the detail, the list and the dashboard are reloaded.
- **No automatic retry and no double submit.** Slot creation, slot removal and transitions are one
  request per deliberate tap, the button shows progress and ignores further taps, and a failure is
  reported once.
- **Account isolation.** Data is keyed by the signed-in account, local screen state is reset when the
  account changes, and a mutation that finishes after the account changed is dropped without showing
  anything or invalidating anything (see ADR-055).
- **Timezone.** The 11B policy applies: offsets required, UTC on the wire, device-local display. A
  date/time the provider picks is converted back to UTC with the injectable `localToUtcProvider`.

### Known gaps (not invented around)

No facility-wide aggregation of its practitioners' reservations (the API has no such relation);
facility membership management endpoints exist but are not part of 11C; no profile or service
editing on mobile; the transition `reason` (accepted by the API) is not collected; the availability
list has no filter and no "reserved" flag per slot.
