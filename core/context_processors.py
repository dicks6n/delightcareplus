from accounts import wishlist
from cart.cart import Cart
from catalog.models import Brand, Department

from .models import SiteSettings


def site(request):
    if request.path.startswith("/django-admin/"):
        return {}
    wish_ids = wishlist.get_ids(request)
    return {
        "shop": SiteSettings.load(),
        "nav_departments": Department.objects.filter(is_active=True).prefetch_related("categories"),
        "nav_brands": Brand.objects.all(),
        "cart_count": Cart(request).count,
        "wishlist_ids": wish_ids,
        "wishlist_count": len(wish_ids),
    }
