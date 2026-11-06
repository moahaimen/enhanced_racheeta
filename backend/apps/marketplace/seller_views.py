"""Seller onboarding and store-management endpoints (pharmacy store, documents, activation,
tax and delivery settings, variants, photos) and the administrator document review.

Every company-scoped endpoint resolves the acting business with `_acting_company`: the owner, or
(with `?company=<id>`) an ACTIVE staff member holding the capability. Nothing is taken from ids
in the body. Files are streamed only after the same checks (apps.marketplace.uploads.stream).
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminAccount

from . import sellers, uploads
from .models import MedicalCompany, ProductImage, ProductVariant, SellerDocument, ShippingRate
from .permissions import IsMedicalCompanyAccount
from .serializers import (
    AdminSellerDocumentSerializer,
    CompanyOwnerSerializer,
    DocumentDecisionSerializer,
    ImageUploadSerializer,
    PharmacyStoreSerializer,
    ProductImageSerializer,
    SellerDocumentSerializer,
    SellerDocumentUploadSerializer,
    ShippingRateSerializer,
    ShippingRateWriteSerializer,
    StoreSettingsSerializer,
    StoreStatusSerializer,
    VariantOwnerSerializer,
    VariantWriteSerializer,
)
from .services import MarketplaceError
from .views import HasCompanyWorkspace, _acting_company, raise_api


def _fail(exc):
    if isinstance(exc, uploads.UploadRejected):
        err = MarketplaceError(str(exc))
        err.code = "invalid_file"
        raise_api(err)
    raise_api(exc)


def _store(request, capability="company.view"):
    company = _acting_company(request, capability)
    return MedicalCompany.objects.select_related("governorate", "city", "account").get(
        pk=company.pk
    )


# ---- pharmacy store and store status -----------------------------------------------------


@extend_schema(tags=["marketplace-company"])
class PharmacyStoreView(APIView):
    """A pharmacy opens its store without leaving its provider identity."""

    permission_classes = [IsMedicalCompanyAccount]
    serializer_class = PharmacyStoreSerializer

    @extend_schema(
        request=PharmacyStoreSerializer,
        responses={201: CompanyOwnerSerializer},
        summary="Open my pharmacy's store (linked to my pharmacy provider profile)",
    )
    def post(self, request):
        serializer = PharmacyStoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            company = sellers.open_pharmacy_store(request.user, dict(serializer.validated_data))
        except MarketplaceError as exc:
            _fail(exc)
        company = MedicalCompany.objects.select_related("governorate", "city", "account").get(
            pk=company.pk
        )
        return Response(CompanyOwnerSerializer(company).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["marketplace-company"])
class StoreView(APIView):
    """The acting business's store (owner, or staff with `?company=`)."""

    permission_classes = [HasCompanyWorkspace]
    serializer_class = CompanyOwnerSerializer

    @extend_schema(responses={200: CompanyOwnerSerializer}, summary="My store (status, rules)")
    def get(self, request):
        return Response(CompanyOwnerSerializer(_store(request)).data)

    @extend_schema(
        request=StoreSettingsSerializer,
        responses={200: CompanyOwnerSerializer},
        summary="Update my store's tax treatment and delivery defaults",
    )
    def patch(self, request):
        company = _acting_company(request, "company.store.manage")
        serializer = StoreSettingsSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            sellers.update_store_settings(
                company.pk, actor=request.user, data=dict(serializer.validated_data)
            )
        except MarketplaceError as exc:
            _fail(exc)
        return Response(CompanyOwnerSerializer(_store(request)).data)


@extend_schema(tags=["marketplace-company"])
class StoreStatusView(APIView):
    permission_classes = [HasCompanyWorkspace]
    serializer_class = StoreStatusSerializer

    @extend_schema(
        request=StoreStatusSerializer,
        responses={200: CompanyOwnerSerializer},
        summary="Activate or pause my store (activation needs verification and documents)",
    )
    def post(self, request):
        company = _acting_company(request, "company.store.manage")
        serializer = StoreStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            sellers.set_store_status(
                company.pk, actor=request.user, active=serializer.validated_data["active"]
            )
        except MarketplaceError as exc:
            _fail(exc)
        return Response(CompanyOwnerSerializer(_store(request)).data)


# ---- documents -----------------------------------------------------------------------------


@extend_schema(tags=["marketplace-company"])
class DocumentListView(APIView):
    permission_classes = [HasCompanyWorkspace]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = SellerDocumentSerializer

    @extend_schema(responses={200: SellerDocumentSerializer(many=True)}, summary="My documents")
    def get(self, request):
        company = _acting_company(request, "company.documents.manage")
        return Response(SellerDocumentSerializer(company.documents.all(), many=True).data)

    @extend_schema(
        request={"multipart/form-data": SellerDocumentUploadSerializer},
        responses={201: SellerDocumentSerializer},
        summary="Upload a verification document (PDF, JPEG or PNG; 5 MB)",
    )
    def post(self, request):
        company = _acting_company(request, "company.documents.manage")
        serializer = SellerDocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            doc = sellers.upload_document(
                company.pk,
                actor=request.user,
                kind=data["kind"],
                upload=data["file"],
                reference_number=data.get("reference_number", ""),
                expires_on=data.get("expires_on"),
            )
        except (MarketplaceError, uploads.UploadRejected) as exc:
            _fail(exc)
        return Response(SellerDocumentSerializer(doc).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["marketplace-company"])
class DocumentDetailView(APIView):
    permission_classes = [HasCompanyWorkspace]
    serializer_class = None

    @extend_schema(responses={204: None}, summary="Withdraw a document that is not approved")
    def delete(self, request, pk):
        company = _acting_company(request, "company.documents.manage")
        try:
            sellers.withdraw_document(pk, company_id=company.pk, actor=request.user)
        except MarketplaceError as exc:
            _fail(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["marketplace-company"])
class DocumentFileView(APIView):
    permission_classes = [HasCompanyWorkspace]
    serializer_class = None

    @extend_schema(
        responses={200: OpenApiResponse(description="The file")}, summary="Open my document"
    )
    def get(self, request, pk):
        company = _acting_company(request, "company.documents.manage")
        doc = get_object_or_404(SellerDocument, pk=pk, company=company)
        return uploads.stream(doc.file, doc.content_type, download_name=doc.original_name)


# ---- delivery rates ------------------------------------------------------------------------


@extend_schema(tags=["marketplace-company"])
class ShippingRateListView(APIView):
    permission_classes = [HasCompanyWorkspace]
    serializer_class = ShippingRateSerializer

    @extend_schema(responses={200: ShippingRateSerializer(many=True)}, summary="Delivery fees")
    def get(self, request):
        company = _acting_company(request, "company.view")
        rates = ShippingRate.objects.filter(company=company).select_related("governorate")
        return Response(ShippingRateSerializer(rates, many=True).data)

    @extend_schema(
        request=ShippingRateWriteSerializer,
        responses={200: ShippingRateSerializer},
        summary="Set the delivery fee to one governorate",
    )
    def post(self, request):
        company = _acting_company(request, "company.store.manage")
        serializer = ShippingRateWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            rate = sellers.set_shipping_rate(
                company.pk,
                actor=request.user,
                governorate=data["governorate"],
                fee=data["fee"],
                min_days=data["min_days"],
                max_days=data["max_days"],
                active=data["is_active"],
            )
        except MarketplaceError as exc:
            _fail(exc)
        return Response(ShippingRateSerializer(rate).data)


@extend_schema(tags=["marketplace-company"])
class ShippingRateDetailView(APIView):
    permission_classes = [HasCompanyWorkspace]
    serializer_class = None

    @extend_schema(responses={204: None}, summary="Remove a delivery fee")
    def delete(self, request, pk):
        company = _acting_company(request, "company.store.manage")
        try:
            sellers.delete_shipping_rate(pk, company_id=company.pk, actor=request.user)
        except MarketplaceError as exc:
            _fail(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---- variants and photos ---------------------------------------------------------------------


@extend_schema(tags=["marketplace-company"])
class VariantListView(APIView):
    permission_classes = [HasCompanyWorkspace]
    serializer_class = VariantOwnerSerializer

    @extend_schema(responses={200: VariantOwnerSerializer(many=True)}, summary="Variants")
    def get(self, request, pk):
        company = _acting_company(request, "company.products.view")
        rows = ProductVariant.objects.filter(product_id=pk, company=company)
        return Response(VariantOwnerSerializer(rows, many=True).data)

    @extend_schema(
        request=VariantWriteSerializer,
        responses={201: VariantOwnerSerializer},
        summary="Add a variant (its own SKU, price and stock)",
    )
    def post(self, request, pk):
        company = _acting_company(request, "company.products.edit")
        serializer = VariantWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            variant = sellers.create_variant(
                company.pk, pk, actor=request.user, data=dict(serializer.validated_data)
            )
        except MarketplaceError as exc:
            _fail(exc)
        return Response(VariantOwnerSerializer(variant).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["marketplace-company"])
class VariantDetailView(APIView):
    permission_classes = [HasCompanyWorkspace]
    serializer_class = VariantOwnerSerializer
    http_method_names = ["patch", "options", "head"]

    @extend_schema(
        request=VariantWriteSerializer,
        responses={200: VariantOwnerSerializer},
        summary="Edit a variant (stock changes go through a stock adjustment)",
    )
    def patch(self, request, pk):
        company = _acting_company(request, "company.products.edit")
        serializer = VariantWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            variant = sellers.update_variant(
                company.pk, pk, actor=request.user, data=dict(serializer.validated_data)
            )
        except MarketplaceError as exc:
            _fail(exc)
        return Response(VariantOwnerSerializer(variant).data)


@extend_schema(tags=["marketplace-company"])
class ProductImageUploadView(APIView):
    permission_classes = [HasCompanyWorkspace]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = ProductImageSerializer

    @extend_schema(
        request={"multipart/form-data": ImageUploadSerializer},
        responses={201: ProductImageSerializer},
        summary="Add a product photo (JPEG, PNG or WebP; 3 MB)",
    )
    def post(self, request, pk):
        company = _acting_company(request, "company.products.edit")
        serializer = ImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            image = sellers.add_image(
                company.pk,
                pk,
                actor=request.user,
                upload=serializer.validated_data["file"],
                alt_text=serializer.validated_data.get("alt_text", ""),
            )
        except (MarketplaceError, uploads.UploadRejected) as exc:
            _fail(exc)
        return Response(ProductImageSerializer(image).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["marketplace-company"])
class ProductImageDeleteView(APIView):
    permission_classes = [HasCompanyWorkspace]
    serializer_class = None

    @extend_schema(responses={204: None}, summary="Remove a product photo")
    def delete(self, request, pk):
        company = _acting_company(request, "company.products.edit")
        try:
            sellers.remove_image(company.pk, pk, actor=request.user)
        except MarketplaceError as exc:
            _fail(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["marketplace"])
class ProductImageFileView(APIView):
    """A product photo: public for a product on sale, the business's team (and Racheeta staff)
    otherwise. Unknown and hidden photos are both 404."""

    permission_classes = [AllowAny]
    serializer_class = None

    @extend_schema(
        responses={200: OpenApiResponse(description="The image")}, summary="Product photo"
    )
    def get(self, request, pk):
        image = get_object_or_404(ProductImage.objects.select_related("product"), pk=pk)
        if not sellers.image_visible_to(image, request.user):
            return Response(status=status.HTTP_404_NOT_FOUND)
        return uploads.stream(image.file, image.content_type)


# ---- administrators: document review ---------------------------------------------------------


@extend_schema(tags=["admin"], summary="Seller documents to review (administrators)")
class AdminDocumentListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdminAccount]
    serializer_class = AdminSellerDocumentSerializer

    def get_queryset(self):
        qs = SellerDocument.objects.select_related("company").order_by("created_at", "id")
        wanted = self.request.query_params.get("status")
        if wanted:
            qs = qs.filter(status=wanted)
        company = self.request.query_params.get("company")
        if company:
            qs = qs.filter(company_id=company)
        return qs


@extend_schema(tags=["admin"])
class AdminDocumentDecisionView(APIView):
    permission_classes = [IsAuthenticated, IsAdminAccount]
    serializer_class = DocumentDecisionSerializer

    @extend_schema(
        request=DocumentDecisionSerializer,
        responses={200: AdminSellerDocumentSerializer},
        summary="Approve or reject a seller document",
    )
    def post(self, request, pk):
        serializer = DocumentDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            doc = sellers.review_document(
                pk,
                admin=request.user,
                approve=serializer.validated_data["approve"],
                note=serializer.validated_data.get("note", ""),
            )
        except MarketplaceError as exc:
            _fail(exc)
        doc = SellerDocument.objects.select_related("company").get(pk=doc.pk)
        return Response(AdminSellerDocumentSerializer(doc).data)


@extend_schema(tags=["admin"])
class AdminDocumentFileView(APIView):
    permission_classes = [IsAuthenticated, IsAdminAccount]
    serializer_class = None

    @extend_schema(
        responses={200: OpenApiResponse(description="The file")}, summary="Open a document"
    )
    def get(self, request, pk):
        doc = get_object_or_404(SellerDocument, pk=pk)
        return uploads.stream(doc.file, doc.content_type, download_name=doc.original_name)
