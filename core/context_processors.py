from accounts import wishlist
from cart.cart import Cart
from catalog.models import Brand, Department
from marketing import referrals

from .models import SiteSettings


def site(request):
    if request.path.startswith("/django-admin/"):
        return {}
    wish_ids = wishlist.get_ids(request)
    shop = SiteSettings.load()
    return {
        "shop": shop,
        "nav_departments": Department.objects.filter(is_active=True).prefetch_related("categories"),
        "nav_brands": Brand.objects.all(),
        "cart_count": Cart(request).count,
        "wishlist_ids": wish_ids,
        "wishlist_count": len(wish_ids),
        "referral_offer": referrals.offer_for(request),
        "tracking": _tracking(request, shop),
    }


def _tracking(request, shop):
    """Ad tracking IDs for static/js/tracking.js — None when no platform is set up."""
    if not (shop.meta_pixel_id or shop.tiktok_pixel_id or shop.ga4_id) or request.path.startswith("/manage/"):
        return None
    return {"meta": shop.meta_pixel_id, "tiktok": shop.tiktok_pixel_id, "ga4": shop.ga4_id,
            "consent": request.COOKIES.get("dcp_consent", "")}
