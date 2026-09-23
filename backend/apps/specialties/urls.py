from django.urls import path

from . import views

urlpatterns = [
    path("specialties", views.SpecialtyListView.as_view(), name="specialties"),
]
