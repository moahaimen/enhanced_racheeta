import django_filters

from .models import ProviderProfile
from .types import ProviderKind, ProviderType


class ProviderFilter(django_filters.FilterSet):
    type = django_filters.ChoiceFilter(field_name="provider_type", choices=ProviderType.choices)
    kind = django_filters.ChoiceFilter(method="filter_kind", choices=ProviderKind.choices)
    specialty = django_filters.CharFilter(method="filter_specialty", help_text="Specialty slug")
    governorate = django_filters.UUIDFilter(field_name="governorate_id")
    city = django_filters.UUIDFilter(field_name="city_id")

    class Meta:
        model = ProviderProfile
        fields = ["type", "kind", "specialty", "governorate", "city"]

    def filter_kind(self, queryset, name, value):
        from .types import FACILITY_TYPES, PRACTITIONER_TYPES

        types = PRACTITIONER_TYPES if value == ProviderKind.PRACTITIONER else FACILITY_TYPES
        return queryset.filter(provider_type__in=types)

    def filter_specialty(self, queryset, name, value):
        return queryset.filter(specialties__slug=value, specialties__is_active=True).distinct()
