from django.urls import path

from . import views

urlpatterns = [
    path("dashboards/", views.DashboardIndexView.as_view(), name="dashboards-index"),
    path("dashboards/patient", views.PatientDashboardView.as_view(), name="dashboard-patient"),
    path("dashboards/doctor", views.DoctorDashboardView.as_view(), name="dashboard-doctor"),
    path("dashboards/facility", views.FacilityDashboardView.as_view(), name="dashboard-facility"),
    path("dashboards/company", views.CompanyDashboardView.as_view(), name="dashboard-company"),
    path(
        "dashboards/recruiter", views.RecruiterDashboardView.as_view(), name="dashboard-recruiter"
    ),
    path("dashboards/admin", views.AdminDashboardView.as_view(), name="dashboard-admin"),
]
