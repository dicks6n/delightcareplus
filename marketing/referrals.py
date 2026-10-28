"""Refer-a-friend: each customer gets a personal code. A friend who uses it gets a discount on their first
order; when that order is delivered, the customer earns Glow Points."""
import secrets

from django.db import transaction
from django.utils.text import slugify

from accounts.models import PointsTransaction
from cart.cart import COUPON_KEY
from cart.models import Coupon
from core.models import SiteSettings
from orders.mpesa import format_phone

from .attribution import REF_KEY


def coupon_for(user):
    """The customer's personal refer-a-friend code (created the first time it's needed)."""
    shop = SiteSettings.load()
    coupon = Coupon.objects.filter(referrer=user).first()
    if coupon:
        if coupon.value != shop.referral_discount_percent:  # keep in step with the shop's current offer
            coupon.value = shop.referral_discount_percent
            coupon.save(update_fields=["value"])
        return coupon
    first = user.first_name or user.username.split("@")[0]
    base = (slugify(first).replace("-", "")[:8] or "friend").upper()
    while True:
        code = f"{base}{secrets.randbelow(900) + 100}"
        if not Coupon.objects.filter(code__iexact=code).exists():
            break
    return Coupon.objects.create(
        code=code, referrer=user, first_order_only=True, discount_type="percent", value=shop.referral_discount_percent,
        description=f"{shop.referral_discount_percent}% off your first order — a gift from {first.title()}",
    )


def apply_from_session(request):
    """A visitor arrived through ?ref=CODE: put the friend discount in their bag straight away."""
    code = request.session.get(REF_KEY)
    if not code or not SiteSettings.load().referral_enabled:
        return
    coupon = Coupon.objects.filter(code__iexact=code, referrer__isnull=False, is_active=True).first()
    if coupon and not (request.user.is_authenticated and coupon.referrer_id == request.user.id):
        request.session[COUPON_KEY] = coupon.code
        request.session.modified = True


def offer_for(request):
    """The referral banner shown to an invited visitor, or None."""
    code = request.session.get(REF_KEY)
    if not code or request.session.get(COUPON_KEY, "").upper() != code:
        return None
    coupon = Coupon.objects.filter(code__iexact=code, referrer__isnull=False).select_related("referrer").first()
    if not coupon:
        return None
    return {"code": coupon.code, "percent": int(coupon.value),
            "name": (coupon.referrer.first_name or "A friend").title()}


def reward(order):
    """Called when an order is delivered: credit the friend who invited this customer, once per new customer."""
    if order.referral_rewarded or not order.coupon_code:
        return
    shop = SiteSettings.load()
    coupon = Coupon.objects.filter(code__iexact=order.coupon_code, referrer__isnull=False).select_related("referrer").first()
    if not coupon or not shop.referral_points:
        return
    referrer = coupon.referrer
    phone = format_phone(order.phone)
    own_phone = format_phone(getattr(getattr(referrer, "profile", None), "phone", "") or "")
    own_email = (referrer.email or "").lower()
    if (order.user_id == referrer.id or (phone and phone == own_phone)
            or (order.email and order.email.lower() == own_email)):
        return  # using your own code doesn't count
    from orders.models import Order
    with transaction.atomic():
        rewarded = Order.objects.filter(referral_rewarded=True, coupon_code__iexact=coupon.code)
        if any(format_phone(p) == phone for p in rewarded.values_list("phone", flat=True)):
            return  # this friend has already earned the customer a reward
        PointsTransaction.objects.create(user=referrer, points=shop.referral_points, order=order,
                                         reason=f"Friend's first order {order.number} — thank you!")
        Order.objects.filter(pk=order.pk).update(referral_rewarded=True)
        order.referral_rewarded = True
    from core.mail import send
    if referrer.email:
        send(f"You earned {shop.referral_points} Glow Points 🎁", "emails/referral_reward.html",
             {"user": referrer, "points": shop.referral_points}, [referrer.email])


def is_returning_customer(phone, email):
    """For guests: has someone with this phone or email ordered before? (first-order-only codes)"""
    from orders.models import Order
    past = Order.objects.exclude(status__in=["CANCELLED", "FAILED"])
    if email and past.filter(email__iexact=email).exists():
        return True
    phone = format_phone(phone)
    if not phone:
        return False
    # Phones are stored as typed ("0712 345 678", "+254712…"), so compare the last 9 digits
    tail = phone[-9:]
    candidates = past.filter(phone__contains=tail[-3:]).values_list("phone", flat=True)
    return any(format_phone(p) == phone for p in candidates)
