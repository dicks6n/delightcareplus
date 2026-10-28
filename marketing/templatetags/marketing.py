"""Tags that describe a page's ad-tracking event for static/js/tracking.js."""
import json

from django import template
from django.utils.html import format_html

register = template.Library()


def _tag(data):
    return format_html('<div hidden data-track="{}"></div>', json.dumps(data))


def _item(product, price=None, quantity=1):
    return {"id": str(product.id), "name": product.name, "price": float(price if price is not None else product.price),
            "quantity": quantity}


@register.simple_tag
def track_view(product):
    return _tag({"event": "ViewContent", "items": [_item(product)]})


@register.simple_tag
def track_checkout(summary):
    items = [_item(l["product"], l["unit_price"], l["quantity"]) for l in summary["lines"]]
    return _tag({"event": "InitiateCheckout", "items": items, "value": float(summary["total"])})


@register.simple_tag
def track_purchase(order):
    items = [{"id": str(i.variant.product_id) if i.variant else i.product_name, "name": i.product_name,
              "price": float(i.unit_price), "quantity": i.quantity} for i in order.items.all()]
    return _tag({"event": "Purchase", "order": order.number, "items": items, "value": float(order.total)})


@register.simple_tag(takes_context=True)
def track_pending(context):
    """Events saved in the session by a view that redirected (e.g. sign-up → CompleteRegistration)."""
    request = context.get("request")
    if not request or not hasattr(request, "session"):
        return ""
    events = request.session.pop("track_events", [])
    return format_html("".join(str(_tag(e)) for e in events)) if events else ""
