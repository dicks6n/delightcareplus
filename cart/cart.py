"""
Session cart.

The cart lives in request.session["cart"] as {variant_id: quantity}, so it
works for guests and survives logging in.
"""
from decimal import Decimal

from django.conf import settings

from catalog.models import Variant

from .models import Coupon

MAX_QTY = 99
SESSION_KEY = "cart"
COUPON_KEY = "coupon_code"
POINTS_KEY = "use_points"
POINTS_MAX_SHARE = Decimal("0.20")   # points can pay up to 20% of the goods
POINTS_PER_KES_100 = 1               # earn 1 point per KES 100 spent (1 point = KES 1)


def _d(value):
    return Decimal(str(value))


class Cart:
    def __init__(self, request):
        self.session = request.session
        self.user = request.user
        raw = self.session.get(SESSION_KEY, {})
        # Older formats are ignored safely
        self.data = {str(k): int(v) for k, v in raw.items() if str(v).isdigit()} if isinstance(raw, dict) else {}

    # ------------------------------------------------------------------ writes
    def _save(self):
        self.session[SESSION_KEY] = self.data
        self.session.modified = True

    def add(self, variant, quantity=1):
        key = str(variant.id)
        self.data[key] = min(MAX_QTY, self.data.get(key, 0) + max(1, int(quantity)))
        self._save()

    def set(self, variant_id, quantity):
        key = str(variant_id)
        if key not in self.data:
            return False
        if quantity <= 0:
            del self.data[key]
        else:
            self.data[key] = min(MAX_QTY, quantity)
        self._save()
        return True

    def remove(self, variant_id):
        return self.set(variant_id, 0)

    def clear(self):
        self.data = {}
        self.session.pop(COUPON_KEY, None)
        self._save()

    def apply_coupon(self, code):
        coupon = Coupon.objects.filter(code__iexact=code.strip()).first()
        if not coupon:
            return False, "That coupon code doesn't exist."
        ok, msg = coupon.check_valid(self.summary()["subtotal"])
        if ok:
            self.session[COUPON_KEY] = coupon.code
            self.session.modified = True
        return ok, msg

    def use_points(self, on=True):
        self.session[POINTS_KEY] = bool(on)
        self.session.modified = True

    def remove_coupon(self):
        self.session.pop(COUPON_KEY, None)
        self.session.modified = True

    # ------------------------------------------------------------------- reads
    @property
    def count(self):
        return sum(self.data.values())

    def __len__(self):
        return self.count

    def lines(self):
        variants = Variant.objects.select_related("product", "product__brand").in_bulk(
            [int(k) for k in self.data]
        )
        lines, stale = [], []
        for key, qty in self.data.items():
            v = variants.get(int(key))
            if not v or not v.product.is_active:
                stale.append(key)
                continue
            lines.append({
                "key": key,
                "variant": v,
                "product": v.product,
                "quantity": qty,
                "unit_price": v.price,
                "total": v.price * qty,
            })
        if stale:
            for key in stale:
                self.data.pop(key, None)
            self._save()
        return lines

    def summary(self, city=None, method=None):
        """
        Totals for the bag. Delivery depends on the town + pickup/home choice
        (saved in the session) and the parcel weight. No tax line — prices are final.
        """
        from . import delivery

        lines = self.lines()
        subtotal = sum((l["total"] for l in lines), Decimal("0"))

        coupon, discount, coupon_error = None, Decimal("0"), None
        code = self.session.get(COUPON_KEY)
        if code:
            coupon = Coupon.objects.filter(code__iexact=code).first()
            if coupon:
                ok, msg = coupon.check_valid(subtotal)
                if ok:
                    discount = coupon.discount_for(subtotal)
                else:
                    coupon, coupon_error = None, msg
            else:
                self.remove_coupon()

        saved_city, saved_method = delivery.get_choice(self.session)
        city = city if city is not None else saved_city
        method = method or saved_method

        grams = sum(l["product"].shipping_weight * l["quantity"] for l in lines)
        weight_kg = (Decimal(grams) / 1000).quantize(Decimal("0.01"))
        zone = delivery.zone_for(city) if city else None

        # Glow Points (members only)
        from accounts.models import points_balance
        balance = points_balance(self.user) if lines else 0
        max_points = int((subtotal - discount) * POINTS_MAX_SHARE)
        points_used = min(balance, max_points) if self.session.get(POINTS_KEY) else 0
        discount_points = Decimal(points_used)

        after_discount = subtotal - discount - discount_points
        from core.models import SiteSettings
        free_over = SiteSettings.load().free_delivery_over
        free_delivery = bool(lines) and (
            (coupon and coupon.discount_type == "free_delivery") or (free_over > 0 and after_discount >= free_over)
        )
        if not lines or free_delivery:
            delivery_fee = Decimal("0")
        elif zone:
            delivery_fee = zone.fee(method, weight_kg)
        else:
            delivery_fee = None   # unknown until the shopper picks a town

        total = after_discount + (delivery_fee or Decimal("0"))

        return {
            "lines": lines,
            "count": sum(l["quantity"] for l in lines),
            "subtotal": subtotal,
            "coupon": coupon,
            "coupon_error": coupon_error,
            "discount": discount,
            "points_balance": balance,
            "points_usable": min(balance, max_points),
            "points_used": points_used,
            "points_to_earn": int(after_discount // 100) * POINTS_PER_KES_100,
            "city": city,
            "zone": zone,
            "delivery_method": method if (zone is None or method == "home" or zone.station_list) else "home",
            "delivery": delivery_fee,
            "delivery_known": delivery_fee is not None,
            "free_delivery": free_delivery,
            "free_delivery_over": free_over,
            "to_free_delivery": max(Decimal("0"), free_over - after_discount) if free_over > 0 else Decimal("0"),
            "weight_kg": weight_kg,
            "total": total,
        }

    def summary_json(self, city=None, method=None):
        s = self.summary(city, method)
        return {
            "count": s["count"],
            "subtotal": float(s["subtotal"]),
            "discount": float(s["discount"]),
            "points_used": s["points_used"],
            "points_to_earn": s["points_to_earn"],
            "delivery": float(s["delivery"]) if s["delivery_known"] else None,
            "delivery_method": s["delivery_method"],
            "zone": s["zone"].name if s["zone"] else "",
            "delivery_days": s["zone"].delivery_days if s["zone"] else "",
            "pickup_stations": s["zone"].station_list if s["zone"] else [],
            "free_delivery": s["free_delivery"],
            "to_free_delivery": float(s["to_free_delivery"]),
            "weight_kg": float(s["weight_kg"]),
            "total": float(s["total"]),
            "coupon": s["coupon"].code if s["coupon"] else "",
            "coupon_error": s["coupon_error"] or "",
        }
