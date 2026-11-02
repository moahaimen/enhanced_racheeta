"""Commerce API. Ownership is never taken from a client id without a server-side check:
buyers see their own orders; merchant endpoints resolve the business from the caller's ownership
or an ACTIVE staff membership with the needed capability (apps.workspaces.access)."""

from django.db.models import Prefetch, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.marketplace.models import Product, ProductCategory
from apps.marketplace.permissions import BROWSE_DENIED, current_verified_provider
from apps.marketplace.serializers import StoreCategorySerializer, StoreProductSerializer
from apps.workspaces import access

from . import services
from .models import Order, OrderTransition, QuoteRequest
from .serializers import (
    CancelSerializer,
    CheckoutSerializer,
    DeliveryDefaultsSerializer,
    OrderSerializer,
    OrderTransitionRequestSerializer,
    QuoteCloseSerializer,
    QuoteCreateSerializer,
    QuoteRespondSerializer,
    QuoteSerializer,
)

STATUS_FOR_CODE = {
    "not_allowed": status.HTTP_403_FORBIDDEN,
    "not_found": status.HTTP_404_NOT_FOUND,
    "out_of_stock": status.HTTP_409_CONFLICT,
    "invalid_transition": status.HTTP_409_CONFLICT,
}


class CommerceAPIError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST


def raise_api(exc: services.CommerceError):
    err = CommerceAPIError(str(exc) or exc.code, code=exc.code)
    err.status_code = STATUS_FOR_CODE.get(exc.code, status.HTTP_400_BAD_REQUEST)
    raise err from exc


def _orders():
    return Order.objects.select_related(
        "merchant", "buyer", "delivery_governorate", "delivery_city"
    ).prefetch_related(
        "items", Prefetch("transitions", queryset=OrderTransition.objects.order_by("created_at"))
    )


def _merchant_company_id(request, capability: str):
    """Business to act for: `?company=<id>` (owner or authorized staff) or the caller's own."""
    company_id = request.query_params.get("company") or access.own_company_id(request.user)
    if not company_id:
        raise PermissionDenied("No business workspace.")
    if not access.can_company(request.user, company_id, capability):
        raise PermissionDenied("You do not have access to this business workspace.")
    return company_id


COMPANY_PARAM = OpenApiParameter(
    "company", str, description="Business id (staff access); default: own"
)


# ---- public store -------------------------------------------------------------------------------


@extend_schema(
    tags=["store"], summary="Public store: allowed consumer products (no restricted items)"
)
class StoreProductListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = StoreProductSerializer

    def get_queryset(self):
        qs = Product.objects.consumer_store().select_related(
            "company", "company__governorate", "company__city", "category"
        )
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category__slug=category)
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q) | Q(brand__icontains=q) | Q(description__icontains=q)
            )
        return qs.order_by("title", "id")


@extend_schema(tags=["store"], summary="Public store: one product")
class StoreProductDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = StoreProductSerializer

    def get_queryset(self):
        return Product.objects.consumer_store().select_related("company", "category")


@extend_schema(tags=["store"], summary="Public store categories that currently have products")
class StoreCategoryListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = StoreCategorySerializer
    pagination_class = None

    def get_queryset(self):
        live = Product.objects.consumer_store().values("category_id")
        return ProductCategory.objects.filter(pk__in=live).order_by("sort_order", "name_en")


# ---- buyer orders -------------------------------------------------------------------------------


class MyOrderListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        return _orders().filter(buyer=self.request.user)

    @extend_schema(tags=["store"], summary="My store orders")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["store"],
        summary="Place a store order (prices and totals are computed by the server)",
        request=CheckoutSerializer,
        responses={201: OrderSerializer},
    )
    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            order = services.place_order(
                request.user,
                items=[
                    {"product": line["product"], "quantity": line["quantity"]}
                    for line in data["items"]
                ],
                delivery={
                    "governorate": data["governorate"],
                    "city": data.get("city"),
                    "address": data["address"],
                    "phone": data["phone"],
                    "note": data.get("note", ""),
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                },
                payment_method=data["payment_method"],
            )
        except services.CommerceError as exc:
            raise_api(exc)
        return Response(
            OrderSerializer(_orders().get(pk=order.pk)).data, status=status.HTTP_201_CREATED
        )


class DeliveryDefaultsView(APIView):
    """The caller's own last delivery details (to pre-fill checkout); nobody else's."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["store"],
        summary="My default delivery details (last order, else my account phone)",
        responses=DeliveryDefaultsSerializer,
    )
    def get(self, request):
        last = (
            Order.objects.filter(buyer=request.user)
            .order_by("-created_at")
            .values(
                "delivery_governorate_id", "delivery_city_id", "delivery_address", "contact_phone"
            )
            .first()
        )
        payload = {
            "governorate": str(last["delivery_governorate_id"]) if last else None,
            "city": str(last["delivery_city_id"]) if last and last["delivery_city_id"] else None,
            "address": last["delivery_address"] if last else "",
            "phone": last["contact_phone"] if last else request.user.phone_number,
        }
        return Response(DeliveryDefaultsSerializer(payload).data)


@extend_schema(tags=["store"], summary="One of my store orders")
class MyOrderDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        return _orders().filter(buyer=self.request.user)


class MyOrderCancelView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["store"],
        summary="Cancel my order (before it ships)",
        request=CancelSerializer,
        responses=OrderSerializer,
    )
    def post(self, request, pk):
        serializer = CancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.cancel_as_buyer(
                pk, buyer=request.user, reason=serializer.validated_data["reason"]
            )
        except services.CommerceError as exc:
            raise_api(exc)
        return Response(OrderSerializer(_orders().get(pk=pk)).data)


# ---- merchant (owner or authorized staff) -------------------------------------------------------


@extend_schema(tags=["store"], summary="Store orders of my business", parameters=[COMPANY_PARAM])
class MerchantOrderListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        company_id = _merchant_company_id(self.request, "company.orders.view")
        qs = _orders().filter(merchant_id=company_id)
        wanted = self.request.query_params.get("status")
        return qs.filter(status=wanted) if wanted else qs


@extend_schema(tags=["store"], summary="One order of my business", parameters=[COMPANY_PARAM])
class MerchantOrderDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        return _orders().filter(
            merchant_id=_merchant_company_id(self.request, "company.orders.view")
        )


class MerchantOrderTransitionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["store"],
        summary="Move an order (confirm, ship, deliver, cancel)",
        parameters=[COMPANY_PARAM],
        request=OrderTransitionRequestSerializer,
        responses=OrderSerializer,
    )
    def post(self, request, pk):
        company_id = _merchant_company_id(request, "company.orders.manage")
        serializer = OrderTransitionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.transition_as_merchant(
                pk,
                company_id=company_id,
                actor=request.user,
                to_status=serializer.validated_data["status"],
                reason=serializer.validated_data["reason"],
            )
        except services.CommerceError as exc:
            raise_api(exc)
        return Response(OrderSerializer(_orders().get(pk=pk)).data)


class MerchantOrderPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["store"],
        summary="Record that a manual transfer was received (nothing is charged)",
        parameters=[COMPANY_PARAM],
        request=None,
        responses=OrderSerializer,
    )
    def post(self, request, pk):
        company_id = _merchant_company_id(request, "company.orders.manage")
        try:
            services.record_payment(pk, company_id=company_id, actor=request.user)
        except services.CommerceError as exc:
            raise_api(exc)
        return Response(OrderSerializer(_orders().get(pk=pk)).data)


# ---- quotes -------------------------------------------------------------------------------------


def _quotes():
    return QuoteRequest.objects.select_related("product", "company", "requester")


def _provider(request):
    provider = current_verified_provider(request.user)
    if provider is None:
        raise PermissionDenied(BROWSE_DENIED)
    return provider


class MyQuoteListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = QuoteSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return QuoteRequest.objects.none()
        return _quotes().filter(requester=_provider(self.request))

    @extend_schema(tags=["quotes"], summary="My quote requests (verified providers)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["quotes"],
        summary="Ask a business for a price on a product targeted at me",
        request=QuoteCreateSerializer,
        responses={201: QuoteSerializer},
    )
    def post(self, request):
        provider = _provider(request)
        serializer = QuoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            quote = services.request_quote(
                provider,
                account=request.user,
                product_id=serializer.validated_data["product"],
                quantity=serializer.validated_data["quantity"],
                message=serializer.validated_data["message"],
            )
        except services.CommerceError as exc:
            raise_api(exc)
        return Response(
            QuoteSerializer(_quotes().get(pk=quote.pk)).data, status=status.HTTP_201_CREATED
        )


class MyQuoteCloseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["quotes"],
        summary="Accept, decline or withdraw my quote request",
        request=QuoteCloseSerializer,
        responses=QuoteSerializer,
    )
    def post(self, request, pk):
        provider = _provider(request)
        serializer = QuoteCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.close_as_requester(
                pk,
                provider=provider,
                actor=request.user,
                outcome=serializer.validated_data["outcome"],
            )
        except services.CommerceError as exc:
            raise_api(exc)
        return Response(QuoteSerializer(_quotes().get(pk=pk)).data)


@extend_schema(
    tags=["quotes"], summary="Quote requests received by my business", parameters=[COMPANY_PARAM]
)
class MerchantQuoteListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = QuoteSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return QuoteRequest.objects.none()
        qs = _quotes().filter(company_id=_merchant_company_id(self.request, "company.quotes.view"))
        wanted = self.request.query_params.get("status")
        return qs.filter(status=wanted) if wanted else qs


class MerchantQuoteRespondView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["quotes"],
        summary="Send a price for a request",
        parameters=[COMPANY_PARAM],
        request=QuoteRespondSerializer,
        responses=QuoteSerializer,
    )
    def post(self, request, pk):
        company_id = _merchant_company_id(request, "company.quotes.respond")
        serializer = QuoteRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.respond_quote(
                pk,
                company_id=company_id,
                actor=request.user,
                unit_price=serializer.validated_data["unit_price"],
                note=serializer.validated_data["note"],
            )
        except services.CommerceError as exc:
            raise_api(exc)
        return Response(QuoteSerializer(_quotes().get(pk=pk)).data)


class MerchantQuoteDeclineView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["quotes"],
        summary="Decline a request",
        parameters=[COMPANY_PARAM],
        request=None,
        responses=QuoteSerializer,
    )
    def post(self, request, pk):
        company_id = _merchant_company_id(request, "company.quotes.respond")
        try:
            services.decline_as_company(pk, company_id=company_id, actor=request.user)
        except services.CommerceError as exc:
            raise_api(exc)
        return Response(QuoteSerializer(_quotes().get(pk=pk)).data)
