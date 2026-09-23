from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsAdminAccount

from .models import AuditEvent
from .serializers import AuditEventSerializer


@extend_schema(tags=["admin"], summary="Audit history (administrators)")
class AuditEventListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdminAccount]
    serializer_class = AuditEventSerializer
    queryset = AuditEvent.objects.select_related("actor")
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        "action": ["exact", "startswith"],
        "target_type": ["exact"],
        "target_id": ["exact"],
    }
