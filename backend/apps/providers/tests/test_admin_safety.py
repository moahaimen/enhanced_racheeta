from django.contrib.admin.sites import AdminSite

from apps.providers.admin import ServiceOfferingAdmin
from apps.providers.models import ServiceOffering


def test_service_provider_is_read_only_after_creation():
    model_admin = ServiceOfferingAdmin(ServiceOffering, AdminSite())
    marker = object()

    assert "provider" in model_admin.get_readonly_fields(None, marker)
    assert "provider" not in model_admin.get_readonly_fields(None, None)
