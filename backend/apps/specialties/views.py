from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import Specialty
from .serializers import SpecialtySerializer


@extend_schema(tags=["specialties"], summary="Active specialties (unpaginated)")
class SpecialtyListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = None
    serializer_class = SpecialtySerializer
    queryset = Specialty.objects.filter(is_active=True)
