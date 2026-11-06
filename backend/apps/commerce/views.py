"""Commerce API. Ownership is never taken from a client id without a server-side check:
buyers see their own orders; seller endpoints resolve the business from the caller's ownership
or an ACTIVE staff membership with the needed capability (apps.workspaces.access); finance
endpoints require a Racheeta staff account with the finance permission."""

from django.db.models import Prefetch, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminAccount
from apps.ledger.posting import LedgerError
from apps.ledger.settlement import is_finance
from apps.marketplace.models import MedicalCompany, Product, ProductCategory
from apps.marketplace.permissions import BROWSE_DENIED, current_verified_provider
from apps.marketplace.serializers import StoreCategorySerializer, StoreProductSerializer
from apps.workspaces import access

from . import checkout, inventory, lifecycle, promotions, services
from .errors import CommerceError
from .models import (
    Checkout,
    Coupon,
    Dispute,
    Order,
    OrderTransition,
    ProductOffer,
    QuoteRequest,
    ReturnRequest,
    StockMovement,
)
from .serializers import (
    AdminOrderSerializer,
    CancelSerializer,
    CartPreviewRequestSerializer,
    CheckoutPreviewSerializer,
    CheckoutResultSerializer,
    CheckoutSerializer,
    CouponCreateSerializer,
    CouponSerializer,
    DeliveryDefaultsSerializer,
    DisputeCreateSerializer,
    DisputeResolveSerializer,
    DisputeSerializer,
    InventoryRowSerializer,
    OrderSerializer,
    OrderTransitionRequestSerializer,
    ProductSaleCreateSerializer,
    ProductSaleSerializer,
    QuoteCloseSerializer,
    QuoteCreateSerializer,
    QuoteOrderSerializer,
    QuoteRespondSerializer,
    QuoteSerializer,
    ReturnCreateSerializer,
    ReturnDecisionSerializer,
    ReturnSerializer,
    SellerOrderSerializer,
    StockAdjustSerializer,
    StockMovementSerializer,
    StockThresholdSerializer,
    VerifyPaymentSerializer,
    preview_payload,
)
from .types import CouponFunding

STATUS_FOR_CODE = {
    "not_allowed": status.HTTP_403_FORBIDDEN,
    "professional_only": status.HTTP_403_FORBIDDEN,
    "not_purchasable": status.HTTP_403_FORBIDDEN,
    "not_found": status.HTTP_404_NOT_FOUND,
    "out_of_stock": status.HTTP_409_CONFLICT,
    "invalid_transition": status.HTTP_409_CONFLICT,
    "already_exists": status.HTTP_409_CONFLICT,
    "stale": status.HTTP_409_CONFLICT,
}


class CommerceAPIError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST


def raise_api(exc: Exception):
    code = getattr(exc, "code", "commerce_error")
    err = CommerceAPIError(str(exc) or code, code=code)
    err.status_code = STATUS_FOR_CODE.get(code, status.HTTP_400_BAD_REQUEST)
    raise err from exc


ERRORS = (CommerceError, LedgerError)


def _orders():
    return Order.objects.select_related(
        "merchant",
        "buyer",
        "checkout",
        "delivery_governorate",
        "delivery_city",
        "payment_verified_by",
    ).prefetch_related(
        "items__product",
        "refunds",
        Prefetch("returns", queryset=ReturnRequest.objects.prefetch_related("lines__item")),
        "disputes",
        Prefetch("transitions", queryset=OrderTransition.objects.order_by("created_at")),
    )


def _merchant_company_id(request, capability: str):
    """Business to act for: `?company=<id>` (owner or authorized staff) or the caller's own."""
    company_id = request.query_params.get("company") or access.own_company_id(request.user)
    if not company_id:
        raise PermissionDenied("No business workspace.")
    if not access.can_company(request.user, company_id, capability):
        raise PermissionDenied("You do not have access to this business workspace.")
    return company_id


class IsFinance(BasePermission):
    """Racheeta staff WITH the finance permission (support staff without it are refused)."""

    message = "Racheeta finance only."

    def has_permission(self, request, view) -> bool:
        return is_finance(request.user)


COMPANY_PARAM = OpenApiParameter(
    "company", str, description="Business id (staff access); default: own"
)
FINANCE = [IsAuthenticated, IsAdminAccount, IsFinance]


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


# ---- checkout -----------------------------------------------------------------------------------


class CheckoutPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["store"],
        summary="Price a cart on the server: per-seller orders, offers, coupons, totals",
        request=CartPreviewRequestSerializer,
        responses=CheckoutPreviewSerializer,
    )
    def post(self, request):
        serializer = CartPreviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            priced, _ = checkout.preview(
                request.user,
                items=[dict(line) for line in data["items"]],
                coupons=data["coupons"],
            )
        except ERRORS as exc:
            raise_api(exc)
        return Response(CheckoutPreviewSerializer(preview_payload(priced)).data)


def _checkout_response(pk, code):
    result = Checkout.objects.prefetch_related(
        Prefetch("orders", queryset=_orders().order_by("created_at"))
    ).get(pk=pk)
    return Response(CheckoutResultSerializer(result).data, status=code)


class CheckoutListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["store"],
        summary="Place one checkout (one order per seller); prices are computed by the server",
        request=CheckoutSerializer,
        responses={201: CheckoutResultSerializer, 200: CheckoutResultSerializer},
    )
    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result, created = checkout.place(
                request.user,
                items=[dict(line) for line in data["items"]],
                coupons=data["coupons"],
                delivery=serializer.delivery(),
                payment_method=data["payment_method"],
                idempotency_key=data["idempotency_key"],
            )
        except ERRORS as exc:
            raise_api(exc)
        return _checkout_response(
            result.pk, status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


# ---- buyer orders -------------------------------------------------------------------------------


@extend_schema(tags=["store"], summary="My store orders")
class MyOrderListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        return _orders().filter(buyer=self.request.user)


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


def _buyer_action(summary, request_serializer, run):
    class View(APIView):
        permission_classes = [IsAuthenticated]

        @extend_schema(
            tags=["store"], summary=summary, request=request_serializer, responses=OrderSerializer
        )
        def post(self, request, pk):
            data = {}
            if request_serializer is not None:
                serializer = request_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                data = serializer.validated_data
            try:
                run(pk, request.user, data)
            except ERRORS as exc:
                raise_api(exc)
            return Response(OrderSerializer(_orders().get(pk=pk, buyer=request.user)).data)

    return View


MyOrderCancelView = _buyer_action(
    "Cancel my order (before it ships)",
    CancelSerializer,
    lambda pk, user, d: lifecycle.buyer_cancel(pk, buyer=user, reason=d["reason"]),
)
MyOrderCancelView.__name__ = "MyOrderCancelView"
MyOrderConfirmDeliveryView = _buyer_action(
    "Confirm I received my order",
    None,
    lambda pk, user, d: lifecycle.confirm_delivery(pk, actor=user),
)
MyOrderConfirmDeliveryView.__name__ = "MyOrderConfirmDeliveryView"
MyOrderReturnView = _buyer_action(
    "Ask to return items (within the return window)",
    ReturnCreateSerializer,
    lambda pk, user, d: lifecycle.request_return(
        pk, buyer=user, lines=[dict(x) for x in d["lines"]], reason=d["reason"]
    ),
)
MyOrderReturnView.__name__ = "MyOrderReturnView"
MyOrderDisputeView = _buyer_action(
    "Open a dispute with Racheeta about this order",
    DisputeCreateSerializer,
    lambda pk, user, d: lifecycle.open_dispute(pk, buyer=user, reason=d["reason"]),
)
MyOrderDisputeView.__name__ = "MyOrderDisputeView"


# ---- seller (owner or authorized staff) ---------------------------------------------------------


@extend_schema(tags=["seller"], summary="Store orders of my business", parameters=[COMPANY_PARAM])
class MerchantOrderListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SellerOrderSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        company_id = _merchant_company_id(self.request, "company.orders.view")
        qs = _orders().filter(merchant_id=company_id)
        wanted = self.request.query_params.get("status")
        return qs.filter(status=wanted) if wanted else qs


@extend_schema(tags=["seller"], summary="One order of my business", parameters=[COMPANY_PARAM])
class MerchantOrderDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SellerOrderSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        return _orders().filter(
            merchant_id=_merchant_company_id(self.request, "company.orders.view")
        )


class MerchantOrderTransitionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["seller"],
        summary="Accept, decline or ship an order",
        parameters=[COMPANY_PARAM],
        request=OrderTransitionRequestSerializer,
        responses=SellerOrderSerializer,
    )
    def post(self, request, pk):
        company_id = _merchant_company_id(request, "company.orders.manage")
        serializer = OrderTransitionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            lifecycle.seller_transition(
                pk,
                company_id=company_id,
                actor=request.user,
                to_status=data["status"],
                reason=data["reason"],
                shipping_reference=data["shipping_reference"],
            )
        except ERRORS as exc:
            raise_api(exc)
        return Response(SellerOrderSerializer(_orders().get(pk=pk)).data)


def _returns():
    return ReturnRequest.objects.select_related("order").prefetch_related("lines__item")


@extend_schema(
    tags=["seller"], summary="Return requests for my business", parameters=[COMPANY_PARAM]
)
class MerchantReturnListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ReturnSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ReturnRequest.objects.none()
        company_id = _merchant_company_id(self.request, "company.orders.view")
        return _returns().filter(order__merchant_id=company_id)


class MerchantReturnDecideView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["seller"],
        summary="Approve or reject a return request",
        parameters=[COMPANY_PARAM],
        request=ReturnDecisionSerializer,
        responses=ReturnSerializer,
    )
    def post(self, request, pk):
        company_id = _merchant_company_id(request, "company.returns.manage")
        serializer = ReturnDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            lifecycle.decide_return(
                pk, company_id=company_id, actor=request.user, **serializer.validated_data
            )
        except ERRORS as exc:
            raise_api(exc)
        return Response(ReturnSerializer(_returns().get(pk=pk)).data)


class MerchantReturnReceivedView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["seller"],
        summary="Returned items arrived back (restocks them)",
        parameters=[COMPANY_PARAM],
        request=None,
        responses=ReturnSerializer,
    )
    def post(self, request, pk):
        company_id = _merchant_company_id(request, "company.returns.manage")
        try:
            lifecycle.receive_return(pk, company_id=company_id, actor=request.user)
        except ERRORS as exc:
            raise_api(exc)
        return Response(ReturnSerializer(_returns().get(pk=pk)).data)


def _inventory_row(product) -> dict:
    left = inventory.available(product)
    return {
        "id": product.pk,
        "title": product.title,
        "image_url": product.image_url or "",
        "is_active": product.is_active,
        "price": product.price,
        "on_hand": product.stock_quantity,
        "reserved": product.stock_reserved,
        "available": left,
        "reorder_threshold": product.reorder_threshold,
        "low": bool(
            left is not None
            and product.reorder_threshold is not None
            and left <= product.reorder_threshold
        ),
    }


class MerchantInventoryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["seller"],
        summary="Stock of my products: on hand, reserved, available, alert level",
        parameters=[COMPANY_PARAM],
        responses=InventoryRowSerializer(many=True),
    )
    def get(self, request):
        company_id = _merchant_company_id(request, "company.products.view")
        products = Product.objects.filter(company_id=company_id).order_by("title", "id")
        return Response(
            InventoryRowSerializer([_inventory_row(p) for p in products], many=True).data
        )


class MerchantStockAdjustView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["seller"],
        summary="Adjust on-hand stock (with a reason; never below reserved units)",
        parameters=[COMPANY_PARAM],
        request=StockAdjustSerializer,
        responses=InventoryRowSerializer,
    )
    def post(self, request, pk):
        company_id = _merchant_company_id(request, "company.stock.manage")
        serializer = StockAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            product = inventory.adjust(
                pk, company_id=company_id, actor=request.user, **serializer.validated_data
            )
        except ERRORS as exc:
            raise_api(exc)
        return Response(InventoryRowSerializer(_inventory_row(product)).data)


class MerchantStockThresholdView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["seller"],
        summary="Set the low-stock alert level of a product",
        parameters=[COMPANY_PARAM],
        request=StockThresholdSerializer,
        responses=InventoryRowSerializer,
    )
    def post(self, request, pk):
        company_id = _merchant_company_id(request, "company.stock.manage")
        serializer = StockThresholdSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            product = inventory.set_threshold(
                pk, company_id=company_id, threshold=serializer.validated_data["threshold"]
            )
        except ERRORS as exc:
            raise_api(exc)
        return Response(InventoryRowSerializer(_inventory_row(product)).data)


@extend_schema(
    tags=["seller"], summary="Stock movement history of a product", parameters=[COMPANY_PARAM]
)
class MerchantStockMovementListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StockMovementSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return StockMovement.objects.none()
        company_id = _merchant_company_id(self.request, "company.products.view")
        return (
            StockMovement.objects.filter(
                product_id=self.kwargs["pk"], product__company_id=company_id
            )
            .select_related("order")
            .order_by("-created_at", "id")
        )


class MerchantCouponListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CouponSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Coupon.objects.none()
        company_id = _merchant_company_id(self.request, "company.offers.manage")
        return Coupon.objects.filter(company_id=company_id).select_related("company")

    @extend_schema(tags=["seller"], summary="My store coupons", parameters=[COMPANY_PARAM])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["seller"],
        summary="Create a store coupon (seller-funded: lowers the commission base)",
        parameters=[COMPANY_PARAM],
        request=CouponCreateSerializer,
        responses={201: CouponSerializer},
    )
    def post(self, request):
        company_id = _merchant_company_id(request, "company.offers.manage")
        serializer = CouponCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            coupon = promotions.create_coupon(
                actor=request.user,
                funded_by=CouponFunding.SELLER,
                company=MedicalCompany.objects.get(pk=company_id),
                **serializer.validated_data,
            )
        except ERRORS as exc:
            raise_api(exc)
        return Response(CouponSerializer(coupon).data, status=status.HTTP_201_CREATED)


class MerchantCouponDeactivateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["seller"],
        summary="Stop a store coupon",
        parameters=[COMPANY_PARAM],
        request=None,
        responses=CouponSerializer,
    )
    def post(self, request, pk):
        company_id = _merchant_company_id(request, "company.offers.manage")
        try:
            coupon = promotions.deactivate_coupon(pk, actor=request.user, company_id=company_id)
        except ERRORS as exc:
            raise_api(exc)
        return Response(CouponSerializer(coupon).data)


class MerchantOfferListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProductSaleSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ProductOffer.objects.none()
        company_id = _merchant_company_id(self.request, "company.offers.manage")
        return ProductOffer.objects.filter(company_id=company_id).select_related("product")

    @extend_schema(tags=["seller"], summary="My product sales", parameters=[COMPANY_PARAM])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["seller"],
        summary="Put a product on sale for a period (seller-funded)",
        parameters=[COMPANY_PARAM],
        request=ProductSaleCreateSerializer,
        responses={201: ProductSaleSerializer},
    )
    def post(self, request):
        company_id = _merchant_company_id(request, "company.offers.manage")
        serializer = ProductSaleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            offer = promotions.create_offer(
                actor=request.user,
                company=MedicalCompany.objects.get(pk=company_id),
                product_id=data["product"],
                percent=data["percent"],
                starts_at=data.get("starts_at"),
                ends_at=data["ends_at"],
            )
        except ERRORS as exc:
            raise_api(exc)
        return Response(ProductSaleSerializer(offer).data, status=status.HTTP_201_CREATED)


class MerchantOfferDeactivateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["seller"],
        summary="End a product sale",
        parameters=[COMPANY_PARAM],
        request=None,
        responses=ProductSaleSerializer,
    )
    def post(self, request, pk):
        company_id = _merchant_company_id(request, "company.offers.manage")
        try:
            offer = promotions.deactivate_offer(pk, actor=request.user, company_id=company_id)
        except ERRORS as exc:
            raise_api(exc)
        return Response(ProductSaleSerializer(offer).data)


# ---- Racheeta finance (staff with the finance permission) ---------------------------------------


@extend_schema(tags=["finance"], summary="All marketplace orders (filterable)")
class AdminOrderListView(generics.ListAPIView):
    permission_classes = FINANCE
    serializer_class = AdminOrderSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        qs = _orders()
        params = self.request.query_params
        for field in ("status", "payment_status", "settlement_state", "merchant"):
            if params.get(field):
                qs = qs.filter(**{f"{field}_id" if field == "merchant" else field: params[field]})
        q = (params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(number__icontains=q) | Q(checkout__number__icontains=q))
        return qs


@extend_schema(tags=["finance"], summary="One marketplace order")
class AdminOrderDetailView(generics.RetrieveAPIView):
    permission_classes = FINANCE
    serializer_class = AdminOrderSerializer

    def get_queryset(self):
        return _orders()


def _finance_action(name, summary, request_serializer, run):
    class View(APIView):
        permission_classes = FINANCE

        @extend_schema(
            tags=["finance"],
            summary=summary,
            request=request_serializer,
            responses=AdminOrderSerializer,
        )
        def post(self, request, pk):
            data = {}
            if request_serializer is not None:
                serializer = request_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                data = serializer.validated_data
            try:
                order_id = run(pk, request.user, data)
            except ERRORS as exc:
                raise_api(exc)
            return Response(AdminOrderSerializer(_orders().get(pk=order_id)).data)

    View.__name__ = name
    return View


AdminVerifyPaymentView = _finance_action(
    "AdminVerifyPaymentView",
    "Record SIMULATED payment evidence (no real money) — posts the payment entry once",
    VerifyPaymentSerializer,
    lambda pk, user, d: lifecycle.verify_payment(pk, actor=user, reference=d["reference"]).pk,
)
AdminConfirmDeliveryView = _finance_action(
    "AdminConfirmDeliveryView",
    "Confirm delivery on the buyer's behalf (courier proof)",
    None,
    lambda pk, user, d: lifecycle.confirm_delivery(pk, actor=user, as_finance=True).pk,
)
AdminCompleteOrderView = _finance_action(
    "AdminCompleteOrderView",
    "Complete a paid, delivered order: accrue the 20% commission and the seller payable",
    None,
    lambda pk, user, d: lifecycle.complete(pk, actor=user).pk,
)
AdminRefundCancelledView = _finance_action(
    "AdminRefundCancelledView",
    "Refund a paid order that was cancelled (simulated)",
    None,
    lambda pk, user, d: lifecycle.refund_cancelled(pk, actor=user).order_id,
)


@extend_schema(tags=["finance"], summary="Return requests (all sellers)")
class AdminReturnListView(generics.ListAPIView):
    permission_classes = FINANCE
    serializer_class = ReturnSerializer

    def get_queryset(self):
        qs = _returns()
        wanted = self.request.query_params.get("status")
        return qs.filter(status=wanted) if wanted else qs


AdminReturnRefundView = _finance_action(
    "AdminReturnRefundView",
    "Refund a received return (proportional compensating entry)",
    None,
    lambda pk, user, d: lifecycle.refund_return(pk, actor=user).order_id,
)


@extend_schema(tags=["finance"], summary="Disputes")
class AdminDisputeListView(generics.ListAPIView):
    permission_classes = FINANCE
    serializer_class = DisputeSerializer

    def get_queryset(self):
        qs = Dispute.objects.select_related("order")
        wanted = self.request.query_params.get("status")
        return qs.filter(status=wanted) if wanted else qs


AdminDisputeResolveView = _finance_action(
    "AdminDisputeResolveView",
    "Resolve a dispute (with or without a full refund of what remains)",
    DisputeResolveSerializer,
    lambda pk, user, d: (
        lifecycle.resolve_dispute(pk, actor=user, refund=d["refund"], note=d["note"]).order_id
    ),
)


class AdminCouponListView(generics.ListAPIView):
    permission_classes = FINANCE
    serializer_class = CouponSerializer

    def get_queryset(self):
        return Coupon.objects.select_related("company").order_by("-created_at", "id")

    @extend_schema(tags=["finance"], summary="All coupons (Racheeta- and seller-funded)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["finance"],
        summary="Create a Racheeta coupon (platform-funded: the seller is paid in full)",
        request=CouponCreateSerializer,
        responses={201: CouponSerializer},
    )
    def post(self, request):
        serializer = CouponCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            coupon = promotions.create_coupon(
                actor=request.user, funded_by=CouponFunding.PLATFORM, **serializer.validated_data
            )
        except ERRORS as exc:
            raise_api(exc)
        return Response(CouponSerializer(coupon).data, status=status.HTTP_201_CREATED)


class AdminCouponDeactivateView(APIView):
    permission_classes = FINANCE

    @extend_schema(
        tags=["finance"], summary="Stop a Racheeta coupon", request=None, responses=CouponSerializer
    )
    def post(self, request, pk):
        try:
            coupon = promotions.deactivate_coupon(pk, actor=request.user)
        except ERRORS as exc:
            raise_api(exc)
        return Response(CouponSerializer(coupon).data)


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
        except ERRORS as exc:
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
        except ERRORS as exc:
            raise_api(exc)
        return Response(QuoteSerializer(_quotes().get(pk=pk)).data)


class MyQuoteOrderView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["quotes"],
        summary="Turn my accepted quotation into an order at the quoted price",
        request=QuoteOrderSerializer,
        responses={201: CheckoutResultSerializer, 200: CheckoutResultSerializer},
    )
    def post(self, request, pk):
        provider = _provider(request)
        serializer = QuoteOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result, created = services.order_from_quote(
                pk,
                provider=provider,
                account=request.user,
                delivery=serializer.delivery(),
                payment_method=data["payment_method"],
                idempotency_key=data["idempotency_key"],
            )
        except ERRORS as exc:
            raise_api(exc)
        return _checkout_response(
            result.pk, status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


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
        except ERRORS as exc:
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
        except ERRORS as exc:
            raise_api(exc)
        return Response(QuoteSerializer(_quotes().get(pk=pk)).data)
