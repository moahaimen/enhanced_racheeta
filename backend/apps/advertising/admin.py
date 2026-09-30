"""Django admin: the ONLY editable model is AdvertisingRate (explicit business
configuration, with its invariants protected). Campaigns, payments and their
targets are lifecycle state owned by the services (which lock, validate and
audit): inspection-only, so the admin can neither activate a campaign, mark a
payment verified, rewrite a status nor change an amount."""

from django import forms
from django.contrib import admin
from django.db import transaction

from apps.audit import services as audit

from .models import (
    AdvertisingCampaign,
    AdvertisingRate,
    CampaignGovernorate,
    CampaignPayment,
    CampaignProviderType,
    CampaignSpecialty,
)


class AdvertisingRateForm(forms.ModelForm):
    class Meta:
        model = AdvertisingRate
        fields = ["code", "name_ar", "name_en", "price_per_day", "currency", "is_active"]

    def _get_validation_exclusions(self):
        # "One active rate" is enforced by the database and by the atomic swap in
        # save_model (activating a rate retires the previous one); the form must not
        # reject the swap before it happens.
        return {*super()._get_validation_exclusions(), "is_active"}

    def clean_price_per_day(self):
        value = self.cleaned_data["price_per_day"]
        if value is not None and value <= 0:
            raise forms.ValidationError("The daily price must be greater than zero.")
        return value

    def clean_currency(self):
        from django.conf import settings

        value = self.cleaned_data["currency"]
        if value not in settings.RACHEETA["CURRENCIES"]:
            raise forms.ValidationError("Unsupported currency.")
        return value


@admin.register(AdvertisingRate)
class AdvertisingRateAdmin(admin.ModelAdmin):
    form = AdvertisingRateForm
    list_display = ("code", "price_per_day", "currency", "is_active", "updated_at")
    list_filter = ("is_active",)

    def has_delete_permission(self, request, obj=None):
        # History stays understandable: campaigns keep a protected reference to the rate.
        return False

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        # Activating a rate atomically retires the previous one (at most one is active).
        if obj.is_active:
            AdvertisingRate.objects.filter(is_active=True).exclude(pk=obj.pk).update(
                is_active=False
            )
        super().save_model(request, obj, form, change)
        audit.record(
            actor=request.user,
            action="advertising.rate.updated" if change else "advertising.rate.created",
            target=obj,
            summary=f"{obj.code}: {obj.price_per_day} {obj.currency}",
            data={"is_active": obj.is_active},
        )


class _InspectionOnly(admin.ModelAdmin):
    actions = None

    def get_readonly_fields(self, request, obj=None):
        return tuple(f.name for f in self.model._meta.concrete_fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AdvertisingCampaign)
class AdvertisingCampaignAdmin(_InspectionOnly):
    list_display = ("name", "company", "product", "status", "starts_on", "ends_on", "quoted_amount")
    list_filter = ("status",)
    search_fields = ("name", "company__name")


@admin.register(CampaignPayment)
class CampaignPaymentAdmin(_InspectionOnly):
    list_display = ("campaign", "amount", "currency", "status", "method", "verified_at")
    list_filter = ("status", "method")


@admin.register(CampaignProviderType)
class CampaignProviderTypeAdmin(_InspectionOnly):
    list_display = ("campaign", "provider_type")


@admin.register(CampaignSpecialty)
class CampaignSpecialtyAdmin(_InspectionOnly):
    list_display = ("campaign", "specialty")


@admin.register(CampaignGovernorate)
class CampaignGovernorateAdmin(_InspectionOnly):
    list_display = ("campaign", "governorate")
