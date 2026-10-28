from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse

from catalog.models import Variant


class Order(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Awaiting Payment"),
        ("PAID", "Paid"),
        ("PROCESSING", "Processing"),
        ("PACKED", "Packed"),
        ("SHIPPED", "Shipped"),
        ("OUT_FOR_DELIVERY", "Out for Delivery"),
        ("DELIVERED", "Delivered"),
        ("CANCELLED", "Cancelled"),
        ("FAILED", "Payment Failed"),
        ("REFUNDED", "Refunded"),
    )
    PAID_STATUSES = ("PAID", "PROCESSING", "PACKED", "SHIPPED", "OUT_FOR_DELIVERY", "DELIVERED")
    CUSTOMER_CANCELLABLE = ("PENDING", "FAILED", "PAID", "PROCESSING")

    PAYMENT_CHOICES = (
        ("mpesa", "M-Pesa"),
        ("airtel", "Airtel Money"),
        ("cod", "Pay on Delivery"),
    )

    number = models.CharField(max_length=20, unique=True, blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")

    # Customer
    full_name = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20)
    city = models.CharField(max_length=80)
    address = models.TextField()
    notes = models.TextField(blank=True)

    # Money
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon_code = models.CharField(max_length=30, blank=True)
    points_redeemed = models.PositiveIntegerField(default=0, help_text="Glow Points used (1 point = KES 1)")
    points_earned = models.PositiveIntegerField(default=0)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    # Payment
    DELIVERY_CHOICES = (("pickup", "Pickup station"), ("home", "Home / office delivery"))
    delivery_method = models.CharField(max_length=10, choices=DELIVERY_CHOICES, default="home")
    delivery_zone = models.CharField(max_length=80, blank=True)
    pickup_station = models.CharField(max_length=120, blank=True)
    parcel_weight_kg = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default="mpesa")
    payment_phone = models.CharField(max_length=20, blank=True)
    payment_reference = models.CharField(max_length=40, blank=True, help_text="M-Pesa receipt or Airtel transaction ID")
    payment_proof = models.ImageField(upload_to="payment_proofs/", blank=True, null=True)
    checkout_request_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    mpesa_result_desc = models.CharField(max_length=255, blank=True)

    # Delivery
    courier = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    estimated_delivery = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    cancellation_reason = models.CharField(max_length=255, blank=True)
    stock_deducted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.number:
            # Orders imported from the old shop keep their numbers, so skip any that are taken
            n = self.id
            while Order.objects.filter(number=f"DCP-{n:05d}").exclude(pk=self.pk).exists():
                n += 1
            self.number = f"DCP-{n:05d}"
            super().save(update_fields=["number"])

    def __str__(self):
        return self.number or f"Order {self.id}"

    def get_absolute_url(self):
        return reverse("orders:detail", args=[self.number])

    @property
    def first_name(self):
        return (self.full_name or "").split(" ")[0]

    @property
    def is_paid(self):
        return self.status in self.PAID_STATUSES

    @property
    def can_cancel(self):
        return self.status in self.CUSTOMER_CANCELLABLE

    @property
    def item_count(self):
        return sum(i.quantity for i in self.items.all())

    @property
    def progress_step(self):
        """0–4 for the tracking bar: placed, paid, packed, shipped, delivered."""
        steps = {"PENDING": 0, "FAILED": 0, "PAID": 1, "PROCESSING": 1, "PACKED": 2,
                 "SHIPPED": 3, "OUT_FOR_DELIVERY": 3, "DELIVERED": 4}
        return steps.get(self.status, 0)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(Variant, on_delete=models.SET_NULL, null=True, blank=True)
    # Snapshot so the order still reads correctly if the product changes later
    product_name = models.CharField(max_length=200)
    variant_label = models.CharField(max_length=60, blank=True)
    brand_name = models.CharField(max_length=100, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.product_name} ×{self.quantity}"

    @property
    def total(self):
        return self.unit_price * self.quantity

    @property
    def product(self):
        return self.variant.product if self.variant else None


class OrderEvent(models.Model):
    """Timeline shown to the customer and the admin."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class RefillReminder(models.Model):
    """'Running low?' email a few days before a supplement/tea pack runs out."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="refill_reminders")
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE)
    email = models.EmailField()
    due_on = models.DateField(db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    cancelled = models.BooleanField(default=False)

    class Meta:
        ordering = ["due_on"]
