from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("track/", views.track, name="track"),
    path("mpesa/callback/", views.mpesa_callback, name="mpesa_callback"),
    path("<str:number>/", views.detail, name="detail"),
    path("<str:number>/pay/", views.pay, name="pay"),
    path("<str:number>/pay/status/", views.pay_status, name="pay_status"),
    path("<str:number>/pay/retry/", views.pay_retry, name="pay_retry"),
    path("<str:number>/pay/airtel/", views.airtel_submit, name="airtel"),
    path("<str:number>/cancel/", views.cancel, name="cancel"),
    path("<str:number>/reorder/", views.reorder, name="reorder"),
]
