"""
Routine Finder — a short quiz that builds a personal routine
(AM/PM skincare + supplements + tea) from what's in stock.
"""
from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, F, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from cart.cart import Cart
from cart.models import Coupon

from .models import Concern, Product

ROUTINE_COUPON = "ROUTINE5"

SKIN_TYPES = [("normal", "Normal", "😊"), ("dry", "Dry", "🏜️"), ("oily", "Oily", "✨"),
              ("combination", "Combination", "🌗"), ("sensitive", "Sensitive", "🌸")]
BUDGETS = [("starter", "Starter · under KES 5,000", 5000), ("glow", "Glow-up · KES 5,000–12,000", 12000),
           ("luxe", "Full luxe · no limit", 10**7)]
ORIGINS = [("any", "Surprise me"), ("FR", "🇫🇷 France collection"), ("JP", "🇯🇵 Japan collection"), ("US", "🇺🇸 USA collection")]

STEPS = [
    ("cleanse", "Cleanse", "AM & PM"),
    ("tone", "Tone / Essence", "AM & PM"),
    ("treat", "Serum", "AM & PM"),
    ("moisturise", "Moisturise", "AM & PM"),
    ("protect", "Protect", "AM"),
    ("mask", "Mask", "2–3× a week"),
    ("supplement", "Supplement", "Daily"),
    ("tea", "Tea", "Daily"),
]


def _pick(step, concern_ids, skin, origin, used, budget_left):
    qs = (Product.objects.live().filter(routine_step=step, stock__gt=0).exclude(id__in=used)
          .annotate(match=Count("concerns", filter=Q(concerns__id__in=concern_ids), distinct=True)))
    if origin != "any":
        preferred = qs.filter(brand__country_code=origin)
        if preferred.exists():
            qs = preferred
    if skin and step not in ("supplement", "tea"):
        fit = qs.filter(Q(skin_type__icontains=skin) | Q(skin_type__icontains="all") | Q(skin_type=""))
        if fit.exists():
            qs = fit
    qs = qs.order_by("-match", "-is_best_seller", F("price").asc())
    cheap_enough = qs.filter(price__lte=budget_left)
    return (cheap_enough or qs).prefetch_related("variants").first()


def finder(request):
    concerns = Concern.objects.all()
    if "go" not in request.GET:
        return render(request, "catalog/routine.html", {
            "concerns": concerns, "skin_types": SKIN_TYPES, "budgets": BUDGETS, "origins": ORIGINS,
        })

    concern_ids = [int(c) for c in request.GET.getlist("concern") if c.isdigit()][:3]
    skin = request.GET.get("skin", "")
    budget_key = request.GET.get("budget", "glow")
    origin = request.GET.get("origin", "any")
    budget = dict((k, v) for k, _, v in BUDGETS).get(budget_key, 12000)

    routine, used, spent = [], [], Decimal("0")
    for step, label, when in STEPS:
        product = _pick(step, concern_ids, skin, origin, used, Decimal(budget) - spent)
        if product and spent + product.price <= budget * Decimal("1.1"):
            routine.append({"step": step, "label": label, "when": when, "product": product})
            used.append(product.id)
            spent += product.price

    request.session["routine"] = used
    discount = (spent * Decimal("0.05")).quantize(Decimal("1"))
    return render(request, "catalog/routine_result.html", {
        "routine": routine,
        "total": spent,
        "discount": discount,
        "chosen_concerns": concerns.filter(id__in=concern_ids),
        "skin": dict((k, v) for k, v, _ in SKIN_TYPES).get(skin, ""),
        "am": [r for r in routine if r["step"] in ("cleanse", "tone", "treat", "moisturise", "protect")],
        "pm": [r for r in routine if r["step"] in ("cleanse", "tone", "treat", "moisturise", "mask")],
        "inside": [r for r in routine if r["step"] in ("supplement", "tea")],
    })


@require_POST
def add_routine(request):
    ids = [int(i) for i in request.POST.getlist("product") if i.isdigit()]
    cart = Cart(request)
    added = 0
    for p in Product.objects.live().filter(id__in=ids):
        cart.add(p.default_variant(), 1)
        added += 1
    if added >= 3:
        Coupon.objects.get_or_create(code=ROUTINE_COUPON, defaults={
            "description": "5% off your personal routine", "discount_type": "percent", "value": 5})
        ok, _ = cart.apply_coupon(ROUTINE_COUPON)
        messages.success(request, f"Your {added}-step routine is in your bag" + (" with 5% off 🎉" if ok else "!"))
    elif added:
        messages.success(request, "Added to your bag.")
    return redirect("cart:page")
