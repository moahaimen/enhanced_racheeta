import django_filters

from .models import AdvertisingCampaign
from .types import CampaignStatus, PaymentStatus


class OwnerCampaignFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=CampaignStatus.choices)

    class Meta:
        model = AdvertisingCampaign
        fields: list[str] = []


class AdminCampaignFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=CampaignStatus.choices)
    company = django_filters.UUIDFilter(field_name="company_id")
    payment_status = django_filters.ChoiceFilter(
        field_name="payment__status", choices=PaymentStatus.choices
    )

    class Meta:
        model = AdvertisingCampaign
        fields: list[str] = []
