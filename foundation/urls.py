from django.urls import path

from . import views

app_name = "foundation"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("start/", views.start, name="start"),
    path("my/", views.mine, name="mine"),
    path("mpesa/callback/", views.mpesa_callback, name="mpesa_callback"),
    path("donation/<str:reference>/", views.pay, name="pay"),
    path("donation/<str:reference>/retry/", views.pay_retry, name="pay_retry"),
    path("donation/<str:reference>/status/", views.pay_status, name="pay_status"),
    path("donation/<str:reference>/airtel/", views.airtel_submit, name="airtel"),
    path("donation/<str:reference>/thank-you/", views.thanks, name="thanks"),
    path("f/<slug:slug>/", views.campaign, name="campaign"),
    path("f/<slug:slug>/donate/", views.donate, name="donate"),
    path("f/<slug:slug>/update/", views.post_update, name="post_update"),
]
