from django.urls import path

from . import routine, views

app_name = "catalog"

urlpatterns = [
    path("", views.shop, name="shop"),
    path("brands/", views.brands, name="brands"),
    path("brand/<slug:slug>/", views.brand, name="brand"),
    path("d/<slug:slug>/", views.department, name="department"),
    path("c/<slug:slug>/", views.category, name="category"),
    path("p/<slug:slug>/", views.product_detail, name="product"),
    path("p/<slug:slug>/review/", views.submit_review, name="review"),
    path("api/quick/<int:pk>/", views.quick_view, name="quick_view"),
    path("api/search/", views.search_suggest, name="search"),
    path("concern/<slug:slug>/", views.concern, name="concern"),
    path("compare/", views.compare, name="compare"),
    path("compare/<int:pk>/toggle/", views.compare_toggle, name="compare_toggle"),
    path("verify/", views.verify, name="verify"),
    path("p/<int:pk>/notify/", views.stock_alert, name="stock_alert"),
    path("routine-finder/", routine.finder, name="routine"),
    path("routine-finder/add/", routine.add_routine, name="routine_add"),
    path("wishlist/", views.wishlist_page, name="wishlist"),
    path("wishlist/<int:pk>/toggle/", views.wishlist_toggle, name="wishlist_toggle"),
    path("wishlist/<int:pk>/to-cart/", views.wishlist_to_cart, name="wishlist_to_cart"),
]
