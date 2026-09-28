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
