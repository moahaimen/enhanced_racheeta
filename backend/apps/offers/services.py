from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit_services
from apps.providers.models import ProviderProfile, ServiceOffering

from .models import Offer


class OfferError(Exception):
    code = "offer_error"


class ServiceUnavailable(OfferError):
    code = "service_unavailable"


class InvalidOffer(OfferError):
    code = "invalid_offer"


class OfferNotFound(OfferError):
    code = "not_found"


def _validate_window(*, starts_at, ends_at):
    if ends_at <= starts_at:
        raise InvalidOffer("Offer end time must be after its start time.")
    if ends_at <= timezone.now():
        raise InvalidOffer("Offer must end in the future.")


@transaction.atomic
def create_offer(
    provider: ProviderProfile,
    *,
    service_id,
    title: str,
    description: str,
    offer_price,
    starts_at,
    ends_at,
) -> Offer:
    provider = ProviderProfile.objects.select_for_update(of=("self",)).get(pk=provider.pk)
    try:
        service = ServiceOffering.objects.select_for_update(of=("self",)).get(
            pk=service_id,
            provider=provider,
            is_active=True,
        )
    except ServiceOffering.DoesNotExist as exc:
        raise ServiceUnavailable("The selected service is unavailable.") from exc

    _validate_window(starts_at=starts_at, ends_at=ends_at)
    if offer_price >= service.price:
        raise InvalidOffer("Offer price must be lower than the service price.")

    offer = Offer.objects.create(
        provider=provider,
        service=service,
        service_title_snapshot=service.title,
        title=title.strip(),
        description=description.strip(),
        original_price_snapshot=service.price,
        offer_price=offer_price,
        currency_snapshot=service.currency,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    audit_services.record(
        actor=provider.account,
        action="offer.created",
        target=offer,
        summary=offer.title,
        data={"service_id": str(service.pk)},
    )
    return offer


@transaction.atomic
def update_offer(provider: ProviderProfile, *, offer_id, changes: dict) -> Offer:
    provider = ProviderProfile.objects.select_for_update(of=("self",)).get(pk=provider.pk)
    try:
        offer = Offer.objects.select_for_update(of=("self",)).get(
            pk=offer_id,
            provider=provider,
        )
    except Offer.DoesNotExist as exc:
        raise OfferNotFound("Offer not found.") from exc

    starts_at = changes.get("starts_at", offer.starts_at)
    ends_at = changes.get("ends_at", offer.ends_at)
    is_active = changes.get("is_active", offer.is_active)
    offer_price = changes.get("offer_price", offer.offer_price)

    if is_active:
        _validate_window(starts_at=starts_at, ends_at=ends_at)
    elif ends_at <= starts_at:
        raise InvalidOffer("Offer end time must be after its start time.")
    if offer_price >= offer.original_price_snapshot:
        raise InvalidOffer("Offer price must be lower than the original service price.")

    for field in ("title", "description", "offer_price", "starts_at", "ends_at", "is_active"):
        if field in changes:
            value = changes[field]
            if field in {"title", "description"}:
                value = value.strip()
            setattr(offer, field, value)
    offer.save()

    audit_services.record(
        actor=provider.account,
        action="offer.updated",
        target=offer,
        summary=offer.title,
        data={"is_active": offer.is_active},
    )
    return offer
