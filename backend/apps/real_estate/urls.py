from django.urls import path

from . import inquiry_views, promotion_views, views

urlpatterns = [
    # public catalogue
    path(
        "real-estate/listings",
        views.PublicListingListView.as_view(),
        name="real-estate-listings",
    ),
    path(
        "real-estate/listings/<uuid:pk>",
        views.PublicListingDetailView.as_view(),
        name="real-estate-listing-detail",
    ),
    # inquiries: seeker side
    path(
        "real-estate/listings/<uuid:pk>/inquiries",
        inquiry_views.ListingInquiryCreateView.as_view(),
        name="real-estate-listing-inquiry",
    ),
    path(
        "real-estate/inquiries/mine",
        inquiry_views.MyInquiryListView.as_view(),
        name="real-estate-my-inquiries",
    ),
    path(
        "real-estate/inquiries/mine/<uuid:pk>/withdraw",
        inquiry_views.MyInquiryWithdrawView.as_view(),
        name="real-estate-my-inquiry-withdraw",
    ),
    # inquiries: owner side
    path(
        "real-estate/owner/inquiries",
        inquiry_views.OwnerInquiryListView.as_view(),
        name="real-estate-owner-inquiries",
    ),
    path(
        "real-estate/owner/inquiries/<uuid:pk>/respond",
        inquiry_views.OwnerInquiryRespondView.as_view(),
        name="real-estate-owner-inquiry-respond",
    ),
    path(
        "real-estate/owner/inquiries/<uuid:pk>/close",
        inquiry_views.OwnerInquiryCloseView.as_view(),
        name="real-estate-owner-inquiry-close",
    ),
    # seller self-service
    path("real-estate/owner", views.MySellerView.as_view(), name="real-estate-owner"),
    path(
        "real-estate/owner/dashboard",
        views.MyDashboardView.as_view(),
        name="real-estate-owner-dashboard",
    ),
    path(
        "real-estate/owner/listings",
        views.MyListingListView.as_view(),
        name="real-estate-owner-listings",
    ),
    path(
        "real-estate/owner/listings/<uuid:pk>",
        views.MyListingDetailView.as_view(),
        name="real-estate-owner-listing",
    ),
    path(
        "real-estate/owner/listings/<uuid:pk>/publish",
        views.MyListingPublishView.as_view(),
        name="real-estate-owner-listing-publish",
    ),
    path(
        "real-estate/owner/listings/<uuid:pk>/unpublish",
        views.MyListingUnpublishView.as_view(),
        name="real-estate-owner-listing-unpublish",
    ),
    # promotions
    path(
        "real-estate/owner/promotions",
        promotion_views.MyPromotionListView.as_view(),
        name="real-estate-owner-promotions",
    ),
    path(
        "real-estate/owner/promotions/<uuid:pk>/end",
        promotion_views.MyPromotionEndView.as_view(),
        name="real-estate-owner-promotion-end",
    ),
    path(
        "real-estate/promoted",
        promotion_views.PromotedListingFeedView.as_view(),
        name="real-estate-promoted",
    ),
    path(
        "admin/real-estate/promotions",
        promotion_views.AdminPromotionListView.as_view(),
        name="admin-real-estate-promotions",
    ),
    path(
        "admin/real-estate/promotions/<uuid:pk>/approve",
        promotion_views.AdminPromotionApproveView.as_view(),
        name="admin-real-estate-promotion-approve",
    ),
    path(
        "admin/real-estate/promotions/<uuid:pk>/reject",
        promotion_views.AdminPromotionRejectView.as_view(),
        name="admin-real-estate-promotion-reject",
    ),
]
