from django.urls import path

from .views import LittleLemonTokenCreateView, LittleLemonTokenLogoutView

urlpatterns = [
    path("login", LittleLemonTokenCreateView.as_view(), name="token-login"),
    path("login/", LittleLemonTokenCreateView.as_view(), name="token-login-slash"),
    path("logout", LittleLemonTokenLogoutView.as_view(), name="token-logout"),
    path("logout/", LittleLemonTokenLogoutView.as_view(), name="token-logout-slash"),
]
