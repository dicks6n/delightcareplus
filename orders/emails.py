from django.conf import settings

from core.mail import send


def _to(order):
    return [order.email or (order.user.email if order.user else "")]


def order_placed(order):
    send(f"We've received your order {order.number} 🌿", "emails/order_placed.html", {"order": order}, _to(order))
    send(f"🛒 New order {order.number} — KES {order.total:,.0f} ({order.get_payment_method_display()})",
         "emails/admin_new_order.html", {"order": order}, settings.ADMIN_EMAILS)


def payment_received(order):
    send(f"Payment received for {order.number} ✅", "emails/payment_received.html", {"order": order}, _to(order))


def order_shipped(order):
    send(f"Your order {order.number} is on its way 🚚", "emails/order_shipped.html", {"order": order}, _to(order))


def order_delivered(order):
    send(f"Delivered! How do you like your order {order.number}? 💚", "emails/order_delivered.html", {"order": order}, _to(order))


def order_cancelled(order):
    send(f"Order {order.number} has been cancelled", "emails/order_cancelled.html", {"order": order}, _to(order))
    send(f"⚠️ Order {order.number} cancelled", "emails/admin_order_cancelled.html", {"order": order}, settings.ADMIN_EMAILS)
