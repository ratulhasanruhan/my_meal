from django.contrib.auth import views as auth_views
from django.urls import path

from . import health, views

urlpatterns = [
    path("healthz/", health.healthz, name="healthz"),
    path("", views.dashboard, name="dashboard"),
    path("report/", views.report, name="report"),
    path("analytics/", views.analytics, name="analytics"),
    path("settings/", views.settings_view, name="settings"),
    path("api/set-meal/", views.set_meal, name="set_meal"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="meals/login.html", redirect_authenticated_user=True
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
