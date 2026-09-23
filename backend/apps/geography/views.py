"""Public, read-only reference endpoints. Lists are bounded, so unpaginated."""

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import City, Country, Governorate
from .serializers import CitySerializer, CountrySerializer, GovernorateSerializer


class _ReferenceList(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = None
    filter_backends = [DjangoFilterBackend]


@extend_schema(tags=["geography"], summary="Active countries")
class CountryListView(_ReferenceList):
    serializer_class = CountrySerializer
    queryset = Country.objects.filter(is_active=True)


@extend_schema(tags=["geography"], summary="Active governorates (filter by country)")
class GovernorateListView(_ReferenceList):
    serializer_class = GovernorateSerializer
    queryset = Governorate.objects.filter(is_active=True, country__is_active=True)
    filterset_fields = {"country": ["exact"]}


@extend_schema(tags=["geography"], summary="Active cities (filter by governorate)")
class CityListView(_ReferenceList):
    serializer_class = CitySerializer
    queryset = City.objects.filter(is_active=True, governorate__is_active=True)
    filterset_fields = {"governorate": ["exact"]}
