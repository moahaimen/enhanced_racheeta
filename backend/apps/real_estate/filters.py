import django_filters
from django.db.models import Exists, F, OuterRef

from .models import ListingSuitableUse, PropertyListing
from .types import PropertyType, PublicationStatus, SuitableUse, TransactionType

# Safe orderings only. Every ordering ends in `id`, so pages are stable; a
# price on request (null) always sorts last.
ORDERINGS = {
    "created_at": ("created_at", "id"),
    "-created_at": ("-created_at", "id"),
    "price": (F("price").asc(nulls_last=True), "id"),
    "-price": (F("price").desc(nulls_last=True), "id"),
    "area_sqm": (F("area_sqm").asc(nulls_last=True), "id"),
    "-area_sqm": (F("area_sqm").desc(nulls_last=True), "id"),
}
ORDERING_CHOICES = [(key, key) for key in ORDERINGS]


class _ListingFilter(django_filters.FilterSet):
    transaction_type = django_filters.ChoiceFilter(choices=TransactionType.choices)
    property_type = django_filters.ChoiceFilter(choices=PropertyType.choices)
    governorate = django_filters.UUIDFilter(field_name="governorate_id")
    city = django_filters.UUIDFilter(field_name="city_id")
    suitable_use = django_filters.ChoiceFilter(
        choices=SuitableUse.choices, method="filter_suitable_use"
    )
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    min_area = django_filters.NumberFilter(field_name="area_sqm", lookup_expr="gte")
    max_area = django_filters.NumberFilter(field_name="area_sqm", lookup_expr="lte")
    ordering = django_filters.ChoiceFilter(choices=ORDERING_CHOICES, method="filter_ordering")

    class Meta:
        model = PropertyListing
        fields: list[str] = []

    def filter_suitable_use(self, queryset, name, value):
        return queryset.filter(
            Exists(ListingSuitableUse.objects.filter(listing=OuterRef("pk"), use=value))
        )

    def filter_ordering(self, queryset, name, value):
        return queryset.order_by(*ORDERINGS[value])


class PublicListingFilter(_ListingFilter):
    """Filters only narrow the queryset the view starts from
    (`publicly_visible()`): they can never widen exposure."""


class OwnerListingFilter(_ListingFilter):
    publication_status = django_filters.ChoiceFilter(choices=PublicationStatus.choices)
