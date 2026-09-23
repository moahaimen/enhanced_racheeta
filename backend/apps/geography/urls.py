from django.urls import path

from . import views

urlpatterns = [
    path("geo/countries", views.CountryListView.as_view(), name="geo-countries"),
    path("geo/governorates", views.GovernorateListView.as_view(), name="geo-governorates"),
    path("geo/cities", views.CityListView.as_view(), name="geo-cities"),
]
