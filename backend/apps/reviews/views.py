from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import has_role
from apps.accounts.roles import AccountRole
from apps.providers.models import ProviderProfile

from . import services
from .models import Review
from .serializers import MyReviewSerializer, PublicReviewSerializer, ReviewCreateSerializer

IsPatientAccount = has_role(AccountRole.PATIENT)


class ReviewAPIError(APIException):
    status_code = status.HTTP_409_CONFLICT


STATUS_FOR_CODE = {
    "reservation_not_reviewable": status.HTTP_409_CONFLICT,
    "already_reviewed": status.HTTP_409_CONFLICT,
}


def raise_api(exc: services.ReviewError):
    err = ReviewAPIError(str(exc) or exc.code, code=exc.code)
    err.status_code = STATUS_FOR_CODE.get(exc.code, status.HTTP_400_BAD_REQUEST)
    raise err from exc


@extend_schema(tags=["reviews"], summary="Public reviews for a provider")
class PublicProviderReviewListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PublicReviewSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Review.objects.none()
        provider = get_object_or_404(
            ProviderProfile.objects.discoverable(),
            pk=self.kwargs["provider_id"],
        )
        return Review.objects.filter(provider=provider).order_by("-created_at")


@extend_schema(tags=["reviews"], summary="Create a review for a completed reservation")
class ReviewCreateView(APIView):
    permission_classes = [IsAuthenticated, IsPatientAccount]
    serializer_class = ReviewCreateSerializer

    @extend_schema(request=ReviewCreateSerializer, responses={201: MyReviewSerializer})
    def post(self, request):
        serializer = ReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            review = services.create_review(
                patient=request.user,
                reservation_id=serializer.validated_data["reservation"],
                rating=serializer.validated_data["rating"],
                comment=serializer.validated_data.get("comment", ""),
            )
        except services.ReviewError as exc:
            raise_api(exc)
        return Response(MyReviewSerializer(review).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["reviews"], summary="My submitted reviews")
class MyReviewListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsPatientAccount]
    serializer_class = MyReviewSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Review.objects.none()
        return Review.objects.filter(patient=self.request.user).order_by("-created_at")
