from django.urls import path

from . import views

urlpatterns = [
    path(
        "chat/reservations/<uuid:reservation_id>/conversation",
        views.ReservationConversationView.as_view(),
        name="chat-reservation-conversation",
    ),
    path("chat/conversations/", views.ConversationListView.as_view(), name="chat-conversations"),
    path(
        "chat/conversations/<uuid:pk>/messages/",
        views.ConversationMessagesView.as_view(),
        name="chat-conversation-messages",
    ),
    path(
        "chat/conversations/<uuid:pk>/read/",
        views.ConversationReadView.as_view(),
        name="chat-conversation-read",
    ),
    path("chat/unread-count/", views.ChatUnreadCountView.as_view(), name="chat-unread-count"),
]
