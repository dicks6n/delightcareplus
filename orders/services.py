"""
Order business logic, kept out of views so the shop and the dashboard share it.
"""
import logging

from django.db import transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.utils import timezone

from datetime import timedelta

from accounts.models import PointsTransaction
from cart.models import Coupon
from catalog.models import Product, Variant

from . import emails
from .models import Order, OrderEvent, OrderItem, RefillReminder

logger = logging.getLogger("orders")


def log_event(order, status, note="", user=None):
    OrderEvent.objects.create(order=order, status=status, note=note[:255],
                              created_by=user if (user and user.is_authenticated) else None)


@transaction.atomic
def _attribution(request):
    """Which ad, post or link brought this customer (see marketing/attribution.py)."""
    from marketing.attribution import get
    a = get(request)
    return {"source": a.get("source", "")[:60], "medium": a.get("medium", "")[:60], "campaign": a.get("campaign", "")[:100]}


def create_order(request, summary, details, payment_method):
    order = Order.objects.create(
        user=request.user if request.user.is_authenticated else None,
        full_name=details["full_name"],
        email=details.get("email", ""),
        phone=details["phone"],
        city=details["city"],
        address=details["address"],
        notes=details.get("notes", ""),
        subtotal=summary["subtotal"],
        discount=summary["discount"],
        points_redeemed=summary["points_used"],
        coupon_code=summary["coupon"].code if summary["coupon"] else "",
        delivery_fee=summary["delivery"],
        delivery_method=summary["delivery_method"],
        delivery_zone=summary["zone"].name if summary["zone"] else "",
        pickup_station=details.get("pickup_station", "") if summary["delivery_method"] == "pickup" else "",
        parcel_weight_kg=summary["weight_kg"],
        total=summary["total"],
        payment_method=payment_method,
        **_attribution(request),
    )
    OrderItem.objects.bulk_create([
        OrderItem(
            order=order,
            variant=l["variant"],
            product_name=l["product"].name,
            variant_label=l["variant"].label,
            brand_name=l["product"].brand.name if l["product"].brand else "",
            unit_price=l["unit_price"],
            quantity=l["quantity"],
        )
        for l in summary["lines"]
    ])
    if order.coupon_code:
        Coupon.objects.filter(code__iexact=order.coupon_code).update(used_count=F("used_count") + 1)
    if order.points_redeemed and order.user:
        PointsTransaction.objects.create(user=order.user, points=-order.points_redeemed,
                                         reason=f"Used on order {order.number}", order=order)
    log_event(order, "PENDING", "Order placed")
    return order


def award_points(order):
    """Glow Points are credited once the order is delivered (so cancelled orders don't earn)."""
    if not order.user or order.points_earned:
        return
    goods = order.subtotal - order.discount - order.points_redeemed
    pts = int(goods // 100)
    if pts > 0:
        PointsTransaction.objects.create(user=order.user, points=pts, reason=f"Earned on order {order.number}", order=order)
        Order.objects.filter(pk=order.pk).update(points_earned=pts)
        order.points_earned = pts


def refund_points(order):
    if order.user and order.points_redeemed:
        if not PointsTransaction.objects.filter(order=order, reason__startswith="Refunded").exists():
            PointsTransaction.objects.create(user=order.user, points=order.points_redeemed,
                                             reason=f"Refunded — order {order.number} cancelled", order=order)


def schedule_refills(order):
    """Email a reminder ~5 days before supplements/teas from this order run out."""
    email = order.email or (order.user.email if order.user else "")
    if not email:
        return
    start = timezone.localdate()
    for item in order.items.select_related("variant__product"):
        product = item.product
        if not product or not product.days_supply:
            continue
        days = product.days_supply * item.quantity
        if days < 10:
            continue
        RefillReminder.objects.get_or_create(order=order, product=product, defaults={
            "email": email, "due_on": start + timedelta(days=days - 5)})


def deduct_stock(order):
    if order.stock_deducted:
        return
    with transaction.atomic():
        for item in order.items.select_related("variant"):
            if not item.variant_id:
                continue
            Variant.objects.filter(id=item.variant_id).update(stock=Greatest(F("stock") - item.quantity, Value(0)))
            Product.objects.filter(id=item.variant.product_id).update(stock=Greatest(F("stock") - item.quantity, Value(0)))
        Order.objects.filter(id=order.id).update(stock_deducted=True)
        order.stock_deducted = True


def restore_stock(order):
    if not order.stock_deducted:
        return
    with transaction.atomic():
        for item in order.items.select_related("variant"):
            if not item.variant_id:
                continue
            Variant.objects.filter(id=item.variant_id).update(stock=F("stock") + item.quantity)
            Product.objects.filter(id=item.variant.product_id).update(stock=F("stock") + item.quantity)
        Order.objects.filter(id=order.id).update(stock_deducted=False)
        order.stock_deducted = False


def mark_paid(order, reference="", user=None, note="Payment received"):
    """Idempotent. Returns True only the first time."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.is_paid:
            return False
        order.status = "PAID"
        order.paid_at = timezone.now()
        if reference:
            order.payment_reference = reference
        order.save()
        deduct_stock(order)
        log_event(order, "PAID", note, user)
    schedule_refills(order)
    emails.payment_received(order)
    return True


TRANSITIONS = {
    "PENDING": ["PAID", "CANCELLED"],
    "FAILED": ["PAID", "CANCELLED"],
    "PAID": ["PROCESSING", "CANCELLED"],
    "PROCESSING": ["PACKED", "CANCELLED"],
    "PACKED": ["SHIPPED", "CANCELLED"],
    "SHIPPED": ["OUT_FOR_DELIVERY", "DELIVERED"],
    "OUT_FOR_DELIVERY": ["DELIVERED"],
    "DELIVERED": ["REFUNDED"],
    "CANCELLED": ["REFUNDED"],
}


def next_statuses(order):
    allowed = list(TRANSITIONS.get(order.status, []))
    if order.status in ("PENDING", "CANCELLED") and not order.paid_at and "REFUNDED" in allowed:
        allowed.remove("REFUNDED")
    if order.payment_method == "cod" and order.status == "PENDING":
        allowed = ["PROCESSING", "CANCELLED"]   # cash orders are confirmed, then paid on delivery
    return allowed


def change_status(order, new_status, user=None, note="", courier="", tracking="", eta=None):
    if new_status not in next_statuses(order):
        raise ValueError(f"Can't move from {order.get_status_display()} to {dict(Order.STATUS_CHOICES)[new_status]}.")

    if new_status == "PAID":
        mark_paid(order, user=user, note=note or "Payment confirmed by admin")
        return

    now = timezone.now()
    order.status = new_status
    if new_status == "SHIPPED":
        order.shipped_at = now
        order.courier = courier or order.courier
        order.tracking_number = tracking or order.tracking_number
        order.estimated_delivery = eta or order.estimated_delivery
    elif new_status == "DELIVERED":
        order.delivered_at = now
        if order.payment_method == "cod" and not order.paid_at:
            order.paid_at = now
    elif new_status == "CANCELLED":
        order.cancelled_at = now
        order.cancellation_reason = note[:255] or order.cancellation_reason
    order.save()

    if new_status == "PROCESSING" and order.payment_method == "cod":
        deduct_stock(order)
        schedule_refills(order)
    if new_status == "DELIVERED":
        award_points(order)
        from marketing.referrals import reward
        reward(order)
    if new_status in ("CANCELLED", "REFUNDED"):
        restore_stock(order)
        refund_points(order)
        order.refill_reminders.update(cancelled=True)

    log_event(order, new_status, note, user)

    if new_status == "SHIPPED":
        emails.order_shipped(order)
    elif new_status == "DELIVERED":
        emails.order_delivered(order)
    elif new_status == "CANCELLED":
        emails.order_cancelled(order)
