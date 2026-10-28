from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from orders import views as order_views

admin.site.site_header = "Delight Care Plus — Admin"
admin.site.site_title = "Delight Care Plus"
admin.site.index_title = "Store management"

urlpatterns = [
    path("", include("core.urls")),
    path("shop/", include("catalog.urls")),
    path("cart/", include("cart.urls")),
    path("orders/", include("orders.urls")),
    path("account/", include("accounts.urls")),
    path("chat/", include("chat.urls")),
    path("blog/", include("blog.urls")),
    path("manage/", include("dashboard.urls")),   # staff dashboard (separate from Django admin)
    path("django-admin/", admin.site.urls),
    # The old site's M-Pesa callback address, so payments still confirm if Safaricom or .env uses it
    path("mpesa/callback/", order_views.mpesa_callback),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "core.views.page_not_found"
handler500 = "core.views.server_error"
