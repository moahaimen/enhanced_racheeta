from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import (
    APIException,
    ErrorDetail,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminAccount

from . import services
from .models import MedicalCompany, Product, ProductCategory
from .permissions import (
    BROWSE_DENIED,
    CanBrowseMarketplace,
    HasMedicalCompany,
    IsMedicalCompanyAccount,
    current_verified_provider,
)
from .serializers import (
    CompanyAdminSerializer,
    CompanyDashboardSerializer,
    CompanyOwnerSerializer,
    CompanyVerificationDecisionSerializer,
    CompanyWriteSerializer,
    PaginatedProductOwnerSerializer,
    ProductCategorySerializer,
    ProductOwnerSerializer,
    ProductPublicSerializer,
    ProductWriteSerializer,
)


class MarketplaceAPIError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST


STATUS_FOR_CODE = {
    "invalid_transition": status.HTTP_400_BAD_REQUEST,
    "already_exists": status.HTTP_409_CONFLICT,
    "company_not_verified": status.HTTP_403_FORBIDDEN,
    "category_unavailable": status.HTTP_409_CONFLICT,
    "invalid_product": status.HTTP_400_BAD_REQUEST,
    "not_found": status.HTTP_404_NOT_FOUND,
}


def raise_api(exc: services.MarketplaceError):
    err = MarketplaceAPIError(str(exc) or exc.code, code=exc.code)
    err.status_code = STATUS_FOR_CODE.get(exc.code, status.HTTP_400_BAD_REQUEST)
    raise err from exc


def _own_company(request) -> MedicalCompany:
    try:
        return MedicalCompany.objects.select_related("governorate", "city", "account").get(
            account=request.user
        )
    except MedicalCompany.DoesNotExist as exc:
        raise NotFound("You have not created a company profile yet.") from exc


# ---- reference data ----------------------------------------------------------------


@extend_schema(tags=["marketplace"], summary="Active product categories (reference data)")
class ProductCategoryListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = ProductCategorySerializer
    pagination_class = None  # bounded administrator reference data, like governorates
    queryset = (
        ProductCategory.objects.filter(is_active=True)
        .with_publishability()
        .order_by("sort_order", "name_en", "id")
    )


# ---- company self-service ------------------------------------------------------------


@extend_schema(tags=["marketplace-company"])
class MyCompanyView(APIView):
    permission_classes = [IsMedicalCompanyAccount]
    serializer_class = CompanyOwnerSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    @extend_schema(responses={200: CompanyOwnerSerializer}, summary="My company profile")
    def get(self, request):
        return Response(CompanyOwnerSerializer(_own_company(request)).data)

    @extend_schema(
        request=CompanyWriteSerializer,
        responses={201: CompanyOwnerSerializer},
        summary="Create my company profile (onboarding)",
    )
    def post(self, request):
        serializer = CompanyWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.create_company(request.user, dict(serializer.validated_data))
        except services.MarketplaceError as exc:
            raise_api(exc)
        return Response(
            CompanyOwnerSerializer(_own_company(request)).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        request=CompanyWriteSerializer,
        responses={200: CompanyOwnerSerializer},
        summary="Update my company profile",
    )
    def patch(self, request):
        company = _own_company(request)
        serializer = CompanyWriteSerializer(company, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            services.update_company(company, dict(serializer.validated_data))
        except services.IdentityLocked as exc:
            raise ValidationError(
                {
                    field: ErrorDetail(
                        "This field is locked while verification is pending or granted. "
                        "Ask Racheeta administration to change it.",
                        code="identity_locked",
                    )
                    for field in exc.fields
                }
            ) from exc
        except services.MarketplaceError as exc:
            raise_api(exc)
        return Response(CompanyOwnerSerializer(_own_company(request)).data)


@extend_schema(tags=["marketplace-company"], summary="Request verification of my company")
class MyCompanyVerificationRequestView(APIView):
    permission_classes = [HasMedicalCompany]
    serializer_class = None

    @extend_schema(request=None, responses={200: CompanyOwnerSerializer})
    def post(self, request):
        try:
            services.request_verification(_own_company(request))
        except services.MarketplaceError as exc:
            raise_api(exc)
        return Response(CompanyOwnerSerializer(_own_company(request)).data)


@extend_schema(tags=["marketplace-company"], summary="My company dashboard (backend-computed)")
class MyCompanyDashboardView(APIView):
    permission_classes = [HasMedicalCompany]
    serializer_class = CompanyDashboardSerializer

    @extend_schema(responses={200: CompanyDashboardSerializer})
    def get(self, request):
        return Response(
            CompanyDashboardSerializer(services.dashboard_summary(_own_company(request))).data
        )


def _category_with_publishability():
    """Nested categories carry `can_publish` too: one bounded query per page,
    annotated in SQL (see ProductCategoryQuerySet.with_publishability)."""
    return Prefetch("category", queryset=ProductCategory.objects.with_publishability())


def _own_product_response(request, pk, status_code=status.HTTP_200_OK):
    """After a write: answer with the product as the owner list reads it
    (current row, category publishability annotated)."""
    return Response(
        ProductOwnerSerializer(_own_products(request).get(pk=pk)).data, status=status_code
    )


def _own_products(request):
    return (
        Product.objects.filter(company__account=request.user)
        .select_related("company")
        .prefetch_related(_category_with_publishability())
    )


@extend_schema(tags=["marketplace-company"])
class MyProductListView(generics.GenericAPIView):
    permission_classes = [HasMedicalCompany]
    serializer_class = ProductOwnerSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {"is_active": ["exact"], "category": ["exact"]}

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Product.objects.none()
        return _own_products(self.request).order_by("-created_at", "id")

    @extend_schema(
        summary="My products (paginated, newest first)",
        responses={200: PaginatedProductOwnerSerializer},
    )
    def get(self, request):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(ProductOwnerSerializer(page, many=True).data)
        return Response(ProductOwnerSerializer(qs, many=True).data)

    @extend_schema(
        summary="Create a product (inactive until activated)",
        request=ProductWriteSerializer,
        responses={201: ProductOwnerSerializer},
    )
    def post(self, request):
        serializer = ProductWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            product = services.create_product(
                _own_company(request), dict(serializer.validated_data)
            )
        except services.MarketplaceError as exc:
            raise_api(exc)
        return _own_product_response(request, product.pk, status.HTTP_201_CREATED)


@extend_schema(tags=["marketplace-company"])
class MyProductDetailView(APIView):
    permission_classes = [HasMedicalCompany]
    serializer_class = ProductOwnerSerializer
    http_method_names = ["get", "patch", "head", "options"]

    @extend_schema(responses={200: ProductOwnerSerializer}, summary="One of my products")
    def get(self, request, pk):
        return Response(
            ProductOwnerSerializer(get_object_or_404(_own_products(request), pk=pk)).data
        )

    @extend_schema(
        request=ProductWriteSerializer,
        responses={200: ProductOwnerSerializer},
        summary="Update one of my products (an active product is re-validated)",
    )
    def patch(self, request, pk):
        product = get_object_or_404(_own_products(request), pk=pk)
        serializer = ProductWriteSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            product = services.update_product(
                _own_company(request), pk, dict(serializer.validated_data)
            )
        except services.MarketplaceError as exc:
            raise_api(exc)
        return _own_product_response(request, product.pk)


def _publication_view(active: bool, summary: str):
    @extend_schema(tags=["marketplace-company"], summary=summary)
    class View(APIView):
        permission_classes = [HasMedicalCompany]
        serializer_class = None

        @extend_schema(request=None, responses={200: ProductOwnerSerializer})
        def post(self, request, pk):
            try:
                product = services.update_product(_own_company(request), pk, {}, active=active)
            except services.MarketplaceError as exc:
                raise_api(exc)
            return _own_product_response(request, product.pk)

    View.__name__ = "MyProductActivateView" if active else "MyProductDeactivateView"
    return View


MyProductActivateView = _publication_view(True, "Activate (publish) one of my products")
MyProductDeactivateView = _publication_view(False, "Deactivate one of my products")


# ---- targeted provider catalogue -----------------------------------------------------


def _targeted(request):
    """List and detail share this: the provider is re-read from the database
    here (not taken from the permission check), and `targeted_for` re-checks
    its verification and identity inside the statement that returns products."""
    provider = current_verified_provider(request.user)
    if provider is None:
        raise PermissionDenied(BROWSE_DENIED)
    return (
        Product.objects.targeted_for(provider)
        .select_related("company", "company__governorate", "company__city")
        .prefetch_related(_category_with_publishability())
    )


@extend_schema(
    tags=["marketplace"],
    summary="Products targeted at my provider profile (paginated, newest first)",
)
class TargetedProductListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, CanBrowseMarketplace]
    serializer_class = ProductPublicSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {"category": ["exact"]}
    queryset = Product.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Product.objects.none()
        return _targeted(self.request).order_by("-created_at", "id")


@extend_schema(tags=["marketplace"], summary="One product targeted at my provider profile")
class TargetedProductDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, CanBrowseMarketplace]
    serializer_class = ProductPublicSerializer
    queryset = Product.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Product.objects.none()
        return _targeted(self.request)  # same rule as the list: 404 otherwise


# ---- administrators ------------------------------------------------------------------


@extend_schema(tags=["admin"], summary="Medical companies (administrators)")
class AdminCompanyListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdminAccount]
    serializer_class = CompanyAdminSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {"verification_status": ["exact"]}
    queryset = MedicalCompany.objects.select_related("governorate", "city", "account").order_by(
        "-created_at", "id"
    )


@extend_schema(tags=["admin"], summary="Decide a company's verification")
class AdminCompanyVerificationView(APIView):
    permission_classes = [IsAuthenticated, IsAdminAccount]
    serializer_class = CompanyVerificationDecisionSerializer

    @extend_schema(
        request=CompanyVerificationDecisionSerializer, responses={200: CompanyAdminSerializer}
    )
    def post(self, request, pk):
        company = get_object_or_404(MedicalCompany.objects.select_related("account"), pk=pk)
        serializer = CompanyVerificationDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                services.set_verification(
                    company,
                    serializer.validated_data["status"],
                    admin=request.user,
                    note=serializer.validated_data.get("note", ""),
                )
        except services.MarketplaceError as exc:
            raise_api(exc)
        company = MedicalCompany.objects.select_related("governorate", "city", "account").get(pk=pk)
        return Response(CompanyAdminSerializer(company).data)
