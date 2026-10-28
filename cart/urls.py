from django.urls import path

from . import views

app_name = "cart"

urlpatterns = [
    path("", views.cart_page, name="page"),
    path("add/", views.add, name="add"),
    path("update/<int:variant_id>/", views.update, name="update"),
    path("remove/<int:variant_id>/", views.remove, name="remove"),
    path("clear/", views.clear, name="clear"),
    path("coupon/", views.coupon_apply, name="coupon_apply"),
    path("coupon/remove/", views.coupon_remove, name="coupon_remove"),
    path("count/", views.count, name="count"),
    path("points/", views.toggle_points, name="points"),
    path("delivery/", views.delivery_quote, name="delivery_quote"),
]
