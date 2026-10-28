from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from catalog.models import Product, Variant
from core.utils import int_or, is_ajax, safe_next

from . import delivery
from .cart import Cart


def cart_page(request):
    cart = Cart(request)
    summary = cart.summary()
    if summary["coupon_error"]:
        messages.warning(request, summary["coupon_error"])

    in_cart = [l["product"].id for l in summary["lines"]]
    cats = {l["product"].category_id for l in summary["lines"] if l["product"].category_id}
    suggestions = Product.objects.live().exclude(id__in=in_cart).with_ratings().prefetch_related("variants")
    if cats:
        suggestions = suggestions.filter(Q(category_id__in=cats) | Q(is_best_seller=True))
    suggestions = suggestions.order_by("-is_best_seller", "-views")[:4]

    return render(request, "cart/cart.html", {"summary": summary, "suggestions": suggestions,
                                              "zones": delivery.all_towns()})


@require_POST
def add(request):
    variant_id = request.POST.get("variant")
    if variant_id:
        variant = get_object_or_404(Variant.objects.select_related("product"), pk=variant_id, product__is_active=True)
    else:
        product = get_object_or_404(Product, pk=request.POST.get("product"), is_active=True)
        variant = product.default_variant()

    if variant.stock <= 0 or variant.product.stock <= 0:
        msg = f"Sorry, {variant.product.name} is out of stock right now."
        if is_ajax(request):
            return JsonResponse({"ok": False, "message": msg}, status=409)
        messages.error(request, msg)
        return redirect(safe_next(request, variant.product.get_absolute_url()))

    cart = Cart(request)
    cart.add(variant, int_or(request.POST.get("quantity"), 1))

    if request.POST.get("buy_now"):
        url = "/orders/checkout/"
        if is_ajax(request):
            return JsonResponse({"ok": True, "redirect": url, "cart_count": cart.count})
        return redirect(url)

    msg = f"{variant.product.name} added to your bag"
    if is_ajax(request):
        return JsonResponse({"ok": True, "message": msg, "cart_count": cart.count})
    messages.success(request, msg)
    return redirect(safe_next(request, "/cart/"))


@require_POST
def update(request, variant_id):
    cart = Cart(request)
    qty = int_or(request.POST.get("quantity"), 1, lo=0)
    ok = cart.set(variant_id, qty)
    if is_ajax(request):
        data = cart.summary_json()
        line = next((l for l in cart.lines() if l["key"] == str(variant_id)), None)
        return JsonResponse({"ok": ok, "line_total": float(line["total"]) if line else 0, **data})
    return redirect("cart:page")


@require_POST
def remove(request, variant_id):
    cart = Cart(request)
    cart.remove(variant_id)
    if is_ajax(request):
        return JsonResponse({"ok": True, **cart.summary_json()})
    messages.success(request, "Item removed.")
    return redirect("cart:page")


@require_POST
def clear(request):
    Cart(request).clear()
    if is_ajax(request):
        return JsonResponse({"ok": True})
    return redirect("cart:page")


@require_POST
def coupon_apply(request):
    cart = Cart(request)
    ok, msg = cart.apply_coupon(request.POST.get("code", ""))
    if is_ajax(request):
        return JsonResponse({"ok": ok, "message": msg, **cart.summary_json()})
    (messages.success if ok else messages.error)(request, msg)
    return redirect(safe_next(request, "/cart/"))


@require_POST
def coupon_remove(request):
    cart = Cart(request)
    cart.remove_coupon()
    if is_ajax(request):
        return JsonResponse({"ok": True, **cart.summary_json()})
    return redirect(safe_next(request, "/cart/"))


def count(request):
    return JsonResponse({"count": Cart(request).count})


def delivery_quote(request):
    """GET ?city=&method= → recalculated totals; also remembers the choice."""
    city = request.GET.get("city", "").strip()
    method = request.GET.get("method", "home")
    if city:
        delivery.set_choice(request.session, city, method)
    return JsonResponse({"ok": True, **Cart(request).summary_json(city or None, method)})


@require_POST
def toggle_points(request):
    cart = Cart(request)
    cart.use_points(request.POST.get("on") == "1")
    return JsonResponse({"ok": True, **cart.summary_json()})
