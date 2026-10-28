from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    path("password-reset/", views.password_reset, name="password_reset"),
    path("password-reset/<uidb64>/<token>/", views.password_reset_confirm, name="password_reset_confirm"),
    path("", views.profile, name="profile"),
    path("password/", views.change_password, name="change_password"),
    path("orders/", views.my_orders, name="orders"),
]
