from django.urls import path

from . import views

urlpatterns = [path("admin/audit", views.AuditEventListView.as_view(), name="admin-audit")]
