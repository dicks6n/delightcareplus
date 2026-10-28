import json
import logging
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from cart import delivery
from core.models import SiteSettings
from cart.cart import Cart

from . import emails, mpesa, services
from .models import Order

logger = logging.getLogger("orders")


SESSION_ORDERS = "my_orders"


def _remember(request, order):
    numbers = request.session.get(SESSION_ORDERS, [])
    if order.number not in numbers:
        request.session[SESSION_ORDERS] = [order.number] + numbers[:19]


def _get_own_order(request, number):
    order = get_object_or_404(Order.objects.prefetch_related("items__variant__product", "events"), number=number)
    owns = (
        request.user.is_staff
        or (request.user.is_authenticated and order.user_id == request.user.id)
        or number in request.session.get(SESSION_ORDERS, [])
    )
    if not owns:
        raise Http404
    return order


def _prefill(request):
    data = request.session.get("checkout_details", {})
    if request.user.is_authenticated:
        u = request.user
        p = getattr(u, "profile", None)
        data = {
            "full_name": data.get("full_name") or u.get_full_name() or u.username,
            "email": data.get("email") or u.email,
            "phone": data.get("phone") or (p.phone if p else ""),
            "city": data.get("city") or (p.city if p else ""),
            "address": data.get("address") or (p.address if p else ""),
            "notes": data.get("notes", ""),
        }
    return data


def checkout(request):
    shop = SiteSettings.load()
    if not shop.store_open:
        messages.info(request, shop.closed_message or "Checkout is paused right now.")
        return redirect("cart:page")
    cart = Cart(request)
    summary = cart.summary()
    if not summary["lines"]:
        messages.info(request, "Your bag is empty.")
        return redirect("cart:page")

    errors = {}
    details = _prefill(request)
    if not details.get("city"):
        details["city"] = delivery.get_choice(request.session)[0]

    if request.method == "POST":
        details = {k: request.POST.get(k, "").strip() for k in
                   ("full_name", "email", "phone", "city", "address", "notes", "pickup_station")}
        method = request.POST.get("payment_method", "mpesa")
        delivery_method = request.POST.get("delivery_method", "home")
        delivery.set_choice(request.session, details["city"], delivery_method)
        summary = cart.summary(details["city"], delivery_method)

        if len(details["full_name"]) < 2:
            errors["full_name"] = "Please enter your name."
        if not mpesa.format_phone(details["phone"]):
            errors["phone"] = "Enter a valid Kenyan phone number, e.g. 0712 345 678."
        if details["email"]:
            try:
                validate_email(details["email"])
            except ValidationError:
                errors["email"] = "That email doesn't look right."
        elif not request.user.is_authenticated:
            errors["email"] = "We need an email to send your receipt."
        if not details["city"]:
            errors["city"] = "Choose your town."
        if summary["delivery_method"] == "pickup":
            if summary["zone"] and details["pickup_station"] not in summary["zone"].station_list:
                errors["pickup_station"] = "Choose the pickup station you'll collect from."
            if not details["address"]:
                details["address"] = f"Pickup: {details['pickup_station']}"
        elif len(details["address"]) < 5:
            errors["address"] = "Add your estate, street or building so the rider can find you."
        allowed = ["mpesa", "airtel"] + (["cod"] if shop.pay_on_delivery else [])
        if method not in allowed:
            errors["payment_method"] = "Choose how you'd like to pay."
        for line in summary["lines"]:
            if line["quantity"] > line["variant"].stock:
                errors["stock"] = f"Only {line['variant'].stock} × {line['product'].name} left — please lower the quantity."

        if not errors:
            request.session["checkout_details"] = details
            if request.user.is_authenticated and request.POST.get("save_details"):
                p = request.user.profile
                p.phone, p.city, p.address = details["phone"], details["city"], details["address"]
                p.save()

            order = services.create_order(request, summary, details, method)
            order.payment_phone = mpesa.format_phone(request.POST.get("mpesa_phone") or details["phone"])
            order.save(update_fields=["payment_phone"])
            _remember(request, order)
            cart.clear()
            emails.order_placed(order)

            if method == "mpesa":
                _send_stk(order)
                return redirect("orders:pay", number=order.number)
            if method == "airtel":
                return redirect("orders:pay", number=order.number)
            services.change_status(order, "PROCESSING", note="Pay on delivery — confirmed automatically")
            return redirect(f"{reverse('orders:detail', args=[order.number])}?new=1")

        messages.error(request, "Please check the highlighted fields.")

    return render(request, "orders/checkout.html", {
        "summary": summary,
        "details": details,
        "errors": errors,
        "zones": delivery.all_towns(),
        "pay_on_delivery": shop.pay_on_delivery,
        "selected_method": request.POST.get("payment_method", "mpesa"),
    })


def _send_stk(order):
    result = mpesa.stk_push(order.payment_phone or mpesa.format_phone(order.phone), order.total,
                            order.number, f"Order {order.number}")
    if result["ok"]:
        order.checkout_request_id = result["checkout_request_id"]
        order.merchant_request_id = result["merchant_request_id"]
        order.mpesa_result_desc = ""
        order.status = "PENDING"
        order.save(update_fields=["checkout_request_id", "merchant_request_id", "mpesa_result_desc", "status"])
    else:
        order.mpesa_result_desc = result["error"][:255]
        order.save(update_fields=["mpesa_result_desc"])
    return result


def pay(request, number):
    order = _get_own_order(request, number)
    if order.is_paid:
        return redirect(f"{reverse('orders:detail', args=[number])}?new=1")
    return render(request, "orders/pay.html", {
        "order": order,
        "airtel_number": SiteSettings.load().airtel_money_number or settings.AIRTEL_MONEY_NUMBER,
    })


@require_POST
def pay_retry(request, number):
    order = _get_own_order(request, number)
    if order.is_paid or order.status == "CANCELLED":
        return redirect("orders:detail", number=number)
    phone = mpesa.format_phone(request.POST.get("phone", "")) or order.payment_phone
    if not phone:
        messages.error(request, "Enter a valid Safaricom number.")
        return redirect("orders:pay", number=number)
    order.payment_phone = phone
    order.payment_method = "mpesa"
    order.checkout_request_id = None
    order.save(update_fields=["payment_phone", "payment_method", "checkout_request_id"])
    result = _send_stk(order)
    if result["ok"]:
        messages.success(request, f"We sent a new M-Pesa prompt to +{phone}.")
    else:
        messages.error(request, result["error"])
    return redirect("orders:pay", number=number)


def pay_status(request, number):
    order = _get_own_order(request, number)
    if order.is_paid:
        return JsonResponse({"status": "paid", "redirect": f"{order.get_absolute_url()}?new=1"})
    if order.status == "FAILED":
        return JsonResponse({"status": "failed", "message": order.mpesa_result_desc or "Payment was not completed."})
    if order.checkout_request_id and request.GET.get("query") == "1":
        res = mpesa.stk_query(order.checkout_request_id)
        if res["status"] == "paid":
            services.mark_paid(order, note="M-Pesa payment confirmed")
            return JsonResponse({"status": "paid", "redirect": f"{order.get_absolute_url()}?new=1"})
        if res["status"] == "failed":
            order.status = "FAILED"
            order.mpesa_result_desc = res["desc"][:255]
            order.save(update_fields=["status", "mpesa_result_desc"])
            return JsonResponse({"status": "failed", "message": res["desc"]})
    return JsonResponse({"status": "pending", "message": order.mpesa_result_desc or "Waiting for you to enter your M-Pesa PIN…"})


@require_POST
def airtel_submit(request, number):
    order = _get_own_order(request, number)
    ref = request.POST.get("reference", "").strip().upper()[:40]
    proof = request.FILES.get("proof")
    if len(ref) < 6:
        messages.error(request, "Enter the transaction ID from your Airtel Money SMS.")
        return redirect("orders:pay", number=number)
    if proof and (proof.size > 5 * 1024 * 1024 or not (proof.content_type or "").startswith("image/")):
        messages.error(request, "The screenshot must be an image under 5 MB.")
        return redirect("orders:pay", number=number)
    order.payment_method = "airtel"
    order.payment_reference = ref
    if proof:
        order.payment_proof = proof
    order.save()
    services.log_event(order, order.status, f"Airtel Money reference {ref} submitted")
    messages.success(request, "Thanks! We'll confirm your payment shortly — usually within an hour.")
    return redirect(f"{reverse('orders:detail', args=[number])}?new=1")


def detail(request, number):
    order = _get_own_order(request, number)
    return render(request, "orders/detail.html", {"order": order, "is_new": request.GET.get("new") == "1"})


@require_POST
def cancel(request, number):
    order = _get_own_order(request, number)
    if not order.can_cancel:
        messages.error(request, "This order is already on its way, so it can't be cancelled online. Chat with us and we'll help.")
        return redirect("orders:detail", number=number)
    reason = request.POST.get("reason", "").strip()[:200] or "Cancelled by customer"
    services.change_status(order, "CANCELLED", user=request.user, note=reason)
    messages.success(request, f"Order {order.number} has been cancelled.")
    return redirect("orders:detail", number=number)


@require_POST
def reorder(request, number):
    order = _get_own_order(request, number)
    cart = Cart(request)
    added = 0
    for item in order.items.select_related("variant__product"):
        if item.variant and item.variant.product.is_active and item.variant.stock > 0:
            cart.add(item.variant, item.quantity)
            added += 1
    if added:
        messages.success(request, f"{added} item{'s' if added != 1 else ''} added to your bag.")
    else:
        messages.error(request, "Sorry, those items aren't available any more.")
    return redirect("cart:page")


def track(request):
    """Guests can look up an order with its number + phone."""
    if request.method == "POST":
        number = request.POST.get("number", "").strip().upper()
        phone = mpesa.format_phone(request.POST.get("phone", ""))
        order = Order.objects.filter(number=number).first()
        if order and phone and phone in (mpesa.format_phone(order.phone), order.payment_phone):
            _remember(request, order)
            return redirect("orders:detail", number=order.number)
        messages.error(request, "We couldn't find an order with that number and phone.")
    return render(request, "orders/track.html")


@csrf_exempt
@require_POST
def mpesa_callback(request):
    token = settings.MPESA_CALLBACK_TOKEN
    if token and not constant_time_compare(request.GET.get("t", ""), token):
        logger.warning("M-Pesa callback with a wrong token from %s", request.META.get("REMOTE_ADDR"))
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Rejected"}, status=403)
    try:
        body = json.loads(request.body)
        cb = body.get("Body", {}).get("stkCallback", {})
    except (ValueError, AttributeError):
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Bad payload"})

    order = Order.objects.filter(checkout_request_id=cb.get("CheckoutRequestID")).first()
    if not order:
        logger.warning("M-Pesa callback for unknown request %s", cb.get("CheckoutRequestID"))
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})
    if order.is_paid:
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Already processed"})

    if str(cb.get("ResultCode")) == "0":
        meta = {i.get("Name"): i.get("Value") for i in cb.get("CallbackMetadata", {}).get("Item", [])}
        amount = Decimal(str(meta.get("Amount", 0)))
        receipt = str(meta.get("MpesaReceiptNumber", ""))
        if amount < int(order.total):
            order.mpesa_result_desc = f"Underpaid: received KES {amount} of {order.total}"
            order.payment_reference = receipt
            order.save(update_fields=["mpesa_result_desc", "payment_reference"])
            services.log_event(order, order.status, order.mpesa_result_desc)
        else:
            services.mark_paid(order, reference=receipt, note=f"M-Pesa receipt {receipt}")
    else:
        order.status = "FAILED"
        order.mpesa_result_desc = str(cb.get("ResultDesc", "Payment failed"))[:255]
        order.save(update_fields=["status", "mpesa_result_desc"])
        services.log_event(order, "FAILED", order.mpesa_result_desc)
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})
