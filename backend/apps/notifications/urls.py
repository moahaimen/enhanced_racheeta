from django.urls import path

from . import views

urlpatterns = [
    path(
        "notifications/push-devices/",
        views.PushDeviceRegisterView.as_view(),
        name="notifications-push-devices",
    ),
    path(
        "notifications/push-devices/unregister/",
        views.PushDeviceUnregisterView.as_view(),
        name="notifications-push-devices-unregister",
    ),
    path("notifications/", views.NotificationListView.as_view(), name="notifications"),
    path(
        "notifications/unread-count/",
        views.NotificationUnreadCountView.as_view(),
        name="notifications-unread-count",
    ),
    path(
        "notifications/read-all/",
        views.NotificationMarkAllReadView.as_view(),
        name="notifications-read-all",
    ),
    path(
        "notifications/<uuid:pk>/read/",
        views.NotificationMarkReadView.as_view(),
        name="notification-read",
    ),
]
