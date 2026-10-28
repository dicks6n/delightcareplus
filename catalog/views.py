from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts import wishlist
from cart.cart import Cart
from core.utils import is_ajax, safe_next
from orders.models import Order, OrderItem

from .models import Batch, Brand, Category, Concern, Department, Product, Review, StockAlert

PER_PAGE = 16
RECENT_LIMIT = 8

SORTS = {
    "featured": ("Featured", ["-is_featured", "-is_best_seller", "-created_at"]),
    "newest": ("Newest", ["-created_at"]),
    "price_asc": ("Price: Low → High", ["price"]),
    "price_desc": ("Price: High → Low", ["-price"]),
    "rating": ("Top Rated", [F("avg_rating").desc(nulls_last=True), "-review_count"]),
    "popular": ("Most Popular", ["-views"]),
    "name": ("Name A–Z", ["name"]),
}


def _filtered(request, qs):
    """Apply URL filters. Returns (queryset, context dict for the filter bar)."""
    g = request.GET
    q = g.get("q", "").strip()
    brand_slugs = [b for b in g.getlist("brand") if b]
    forms = [f for f in g.getlist("form") if f]
    on_sale = g.get("on_sale") == "1"
    in_stock = g.get("in_stock") == "1"
    min_price, max_price = g.get("min_price", "").strip(), g.get("max_price", "").strip()
    sort = g.get("sort", "featured")

    if q:
        for word in q.split()[:6]:
            qs = qs.filter(
                Q(name__icontains=word) | Q(short_description__icontains=word) | Q(description__icontains=word)
                | Q(brand__name__icontains=word) | Q(category__name__icontains=word) | Q(ingredients__icontains=word)
            )
    if brand_slugs:
        qs = qs.filter(brand__slug__in=brand_slugs)
    if g.get("department"):
        qs = qs.filter(category__department__slug=g["department"])
    if forms:
        qs = qs.filter(form__in=forms)
    concern_slugs = [c for c in g.getlist("concern") if c]
    if concern_slugs:
        qs = qs.filter(concerns__slug__in=concern_slugs).distinct()
    for flag in ("vegan", "halal", "cruelty_free", "fragrance_free"):
        if g.get(flag) == "1":
            qs = qs.filter(**{f"is_{flag}": True})
    if on_sale:
        qs = qs.filter(compare_price__gt=F("price"))
    if in_stock:
        qs = qs.filter(stock__gt=0)
    try:
        if min_price:
            qs = qs.filter(price__gte=Decimal(min_price))
        if max_price:
            qs = qs.filter(price__lte=Decimal(max_price))
    except InvalidOperation:
        pass

    qs = qs.with_ratings()
    if sort not in SORTS:
        sort = "featured"
    qs = qs.order_by(*SORTS[sort][1], "-id")

    params = g.copy()
    params.pop("page", None)
    return qs, {
        "q": q,
        "selected_brands": brand_slugs,
        "selected_forms": forms,
        "on_sale": on_sale,
        "in_stock": in_stock,
        "min_price": min_price,
        "max_price": max_price,
        "sort": sort,
        "sort_options": [(k, v[0]) for k, v in SORTS.items()],
        "form_options": Product.FORM_CHOICES,
        "querystring": params.urlencode(),
        "selected_concerns": concern_slugs,
        "flags": {f: g.get(f) == "1" for f in ("vegan", "halal", "cruelty_free", "fragrance_free")},
        "filter_count": len(concern_slugs) + sum(g.get(f) == "1" for f in ("vegan", "halal", "cruelty_free", "fragrance_free")) + len(brand_slugs) + len(forms) + on_sale + in_stock + bool(min_price) + bool(max_price),
    }


def _listing(request, base_qs, context):
    qs, filters = _filtered(request, base_qs)
    page = Paginator(qs.select_related("brand", "category").prefetch_related("variants", "images"), PER_PAGE).get_page(request.GET.get("page"))
    return render(request, "catalog/list.html", {
        **context,
        **filters,
        "page_obj": page,
        "products": page.object_list,
        "total": page.paginator.count,
        # Counts reflect the page being browsed (e.g. only Supplements), so empty brands are hidden
        "all_brands": Brand.objects.annotate(n=Count("products", filter=Q(products__in=base_qs), distinct=True)).filter(n__gt=0),
        "all_concerns": Concern.objects.all(),
    })


def shop(request):
    q = request.GET.get("q", "").strip()
    return _listing(request, Product.objects.live(), {
        "title": f"Results for “{q}”" if q else "Shop All",
        "subtitle": "Premium supplements, skincare & teas — France, Japan & USA collections",
        "breadcrumbs": [("Shop", None)],
    })


def department(request, slug):
    dept = get_object_or_404(Department, slug=slug, is_active=True)
    return _listing(request, Product.objects.live().filter(category__department=dept), {
        "title": dept.name,
        "subtitle": dept.description,
        "department": dept,
        "subcategories": dept.categories.filter(is_active=True),
        "breadcrumbs": [("Shop", reverse("catalog:shop")), (dept.name, None)],
    })


def category(request, slug):
    cat = get_object_or_404(Category.objects.select_related("department"), slug=slug, is_active=True)
    return _listing(request, Product.objects.live().filter(category=cat), {
        "title": cat.name,
        "subtitle": cat.description,
        "department": cat.department,
        "current_category": cat,
        "subcategories": cat.department.categories.filter(is_active=True),
        "breadcrumbs": [("Shop", reverse("catalog:shop")),
                        (cat.department.name, cat.department.get_absolute_url()), (cat.name, None)],
    })


def brand(request, slug):
    b = get_object_or_404(Brand, slug=slug)
    return _listing(request, Product.objects.live().filter(brand=b), {
        "title": b.name,
        "subtitle": b.tagline,
        "brand": b,
        "breadcrumbs": [("Brands", reverse("catalog:brands")), (b.name, None)],
    })


def brands(request):
    return render(request, "catalog/brands.html", {
        "brands": Brand.objects.annotate(n=Count("products", filter=Q(products__is_active=True))),
    })


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("brand", "category__department").prefetch_related("variants", "images"),
        slug=slug,
    )
    if not product.is_active and not request.user.is_staff:
        messages.info(request, "That product is no longer available — here are some alternatives.")
        return redirect(product.category.get_absolute_url() if product.category else "catalog:shop")

    Product.objects.filter(pk=product.pk).update(views=F("views") + 1)
    recent = [i for i in request.session.get("recently_viewed", []) if i != product.id]
    request.session["recently_viewed"] = [product.id] + recent[: RECENT_LIMIT - 1]

    reviews = product.reviews.filter(is_approved=True).select_related("user")
    rating = product.rating_summary()
    counts = dict(reviews.values_list("rating").annotate(c=Count("id")))
    breakdown = [{"stars": s, "count": counts.get(s, 0),
                  "percent": round(counts.get(s, 0) * 100 / rating["count"]) if rating["count"] else 0}
                 for s in range(5, 0, -1)]

    user_review = reviews.filter(user=request.user).first() if request.user.is_authenticated else None
    has_bought = request.user.is_authenticated and OrderItem.objects.filter(
        order__user=request.user, order__status__in=Order.PAID_STATUSES, variant__product=product).exists()

    related = Product.objects.live().with_ratings().exclude(pk=product.pk).prefetch_related("variants", "images")
    related = (related.filter(category=product.category) if product.category else related)[:4]
    same_brand = Product.objects.live().with_ratings().filter(brand=product.brand).exclude(pk=product.pk).prefetch_related("variants", "images")[:4] if product.brand else []

    crumbs = [("Shop", reverse("catalog:shop"))]
    if product.category:
        crumbs += [(product.category.department.name, product.category.department.get_absolute_url()),
                   (product.category.name, product.category.get_absolute_url())]
    crumbs.append((product.name, None))

    return render(request, "catalog/product.html", {
        "breadcrumbs": crumbs,
        "product": product,
        "variants": product.variants.all(),
        "gallery": product.gallery(),
        "reviews": reviews[:30],
        "rating": rating,
        "breakdown": breakdown,
        "user_review": user_review,
        "has_bought": has_bought,
        "related": related,
        "same_brand": same_brand,
        "together": bought_together(product),
        "batch": product.latest_batch(),
        "in_compare": product.id in request.session.get(COMPARE_KEY, []),
        "concerns": product.concerns.all(),
    })


def quick_view(request, pk):
    p = get_object_or_404(Product.objects.select_related("brand", "category"), pk=pk, is_active=True)
    variants = list(p.variants.all()) or [p.default_variant()]
    return JsonResponse({
        "id": p.id,
        "name": p.name,
        "brand": p.brand.name if p.brand else "",
        "flag": p.brand.flag if p.brand else "",
        "category": p.category.name if p.category else "",
        "description": p.short_description or p.description[:300],
        "price": float(p.price),
        "compare_price": float(p.compare_price) if p.compare_price and p.compare_price > p.price else None,
        "discount": p.discount_percent,
        "image": p.image.url if p.image else "",
        "rating": p.rating_summary(),
        "stock": p.stock,
        "low_stock": p.low_stock,
        "in_wishlist": p.id in wishlist.get_ids(request),
        "url": p.get_absolute_url(),
        "variants": [{"id": v.id, "label": v.label, "price": float(v.price), "stock": v.stock} for v in variants],
    })


def search_suggest(request):
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})
    qs = Product.objects.live().select_related("brand").filter(
        Q(name__icontains=q) | Q(brand__name__icontains=q) | Q(category__name__icontains=q)
    )[:7]
    return JsonResponse({
        "results": [{
            "name": p.name,
            "brand": p.brand.name if p.brand else "",
            "price": float(p.price),
            "image": p.image.url if p.image else "",
            "url": p.get_absolute_url(),
        } for p in qs],
        "all_url": f"{reverse('catalog:shop')}?q={quote(q)}",
    })


@login_required
@require_POST
def submit_review(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    try:
        rating = int(request.POST.get("rating", 0))
    except ValueError:
        rating = 0
    if not 1 <= rating <= 5:
        messages.error(request, "Please pick a star rating.")
        return redirect(f"{product.get_absolute_url()}#reviews")

    bought = OrderItem.objects.filter(order__user=request.user, order__status__in=Order.PAID_STATUSES,
                                      variant__product=product).exists()
    Review.objects.update_or_create(product=product, user=request.user, defaults={
        "rating": rating,
        "title": request.POST.get("title", "").strip()[:120],
        "comment": request.POST.get("comment", "").strip()[:2000],
        "is_verified_buyer": bought,
    })
    messages.success(request, "Thanks for your review! ⭐")
    return redirect(f"{product.get_absolute_url()}#reviews")


# ------------------------------------------------------------------ wishlist
def wishlist_page(request):
    ids = wishlist.get_ids(request)
    products = sorted(
        Product.objects.live().filter(id__in=ids).with_ratings().select_related("brand").prefetch_related("variants", "images"),
        key=lambda p: ids.index(p.id),
    )
    return render(request, "catalog/wishlist.html", {"products": products})


@require_POST
def wishlist_toggle(request, pk):
    product = get_object_or_404(Product, pk=pk)
    added = wishlist.toggle(request, product.id)
    count = len(wishlist.get_ids(request))
    msg = f"Saved {product.name} ❤️" if added else f"Removed {product.name}"
    if is_ajax(request):
        return JsonResponse({"ok": True, "added": added, "count": count, "message": msg})
    messages.success(request, msg)
    return redirect(safe_next(request, reverse("catalog:wishlist")))


@require_POST
def wishlist_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    cart = Cart(request)
    cart.add(product.default_variant(), 1)
    wishlist.remove(request, product.id)
    if is_ajax(request):
        return JsonResponse({"ok": True, "cart_count": cart.count, "count": len(wishlist.get_ids(request)),
                             "message": f"{product.name} moved to your bag"})
    return redirect("catalog:wishlist")


# ------------------------------------------------------------ shop by concern
def concern(request, slug):
    c = get_object_or_404(Concern, slug=slug)
    return _listing(request, Product.objects.live().filter(concerns=c), {
        "title": f"{c.emoji} {c.name}".strip(),
        "subtitle": f"Products chosen for {c.name.lower()}",
        "current_concern": c,
        "breadcrumbs": [("Shop", reverse("catalog:shop")), ("Concerns", None), (c.name, None)],
    })


# ---------------------------------------------------------------- compare
COMPARE_KEY = "compare"
COMPARE_MAX = 4


@require_POST
def compare_toggle(request, pk):
    ids = [int(i) for i in request.session.get(COMPARE_KEY, [])]
    if pk in ids:
        ids.remove(pk)
        added = False
    else:
        if len(ids) >= COMPARE_MAX:
            ids.pop(0)
        ids.append(pk)
        added = True
    request.session[COMPARE_KEY] = ids
    return JsonResponse({"ok": True, "added": added, "count": len(ids), "ids": ids})


def compare(request):
    ids = [int(i) for i in request.session.get(COMPARE_KEY, [])]
    products = sorted(Product.objects.live().filter(id__in=ids).with_ratings().select_related("brand", "category")
                      .prefetch_related("concerns", "variants"), key=lambda p: ids.index(p.id))
    return render(request, "catalog/compare.html", {"products": products})


# ------------------------------------------------------- authenticity check
def verify(request):
    code = request.GET.get("code", "").strip().upper()
    batch = None
    if code:
        batch = Batch.objects.select_related("product__brand").filter(code=code).first()
    return render(request, "catalog/verify.html", {"code": code, "batch": batch, "searched": bool(code)})


# ------------------------------------------------------- back in stock alert
@require_POST
def stock_alert(request, pk):
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email

    product = get_object_or_404(Product, pk=pk)
    email = request.POST.get("email", "").strip().lower() or (request.user.email if request.user.is_authenticated else "")
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"ok": False, "message": "Please enter a valid email."})
    StockAlert.objects.get_or_create(product=product, email=email, defaults={})
    StockAlert.objects.filter(product=product, email=email).update(notified_at=None)
    return JsonResponse({"ok": True, "message": "Done! We'll email you the moment it's back. 💌"})


def bought_together(product, limit=3):
    """Products most often in the same orders as this one."""
    order_ids = OrderItem.objects.filter(variant__product=product).values_list("order_id", flat=True)[:500]
    ids = (OrderItem.objects.filter(order_id__in=list(order_ids)).exclude(variant__product=product)
           .values("variant__product").annotate(n=Count("id")).order_by("-n").values_list("variant__product", flat=True)[:limit])
    found = list(Product.objects.live().filter(id__in=list(ids)).prefetch_related("variants", "images"))
    if len(found) < limit and product.category:
        # Fill with complementary products from the same department
        extra = (Product.objects.live().filter(category__department=product.category.department)
                 .exclude(id__in=[p.id for p in found] + [product.id]).exclude(category=product.category)
                 .order_by("-is_best_seller", "-views").prefetch_related("variants", "images")[: limit - len(found)])
        found += list(extra)
    return found
