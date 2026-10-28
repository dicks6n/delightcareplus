from decimal import Decimal

from django.db import models
from django.utils import timezone


class Coupon(models.Model):
    TYPE_CHOICES = (
        ("percent", "Percentage off"),
        ("fixed", "Fixed amount off (KES)"),
        ("free_delivery", "Free delivery"),
    )

    code = models.CharField(max_length=30, unique=True, help_text="Customers type this, e.g. WELCOME10")
    description = models.CharField(max_length=160, blank=True, help_text="Shown to the customer, e.g. 10% off your first order")
    discount_type = models.CharField(max_length=15, choices=TYPE_CHOICES, default="percent")
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="10 = 10% or KES 10")
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text="Empty = unlimited")
    used_count = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    first_order_only = models.BooleanField(default=False, help_text="Only for customers who haven't ordered before")
    referrer = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.CASCADE, related_name="referral_coupons",
                                 help_text="Set for refer-a-friend codes: this customer earns points when the code is used")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.code

    def check_valid(self, subtotal, user=None):
        now = timezone.now()
        if not self.is_active:
            return False, "This coupon is no longer active."
        if user is not None and user.is_authenticated:
            if self.referrer_id == user.id:
                return False, "That's your own invite code — share it with friends instead."
            if self.first_order_only and user.orders.exclude(status__in=["CANCELLED", "FAILED"]).exists():
                return False, "This code is for first orders only."
        if self.valid_from and now < self.valid_from:
            return False, "This coupon isn't active yet."
        if self.valid_until and now > self.valid_until:
            return False, "This coupon has expired."
        if self.max_uses is not None and self.used_count >= self.max_uses:
            return False, "This coupon has been fully used."
        if subtotal < self.min_order_amount:
            return False, f"Spend KES {self.min_order_amount:,.0f} or more to use this coupon."
        return True, "Coupon applied!"

    def discount_for(self, subtotal):
        if self.discount_type == "percent":
            amount = subtotal * self.value / Decimal("100")
        elif self.discount_type == "fixed":
            amount = self.value
        else:
            amount = Decimal("0")
        return min(amount, subtotal).quantize(Decimal("0.01"))


class DeliveryZone(models.Model):
    """
    Delivery pricing like Jumia/Kilimall: a zone (where), a method (pickup station or
    door delivery) and parcel weight. Edit prices any time in admin.
    """
    name = models.CharField(max_length=80, unique=True)
    towns = models.TextField(help_text="One town/area per line — customers pick from these at checkout")
    pickup_stations = models.TextField(blank=True, help_text="One pickup point per line (leave empty if none in this zone)")
    pickup_fee = models.DecimalField(max_digits=8, decimal_places=2, help_text="Pickup station fee for the first kg")
    home_fee = models.DecimalField(max_digits=8, decimal_places=2, help_text="Home/office delivery fee for the first kg")
    extra_kg_fee = models.DecimalField(max_digits=8, decimal_places=2, default=50, help_text="Added for every extra kg (or part kg)")
    delivery_days = models.CharField(max_length=40, default="1-2 days", help_text="Shown to customers, e.g. Same day, 2-4 days")
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name

    @property
    def town_list(self):
        return [t.strip() for t in self.towns.splitlines() if t.strip()]

    @property
    def station_list(self):
        return [t.strip() for t in self.pickup_stations.splitlines() if t.strip()]

    def fee(self, method, weight_kg):
        import math
        base = self.pickup_fee if (method == "pickup" and self.station_list) else self.home_fee
        extra_kg = max(0, math.ceil(Decimal(weight_kg) - 1))
        return (base + self.extra_kg_fee * extra_kg).quantize(Decimal("0.01"))
