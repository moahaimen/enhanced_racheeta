from django.contrib.admin.sites import AdminSite

from apps.providers.admin import ServiceInline, ServiceOfferingAdmin
from apps.providers.models import ServiceOffering


def test_service_provider_is_read_only_after_creation():
    model_admin = ServiceOfferingAdmin(ServiceOffering, AdminSite())
    marker = object()

    assert "provider" in model_admin.get_readonly_fields(None, marker)
    assert "provider" not in model_admin.get_readonly_fields(None, None)


def test_service_deletion_is_disabled_in_admin_and_provider_inline():
    model_admin = ServiceOfferingAdmin(ServiceOffering, AdminSite())
    inline = ServiceInline(model_admin.model, AdminSite())

    assert model_admin.has_delete_permission(None) is False
    assert inline.can_delete is False
