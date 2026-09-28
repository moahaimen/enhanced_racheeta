# Reviews & Offers — Phase 5

## Scope

Phase 5 adds evidence-backed provider reviews/ratings and provider-managed service offers. It does not add payment processing, media uploads, Redis, Celery, or persistent notifications.

## Reviews

A review is tied to exactly one reservation.

Eligibility:
- authenticated account role must be PATIENT;
- the reservation must belong to that patient;
- reservation status must be COMPLETED;
- reservation must still identify a provider;
- only one review may exist per reservation.

Stored review data includes the reservation, patient, provider reference, provider/service snapshots, rating (1–5), optional comment and timestamps. The reservation relationship is protected so review evidence is not silently deleted.

Public provider reviews are exposed only for discoverable providers. Provider discovery/detail expose persisted `average_rating` and `review_count`; unrated providers use a null average and zero count rather than fabricated values.

## Offers

Offers belong to a provider and are created against one of that provider's active services.

Creation snapshots:
- service title;
- original service price;
- currency.

Rules:
- `ends_at > starts_at`;
- `ends_at` must be in the future at creation;
- offer price must be non-negative and strictly below the original service price;
- provider/service ownership and service activity are checked server-side.

Public visibility is server-controlled. A public offer is returned only when:
- the provider is currently discoverable;
- the linked service is active;
- the offer is marked active;
- `starts_at <= now < ends_at`.

The provider workspace can list, create, edit and deactivate its own offers. Expiry needs no background worker because visibility is evaluated against server time.

## Web

- Provider detail shows rating/count, public reviews and currently valid offers.
- Patient reservation cards expose a review form only after COMPLETED reservations and hide it after the review exists.
- Provider offers have a dedicated Arabic/English management workspace with loading/error/action states and pagination.

## Infrastructure

PostgreSQL only. No payment gateway, media/object storage, Redis, Celery or new environment variables.
