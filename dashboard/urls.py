from django.urls import path

from . import marketing_views as mk
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("api/notifications/", views.notifications, name="notifications"),

    path("orders/", views.order_list, name="orders"),
    path("orders/bulk/", views.order_bulk, name="order_bulk"),
    path("orders/<str:number>/", views.order_detail, name="order"),
    path("orders/<str:number>/status/", views.order_status, name="order_status"),
    path("orders/<str:number>/update/", views.order_update, name="order_update"),
    path("orders/<str:number>/invoice/", views.order_invoice, name="order_invoice"),

    path("products/", views.product_list, name="products"),
    path("products/add/", views.product_edit, name="product_add"),
    path("products/bulk/", views.product_bulk, name="product_bulk"),
    path("products/import/", views.product_import, name="product_import"),
    path("products/import/template.csv", views.import_template, name="import_template"),
    path("products/delete-samples/", views.delete_samples, name="delete_samples"),
    path("products/<int:pk>/", views.product_edit, name="product_edit"),
    path("products/<int:pk>/quick/", views.product_quick_edit, name="product_quick"),
    path("products/<int:pk>/duplicate/", views.product_duplicate, name="product_duplicate"),
    path("products/<int:pk>/infographic/", views.product_infographic, name="product_infographic"),
    path("products/<int:pk>/delete/", views.product_delete, name="product_delete"),
    path("products/<int:pk>/batch/", views.batch_add, name="batch_add"),

    path("customers/", views.customer_list, name="customers"),
    path("customers/<int:pk>/", views.customer_detail, name="customer"),
    path("customers/<int:pk>/points/", views.customer_points, name="customer_points"),

    path("reviews/", views.review_list, name="reviews"),
    path("reviews/<int:pk>/", views.review_action, name="review_action"),

    path("marketing/", mk.marketing, name="marketing"),
    path("marketing/ad-studio/", mk.ad_studio, name="ad_studio"),
    path("marketing/ad-studio/<int:pk>/image.jpg", mk.ad_image, name="ad_image"),
    path("marketing/ad-studio/<int:pk>/pack.zip", mk.ad_pack, name="ad_pack"),
    path("marketing/links/", mk.links, name="links"),
    path("marketing/links/add/", mk.link_edit, name="link_add"),
    path("marketing/links/<int:pk>/", mk.link_edit, name="link_edit"),
    path("marketing/emails/", mk.campaigns, name="campaigns"),
    path("marketing/emails/add/", mk.campaign_edit, name="campaign_add"),
    path("marketing/emails/<int:pk>/", mk.campaign_edit, name="campaign"),
    path("marketing/emails/<int:pk>/preview/", mk.campaign_preview, name="campaign_preview"),
    path("marketing/emails/<int:pk>/send/", mk.campaign_send, name="campaign_send"),
    path("marketing/emails/<int:pk>/duplicate/", mk.campaign_duplicate, name="campaign_duplicate"),

    path("inbox/", views.inbox, name="inbox"),
    path("messages/", views.contact_messages, name="contact_messages"),
    path("newsletter/", views.newsletter, name="newsletter"),
    path("stock-alerts/", views.stock_alerts, name="stock_alerts"),
    path("reports/", views.reports, name="reports"),
    path("settings/", views.shop_settings, name="settings"),

    path("<slug:kind>/", views.crud_list, name="crud"),
    path("<slug:kind>/add/", views.crud_edit, name="crud_add"),
    path("<slug:kind>/<int:pk>/", views.crud_edit, name="crud_edit"),
]
