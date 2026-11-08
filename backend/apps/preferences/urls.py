from django.urls import path

from . import views

urlpatterns = [
    path("me/preferences", views.MyPreferencesView.as_view(), name="me-preferences"),
]
