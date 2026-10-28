"""
Delight Care Plus — Seller Center.

Everything the shop owner manages: orders, products, stock, customers, reviews,
coupons, delivery prices, catalog setup, content, chats, reports and settings.
All views are staff-only.
"""
import csv
import io
import json
import zipfile
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db.models import Count, F, Max, Q, Sum
from django.db.models.functions import TruncDate
from django.forms import DateInput, ModelForm, modelform_factory
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from blog.models import Post
from cart.models import Coupon, DeliveryZone
from catalog.models import Batch, Brand, Category, Concern, Department, Product, ProductImage, Review, StockAlert
from chat.models import Message
from core.models import Banner, ContactMessage, NewsletterSubscriber, SiteSettings, Testimonial
from orders import services
from orders.models import Order, OrderItem

from . import forms

REVENUE = Order.PAID_STATUSES


def staff(view):
    return staff_member_required(view, login_url="accounts:login")


def _page(request, qs, per=30):
    return Paginator(qs, per).get_page(request.GET.get("page"))


def _qs_without_page(request):
    params = request.GET.copy()
    params.pop("page", None)
    return params.urlencode()


def _csv_response(filename, header, rows):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    w = csv.writer(response)
    w.writerow(header)
    w.writerows(rows)
    return response


# =====================================================================
# OVERVIEW
# =====================================================================
@staff
def overview(request):
    now = timezone.now()
    today = timezone.localdate()
    shop = SiteSettings.load()

    def stats(since):
        qs = Order.objects.filter(created_at__gte=since, status__in=REVENUE)
        agg = qs.aggregate(rev=Sum("total"), n=Count("id"))
        rev, n = agg["rev"] or Decimal("0"), agg["n"] or 0
        return {"revenue": rev, "orders": n, "aov": (rev / n) if n else 0}

    start_today = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
    s_today, s_7, s_30 = stats(start_today), stats(now - timedelta(days=7)), stats(now - timedelta(days=30))
    s_prev30 = stats(now - timedelta(days=60))
    prev_rev = s_prev30["revenue"] - s_30["revenue"]
    growth = round((s_30["revenue"] - prev_rev) * 100 / prev_rev) if prev_rev else None

    # 30-day chart
    daily = dict(Order.objects.filter(created_at__gte=now - timedelta(days=30), status__in=REVENUE)
                 .annotate(d=TruncDate("created_at")).values_list("d").annotate(t=Sum("total")).values_list("d", "t"))
    labels, values = [], []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        labels.append(d.strftime("%b %d"))
        values.append(float(daily.get(d, 0) or 0))

    to_do = {
        "confirm_payment": Order.objects.filter(status="PENDING", payment_method="airtel").exclude(payment_reference="").count(),
        "awaiting_payment": Order.objects.filter(status__in=["PENDING", "FAILED"]).count(),
        "to_pack": Order.objects.filter(status__in=["PAID", "PROCESSING"]).count(),
        "to_ship": Order.objects.filter(status="PACKED").count(),
        "in_transit": Order.objects.filter(status__in=["SHIPPED", "OUT_FOR_DELIVERY"]).count(),
        "unread_chats": Message.objects.filter(is_staff=False, is_read=False).values("conversation").distinct().count(),
        "contact_messages": ContactMessage.objects.filter(is_handled=False).count(),
        "pending_reviews": Review.objects.filter(is_approved=False).count(),
    }

    top = (OrderItem.objects.filter(order__status__in=REVENUE, order__created_at__gte=now - timedelta(days=30))
           .values("product_name", "brand_name").annotate(qty=Sum("quantity"), revenue=Sum(F("unit_price") * F("quantity")))
           .order_by("-revenue")[:6])
    by_brand = (OrderItem.objects.filter(order__status__in=REVENUE, order__created_at__gte=now - timedelta(days=30))
                .values("brand_name").annotate(revenue=Sum(F("unit_price") * F("quantity"))).order_by("-revenue")[:5])
    by_payment = (Order.objects.filter(status__in=REVENUE, created_at__gte=now - timedelta(days=30))
                  .values("payment_method").annotate(n=Count("id"), t=Sum("total")).order_by("-t"))
    pay_labels = dict(Order.PAYMENT_CHOICES)

    return render(request, "dashboard/overview.html", {
        "s_today": s_today, "s_7": s_7, "s_30": s_30, "growth": growth,
        "chart_labels": json.dumps(labels), "chart_values": json.dumps(values),
        "to_do": to_do,
        "recent_orders": Order.objects.all()[:8],
        "low_stock": Product.objects.live().filter(stock__lte=shop.low_stock_alert).order_by("stock")[:8],
        "expiring": Batch.objects.filter(expiry_date__lte=today + timedelta(days=90), quantity__gt=0)
                    .select_related("product").order_by("expiry_date")[:6],
        "top_products": top,
        "by_brand": by_brand,
        "by_payment": [{"label": pay_labels.get(r["payment_method"], r["payment_method"]), **r} for r in by_payment],
        "customers_total": User.objects.filter(is_staff=False).count(),
        "customers_new": User.objects.filter(is_staff=False, date_joined__gte=now - timedelta(days=30)).count(),
        "sample_count": Product.objects.filter(is_sample=True).count(),
        "stock_alert_count": StockAlert.objects.filter(notified_at__isnull=True).count(),
    })


@staff
def notifications(request):
    unread = Message.objects.filter(is_staff=False, is_read=False).values("conversation").distinct().count()
    new_orders = Order.objects.filter(status__in=["PAID", "PROCESSING"]).count()
    to_confirm = Order.objects.filter(status="PENDING", payment_method="airtel").exclude(payment_reference="").count()
    return JsonResponse({"chats": unread, "orders": new_orders, "confirm": to_confirm,
                         "total": unread + new_orders + to_confirm})


# =====================================================================
# ORDERS
# =====================================================================
ORDER_TABS = [
    ("all", "All", None),
    ("pending", "Awaiting payment", ["PENDING", "FAILED"]),
    ("to_pack", "To pack", ["PAID", "PROCESSING"]),
    ("to_ship", "Ready to ship", ["PACKED"]),
    ("transit", "In transit", ["SHIPPED", "OUT_FOR_DELIVERY"]),
    ("delivered", "Delivered", ["DELIVERED"]),
    ("closed", "Cancelled / refunded", ["CANCELLED", "REFUNDED"]),
]


def _orders_filtered(request):
    qs = Order.objects.select_related("user").prefetch_related("items")
    tab = request.GET.get("tab", "all")
    statuses = dict((k, s) for k, _, s in ORDER_TABS).get(tab)
    if statuses:
        qs = qs.filter(status__in=statuses)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(full_name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q)
                       | Q(payment_reference__icontains=q) | Q(items__product_name__icontains=q)).distinct()
    if request.GET.get("payment"):
        qs = qs.filter(payment_method=request.GET["payment"])
    d_from, d_to = parse_date(request.GET.get("from", "") or ""), parse_date(request.GET.get("to", "") or "")
    if d_from:
        qs = qs.filter(created_at__date__gte=d_from)
    if d_to:
        qs = qs.filter(created_at__date__lte=d_to)
    return qs, tab


@staff
def order_list(request):
    qs, tab = _orders_filtered(request)
    if request.GET.get("export") == "csv":
        return _csv_response("orders.csv",
                             ["Order", "Date", "Customer", "Phone", "Email", "City", "Items", "Subtotal", "Discount",
                              "Delivery", "Total", "Payment", "Reference", "Status"],
                             [[o.number, timezone.localtime(o.created_at).strftime("%Y-%m-%d %H:%M"), o.full_name, o.phone,
                               o.email, o.city, "; ".join(f"{i.product_name} x{i.quantity}" for i in o.items.all()),
                               o.subtotal, o.discount, o.delivery_fee, o.total, o.get_payment_method_display(),
                               o.payment_reference, o.get_status_display()] for o in qs])
    counts = {k: (Order.objects.filter(status__in=s).count() if s else Order.objects.count()) for k, _, s in ORDER_TABS}
    return render(request, "dashboard/orders.html", {
        "page_obj": _page(request, qs), "tab": tab,
        "tabs": [(k, label, counts[k]) for k, label, _ in ORDER_TABS],
        "querystring": _qs_without_page(request),
        "payment_choices": Order.PAYMENT_CHOICES,
    })


@staff
@require_POST
def order_bulk(request):
    numbers = request.POST.getlist("orders")
    new_status = request.POST.get("status")
    done, skipped = 0, 0
    for order in Order.objects.filter(number__in=numbers):
        try:
            services.change_status(order, new_status, user=request.user, note="Bulk update")
            done += 1
        except ValueError:
            skipped += 1
    messages.success(request, f"Updated {done} order(s)." + (f" Skipped {skipped} that can't move to that status." if skipped else ""))
    return redirect(request.POST.get("next") or "dashboard:orders")


@staff
def order_detail(request, number):
    order = get_object_or_404(Order.objects.select_related("user").prefetch_related("items__variant__product", "events__created_by"),
                              number=number)
    customer_orders = Order.objects.filter(Q(user=order.user) if order.user else Q(phone=order.phone)).exclude(pk=order.pk)[:6]
    return render(request, "dashboard/order_detail.html", {
        "order": order,
        "next_statuses": [(s, dict(Order.STATUS_CHOICES)[s]) for s in services.next_statuses(order)],
        "customer_orders": customer_orders,
        "lifetime": Order.objects.filter(Q(user=order.user) if order.user else Q(phone=order.phone),
                                         status__in=REVENUE).aggregate(t=Sum("total"), n=Count("id")),
    })


@staff
@require_POST
def order_status(request, number):
    order = get_object_or_404(Order, number=number)
    eta = parse_date(request.POST.get("estimated_delivery", "") or "")
    try:
        services.change_status(order, request.POST.get("status"), user=request.user,
                               note=request.POST.get("note", "").strip(),
                               courier=request.POST.get("courier", "").strip()[:100],
                               tracking=request.POST.get("tracking_number", "").strip()[:100], eta=eta)
        order.refresh_from_db()
        messages.success(request, f"{order.number} is now {order.get_status_display()}. The customer has been emailed where relevant.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("dashboard:order", number=number)


@staff
@require_POST
def order_update(request, number):
    """Edit delivery details / add an internal note."""
    order = get_object_or_404(Order, number=number)
    for f in ("full_name", "phone", "email", "city", "address", "courier", "tracking_number"):
        if f in request.POST:
            setattr(order, f, request.POST[f].strip()[:Order._meta.get_field(f).max_length or 500])
    eta = parse_date(request.POST.get("estimated_delivery", "") or "")
    if eta:
        order.estimated_delivery = eta
    order.save()
    note = request.POST.get("note", "").strip()
    if note:
        services.log_event(order, order.status, f"Note: {note}", request.user)
    messages.success(request, "Order updated.")
    return redirect("dashboard:order", number=number)


@staff
def order_invoice(request, number):
    order = get_object_or_404(Order.objects.prefetch_related("items"), number=number)
    return render(request, "dashboard/invoice.html", {"order": order, "shop": SiteSettings.load()})


# =====================================================================
# PRODUCTS
# =====================================================================
@staff
def product_list(request):
    shop = SiteSettings.load()
    qs = Product.objects.select_related("brand", "category").annotate(sold=Sum("variants__orderitem__quantity"))
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(brand__name__icontains=q) | Q(category__name__icontains=q))
    if request.GET.get("brand"):
        qs = qs.filter(brand__slug=request.GET["brand"])
    if request.GET.get("category"):
        qs = qs.filter(category__slug=request.GET["category"])
    stock = request.GET.get("stock")
    if stock == "low":
        qs = qs.filter(stock__gt=0, stock__lte=shop.low_stock_alert)
    elif stock == "out":
        qs = qs.filter(stock=0)
    status = request.GET.get("status")
    if status == "live":
        qs = qs.filter(is_active=True)
    elif status == "hidden":
        qs = qs.filter(is_active=False)
    elif status == "sample":
        qs = qs.filter(is_sample=True)
    sort = request.GET.get("sort", "-created_at")
    if sort in ("name", "-created_at", "price", "-price", "stock", "-stock", "-views", "-sold"):
        qs = qs.order_by(F(sort.lstrip("-")).desc(nulls_last=True) if sort.startswith("-") else sort)

    if request.GET.get("export") == "csv":
        return _csv_response("products.csv", IMPORT_COLUMNS, [_product_row(p) for p in qs.prefetch_related("concerns")])

    return render(request, "dashboard/products.html", {
        "page_obj": _page(request, qs, 40),
        "brands": Brand.objects.all(),
        "categories": Category.objects.select_related("department"),
        "querystring": _qs_without_page(request),
        "low": shop.low_stock_alert,
        "sample_count": Product.objects.filter(is_sample=True).count(),
    })


@staff
@require_POST
def product_quick_edit(request, pk):
    """Inline price / stock / live edits from the product table."""
    p = get_object_or_404(Product, pk=pk)
    field = request.POST.get("field")
    value = request.POST.get("value", "")
    try:
        if field == "price":
            p.price = Decimal(value)
            if p.price <= 0:
                raise InvalidOperation
            if p.variants.count() == 1:
                p.variants.update(price=p.price)
        elif field == "stock":
            p.stock = max(0, int(value))
            if p.variants.count() == 1:
                p.variants.update(stock=p.stock)
        elif field in ("is_active", "is_featured", "is_best_seller"):
            setattr(p, field, value in ("1", "true", "on"))
        else:
            return JsonResponse({"ok": False, "message": "Unknown field"}, status=400)
        p.save()
    except (InvalidOperation, ValueError):
        return JsonResponse({"ok": False, "message": "Invalid value"}, status=400)
    return JsonResponse({"ok": True})


@staff
@require_POST
def product_bulk(request):
    ids = [int(i) for i in request.POST.getlist("products") if i.isdigit()]
    action = request.POST.get("action")
    qs = Product.objects.filter(id__in=ids)
    n = qs.count()
    actions = {
        "activate": {"is_active": True}, "deactivate": {"is_active": False},
        "feature": {"is_featured": True}, "unfeature": {"is_featured": False},
        "bestseller": {"is_best_seller": True}, "not_bestseller": {"is_best_seller": False},
        "new": {"is_new": True}, "not_new": {"is_new": False},
    }
    if action in actions:
        qs.update(**actions[action])
        messages.success(request, f"Updated {n} product(s).")
    elif action == "infographic":
        from catalog.photos import make_photos

        for p in qs[:40]:  # drawing takes a moment per product
            make_photos(p)
        messages.success(request, f"Infographics created for {min(n, 40)} product(s).")
    elif action == "delete":
        qs.delete()
        messages.success(request, f"Deleted {n} product(s).")
    elif action == "discount":
        try:
            pct = Decimal(request.POST.get("percent", "0"))
            assert 0 < pct < 90
        except (InvalidOperation, AssertionError):
            messages.error(request, "Enter a discount between 1 and 89%.")
            return redirect("dashboard:products")
        for p in qs:
            base = p.compare_price if p.compare_price and p.compare_price > p.price else p.price
            p.compare_price = base
            p.price = (base * (100 - pct) / 100).quantize(Decimal("1"))
            p.save()
            p.variants.update(compare_price=base)
            for v in p.variants.all():
                v.price = (v.compare_price * (100 - pct) / 100).quantize(Decimal("1")) if v.compare_price else p.price
                v.save()
        messages.success(request, f"{pct}% sale applied to {n} product(s).")
    elif action == "end_sale":
        for p in qs.filter(compare_price__isnull=False):
            if p.compare_price > p.price:
                p.price, p.compare_price = p.compare_price, None
                p.save()
            for v in p.variants.all():
                if v.compare_price:
                    v.price, v.compare_price = v.compare_price, None
                    v.save()
        messages.success(request, "Sale ended — original prices restored.")
    return redirect(request.POST.get("next") or "dashboard:products")


@staff
def product_edit(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    form = forms.ProductForm(request.POST or None, request.FILES or None, instance=product)
    formset = forms.VariantFormSet(request.POST or None, instance=product or Product(), prefix="variants")
    concerns = Concern.objects.all()

    if request.method == "POST" and form.is_valid() and formset.is_valid():
        p = form.save(commit=False)
        p.is_sample = False
        for field in ("routine_step",):
            setattr(p, field, request.POST.get(field, ""))
        for field in ("servings_per_pack", "daily_servings"):
            try:
                setattr(p, field, max(0, int(request.POST.get(field) or 0)))
            except ValueError:
                pass
        for flag in ("is_vegan", "is_halal", "is_cruelty_free", "is_fragrance_free"):
            setattr(p, flag, bool(request.POST.get(flag)))
        p.save()
        p.concerns.set(Concern.objects.filter(id__in=request.POST.getlist("concerns")))
        formset.instance = p
        formset.save()
        if not p.variants.exists():
            p.default_variant()
        for i, f in enumerate(request.FILES.getlist("gallery")):
            if (f.content_type or "").startswith("image/"):
                ProductImage.objects.create(product=p, image=f, sort_order=p.images.count() + i)
        for img_id in request.POST.getlist("remove_image"):
            ProductImage.objects.filter(product=p, id=img_id).delete()
        messages.success(request, f"“{p.name}” saved.")
        if request.POST.get("save_and_new"):
            return redirect("dashboard:product_add")
        return redirect("dashboard:product_edit", pk=p.pk)

    return render(request, "dashboard/product_form.html", {
        "form": form, "formset": formset, "product": product, "concerns": concerns,
        "selected_concerns": [c.id for c in product.concerns.all()] if product else [],
        "routine_steps": Product._meta.get_field("routine_step").choices,
        "batches": product.batches.all() if product else [],
    })


@staff
@require_POST
def product_duplicate(request, pk):
    p = get_object_or_404(Product, pk=pk)
    variants, concerns = list(p.variants.all()), list(p.concerns.all())
    p.pk, p.slug, p.name, p.is_active, p.is_sample, p.views = None, "", f"{p.name} (copy)", False, False, 0
    p.save()
    p.concerns.set(concerns)
    for v in variants:
        v.pk, v.product = None, p
        v.save()
    messages.success(request, "Copy created (hidden until you publish it).")
    return redirect("dashboard:product_edit", pk=p.pk)


@staff
@require_POST
def product_infographic(request, pk):
    """Draw an infographic poster from the product's name, benefits and concerns and make it the main photo.
    A photo the shop uploaded is kept in the gallery."""
    from catalog.photos import make_photos

    p = get_object_or_404(Product, pk=pk)
    make_photos(p)
    messages.success(request, "Infographic created and set as the main photo. Your previous photo is in the gallery.")
    return redirect("dashboard:product_edit", pk=p.pk)


@staff
@require_POST
def product_delete(request, pk):
    p = get_object_or_404(Product, pk=pk)
    name = p.name
    p.delete()
    messages.success(request, f"Deleted “{name}”.")
    return redirect("dashboard:products")


@staff
@require_POST
def delete_samples(request):
    n = Product.objects.filter(is_sample=True).count()
    Product.objects.filter(is_sample=True).delete()
    messages.success(request, f"Removed {n} sample product(s). Your shop now only shows your real products.")
    return redirect("dashboard:products")


@staff
@require_POST
def batch_add(request, pk):
    p = get_object_or_404(Product, pk=pk)
    code = request.POST.get("code", "").strip()
    expiry = parse_date(request.POST.get("expiry_date", "") or "")
    if not code or not expiry:
        messages.error(request, "Batch code and expiry date are required.")
    elif Batch.objects.filter(code__iexact=code).exists():
        messages.error(request, "That batch code already exists.")
    else:
        qty = int(request.POST.get("quantity") or 0)
        Batch.objects.create(product=p, code=code, expiry_date=expiry, quantity=qty,
                             manufactured_on=parse_date(request.POST.get("manufactured_on", "") or ""),
                             imported_on=timezone.localdate(), supplier=request.POST.get("supplier", "")[:120])
        if request.POST.get("add_to_stock") and qty:
            p.stock += qty
            p.save()
            if p.variants.count() == 1:
                p.variants.update(stock=F("stock") + qty)
        messages.success(request, f"Batch {code.upper()} added.")
    return redirect(f"{reverse('dashboard:product_edit', args=[pk])}#batches")


# ---------------------------------------------------------------- import
IMPORT_COLUMNS = ["name", "brand", "department", "category", "form", "size_label", "price", "compare_price", "stock",
                  "short_description", "description", "benefits", "ingredients", "how_to_use", "skin_type",
                  "concerns", "routine_step", "servings_per_pack", "daily_servings", "weight_grams",
                  "image", "is_best_seller", "is_featured", "sku"]


def _product_row(p):
    return [p.name, p.brand.name if p.brand else "", p.category.department.name if p.category else "",
            p.category.name if p.category else "", p.form, p.size_label, p.price, p.compare_price or "", p.stock,
            p.short_description, p.description, p.benefits, p.ingredients, p.how_to_use, p.skin_type,
            "; ".join(c.name for c in p.concerns.all()), p.routine_step, p.servings_per_pack, p.daily_servings,
            p.weight_grams, p.image.name.split("/")[-1] if p.image else "", int(p.is_best_seller), int(p.is_featured), p.sku]


@staff
def import_template(request):
    return _csv_response("delightcare_products_template.csv", IMPORT_COLUMNS, [[
        "Vitamin C Glow Serum", "Japan", "Skincare", "Serums", "serum", "30ml", "2800", "3500", "25",
        "Brightens dull skin in 2 weeks", "Lightweight serum with 15% vitamin C…", "Brighter skin\nFades dark spots",
        "Aqua, Ascorbic Acid…", "Apply 3 drops morning and night", "All skin types", "Dark spots; Dull skin",
        "treat", "0", "1", "150", "vitamin-c-serum.jpg", "1", "0", "KR-VC30",
    ]])


@staff
def product_import(request):
    form = forms.ImportForm(request.POST or None, request.FILES or None)
    report = None
    if request.method == "POST" and form.is_valid():
        report = _run_import(form.cleaned_data["csv_file"], form.cleaned_data.get("images_zip"),
                             form.cleaned_data["update_existing"])
        messages.success(request, f"Import finished: {report['created']} added, {report['updated']} updated, "
                                  f"{len(report['errors'])} problem(s).")
    return render(request, "dashboard/import.html", {"form": form, "report": report, "columns": IMPORT_COLUMNS})


def _is_image(data):
    from PIL import Image
    try:
        Image.open(io.BytesIO(data)).verify()
        return True
    except Exception:
        return False


def _run_import(csv_file, zip_file, update_existing):
    images = {}
    if zip_file:
        try:
            with zipfile.ZipFile(zip_file) as z:
                for name in z.namelist():
                    base = name.split("/")[-1]
                    if base and not base.startswith(".") and base.lower().rsplit(".", 1)[-1] in ("jpg", "jpeg", "png", "webp"):
                        images[base.lower()] = (base, z.read(name))
        except zipfile.BadZipFile:
            return {"created": 0, "updated": 0, "errors": ["The images file isn't a valid .zip"]}

    text = csv_file.read().decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    created = updated = 0
    errors = []
    form_keys = dict(Product.FORM_CHOICES)
    step_keys = dict(Product._meta.get_field("routine_step").choices)

    for n, row in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        name = row.get("name")
        if not name:
            continue
        try:
            price = Decimal(row.get("price", "").replace(",", ""))
        except InvalidOperation:
            errors.append(f"Row {n} ({name}): price “{row.get('price')}” isn't a number")
            continue

        brand = None
        if row.get("brand"):
            brand, _ = Brand.objects.get_or_create(name=row["brand"])
        category = None
        if row.get("category"):
            dept = None
            if row.get("department"):
                dept, _ = Department.objects.get_or_create(name=row["department"])
            category = Category.objects.filter(name__iexact=row["category"]).first()
            if not category:
                dept = dept or Department.objects.get_or_create(name="Other")[0]
                category = Category.objects.create(name=row["category"], department=dept)

        product = Product.objects.filter(name__iexact=name, brand=brand).first() if update_existing else None
        is_new = product is None
        product = product or Product(name=name)
        product.brand, product.category, product.price = brand, category, price
        try:
            cp = Decimal(row.get("compare_price", "").replace(",", "") or "0")
        except InvalidOperation:
            cp = Decimal("0")
        product.compare_price = cp if cp > price else None
        product.form = row.get("form") if row.get("form") in form_keys else product.form or "other"
        product.routine_step = row.get("routine_step") if row.get("routine_step") in step_keys else product.routine_step
        for f in ("size_label", "short_description", "description", "benefits", "ingredients", "how_to_use", "skin_type", "sku"):
            if row.get(f) or is_new:
                setattr(product, f, row.get(f, "")[: Product._meta.get_field(f).max_length or 100000])
        for f in ("stock", "servings_per_pack", "daily_servings", "weight_grams"):
            if row.get(f, "").isdigit():
                setattr(product, f, int(row[f]))
        product.is_best_seller = row.get("is_best_seller") in ("1", "yes", "true")
        product.is_featured = row.get("is_featured") in ("1", "yes", "true")
        product.is_sample = False

        img_key = row.get("image", "").lower()
        if img_key and img_key in images:
            fname, data = images[img_key]
            if _is_image(data):
                product.image.save(fname, ContentFile(data), save=False)
            else:
                errors.append(f"Row {n} ({name}): “{fname}” isn't a readable photo")
        elif img_key:
            errors.append(f"Row {n} ({name}): image “{row.get('image')}” wasn't in the zip")

        try:
            product.save()
        except Exception as e:  # keep importing the other rows
            errors.append(f"Row {n} ({name}): couldn't save — {e}")
            continue
        if row.get("concerns"):
            names = [c.strip() for c in row["concerns"].replace(",", ";").split(";") if c.strip()]
            product.concerns.set([Concern.objects.get_or_create(name=c)[0] for c in names])
        v = product.default_variant()
        v.price, v.stock = product.price, product.stock
        v.compare_price = product.compare_price
        if product.size_label:
            v.label = product.size_label
        v.save()
        created += is_new
        updated += not is_new
    return {"created": created, "updated": updated, "errors": errors}


# =====================================================================
# CUSTOMERS
# =====================================================================
@staff
def customer_list(request):
    qs = User.objects.filter(is_staff=False).select_related("profile").annotate(
        orders_n=Count("orders", filter=Q(orders__status__in=REVENUE), distinct=True),
        spent=Sum("orders__total", filter=Q(orders__status__in=REVENUE)),
        last_order=Max("orders__created_at"),
    )
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q)
                       | Q(last_name__icontains=q) | Q(profile__phone__icontains=q))
    sort = request.GET.get("sort", "-date_joined")
    if sort in ("-date_joined", "-spent", "-orders_n", "-last_order"):
        qs = qs.order_by(F(sort[1:]).desc(nulls_last=True))
    if request.GET.get("export") == "csv":
        return _csv_response("customers.csv", ["Name", "Email", "Phone", "City", "Joined", "Orders", "Spent", "Newsletter"],
                             [[u.get_full_name() or u.username, u.email, u.profile.phone, u.profile.city,
                               u.date_joined.date(), u.orders_n, u.spent or 0, u.profile.marketing_opt_in] for u in qs])
    return render(request, "dashboard/customers.html", {"page_obj": _page(request, qs), "querystring": _qs_without_page(request)})


@staff
def customer_detail(request, pk):
    from accounts.models import points_balance

    u = get_object_or_404(User.objects.select_related("profile"), pk=pk)
    orders = u.orders.all()
    return render(request, "dashboard/customer_detail.html", {
        "customer": u, "orders": orders,
        "spent": orders.filter(status__in=REVENUE).aggregate(t=Sum("total"))["t"] or 0,
        "points": points_balance(u),
        "reviews": u.reviews.select_related("product")[:10],
        "wishlist": u.wishlist.select_related("product")[:12],
        "conversation": u.conversations.first(),
    })


@staff
@require_POST
def customer_points(request, pk):
    from accounts.models import PointsTransaction

    u = get_object_or_404(User, pk=pk)
    try:
        pts = int(request.POST.get("points", 0))
    except ValueError:
        pts = 0
    if pts:
        PointsTransaction.objects.create(user=u, points=pts, reason=request.POST.get("reason", "")[:120] or "Adjusted by shop")
        messages.success(request, f"{pts:+d} Glow Points for {u.get_full_name() or u.username}.")
    return redirect("dashboard:customer", pk=pk)


# =====================================================================
# REVIEWS
# =====================================================================
@staff
def review_list(request):
    qs = Review.objects.select_related("product", "user")
    f = request.GET.get("filter", "")
    if f == "pending":
        qs = qs.filter(is_approved=False)
    elif f == "low":
        qs = qs.filter(rating__lte=2)
    return render(request, "dashboard/reviews.html", {"page_obj": _page(request, qs), "filter": f})


@staff
@require_POST
def review_action(request, pk):
    r = get_object_or_404(Review, pk=pk)
    action = request.POST.get("action")
    if action == "approve":
        r.is_approved = True
        r.save()
    elif action == "hide":
        r.is_approved = False
        r.save()
    elif action == "delete":
        r.delete()
    return redirect(request.POST.get("next") or "dashboard:reviews")


# =====================================================================
# SIMPLE CRUD SCREENS (brands, categories, coupons, delivery, content…)
# =====================================================================
CRUD = {
    "brands": {"model": Brand, "form": forms.BrandForm, "title": "Brands", "icon": "fa-tags",
               "columns": [("name", "Brand"), ("country", "Country"), ("tagline", "Tagline")], "count": "products"},
    "departments": {"model": Department, "form": forms.DepartmentForm, "title": "Departments", "icon": "fa-layer-group",
                    "columns": [("name", "Department"), ("sort_order", "Order"), ("is_active", "Live")], "count": "categories"},
    "categories": {"model": Category, "form": forms.CategoryForm, "title": "Categories", "icon": "fa-sitemap",
                   "columns": [("name", "Category"), ("department", "Department"), ("is_active", "Live")], "count": "products"},
    "concerns": {"model": Concern, "form": None, "title": "Concerns", "icon": "fa-heart-pulse",
                 "columns": [("emoji", ""), ("name", "Concern"), ("group", "Group")], "count": "products",
                 "fields": ["name", "emoji", "group", "icon", "sort_order"]},
    "coupons": {"model": Coupon, "form": forms.CouponForm, "title": "Coupons", "icon": "fa-ticket",
                "columns": [("code", "Code"), ("get_discount_type_display", "Type"), ("value", "Value"),
                            ("used_count", "Used"), ("valid_until", "Ends"), ("is_active", "Active")]},
    "delivery": {"model": DeliveryZone, "form": forms.DeliveryZoneForm, "title": "Delivery prices", "icon": "fa-truck-fast",
                 "columns": [("name", "Zone"), ("pickup_fee", "Pickup (1kg)"), ("home_fee", "Door (1kg)"),
                             ("extra_kg_fee", "+ per kg"), ("delivery_days", "Time")]},
    "banners": {"model": Banner, "form": forms.BannerForm, "title": "Home banners", "icon": "fa-images",
                "columns": [("title", "Title"), ("link", "Link"), ("is_active", "Live")]},
    "testimonials": {"model": Testimonial, "form": forms.TestimonialForm, "title": "Testimonials", "icon": "fa-quote-left",
                     "columns": [("name", "Name"), ("location", "From"), ("rating", "Stars"), ("is_active", "Live")]},
    "posts": {"model": Post, "form": forms.PostForm, "title": "Blog posts", "icon": "fa-pen-nib",
              "columns": [("title", "Title"), ("get_topic_display", "Topic"), ("views", "Views"), ("is_published", "Live")]},
    "batches": {"model": Batch, "form": None, "title": "Batches & expiry", "icon": "fa-barcode",
                "columns": [("code", "Batch"), ("product", "Product"), ("expiry_date", "Expires"), ("quantity", "Qty")],
                "fields": ["product", "code", "manufactured_on", "expiry_date", "imported_on", "supplier", "quantity"]},
}


class _StyledModelForm(forms.StyledMixin, ModelForm):
    pass


def _crud_form(cfg):
    if cfg["form"]:
        return cfg["form"]
    return modelform_factory(cfg["model"], form=_StyledModelForm, fields=cfg["fields"],
                             widgets={f: DateInput(attrs={"type": "date"})
                                      for f in cfg["fields"] if f.endswith(("_on", "_date"))})


@staff
def crud_list(request, kind):
    cfg = CRUD.get(kind)
    if not cfg:
        return redirect("dashboard:overview")
    qs = cfg["model"].objects.all()
    if kind == "coupons":
        qs = qs.filter(referrer__isnull=True)  # customers' refer-a-friend codes are listed under Marketing
    if cfg.get("count"):
        qs = qs.annotate(_n=Count(cfg["count"], distinct=True))
    q = request.GET.get("q", "").strip()
    if q:
        search_field = {"coupons": "code", "batches": "code", "banners": "title", "posts": "title"}.get(kind, "name")
        qs = qs.filter(**{f"{search_field}__icontains": q})
    rows = []
    for obj in qs:
        cells = []
        for attr, _ in cfg["columns"]:
            val = getattr(obj, attr)
            cells.append(val() if callable(val) else val)
        rows.append({"obj": obj, "cells": cells, "count": getattr(obj, "_n", None)})
    return render(request, "dashboard/crud_list.html", {"cfg": cfg, "kind": kind, "rows": rows, "q": q})


@staff
def crud_edit(request, kind, pk=None):
    cfg = CRUD.get(kind)
    if not cfg:
        return redirect("dashboard:overview")
    obj = get_object_or_404(cfg["model"], pk=pk) if pk else None
    FormClass = _crud_form(cfg)
    form = FormClass(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST":
        if request.POST.get("delete") and obj:
            obj.delete()
            messages.success(request, "Deleted.")
            return redirect("dashboard:crud", kind=kind)
        if form.is_valid():
            saved = form.save()
            if kind == "posts" and not saved.author_id:
                saved.author = request.user
                saved.save()
            messages.success(request, f"Saved “{saved}”.")
            return redirect("dashboard:crud", kind=kind)
    return render(request, "dashboard/crud_form.html", {"cfg": cfg, "kind": kind, "form": form, "obj": obj})


# =====================================================================
# MESSAGES, NEWSLETTER, INBOX
# =====================================================================
@staff
def inbox(request):
    return render(request, "dashboard/inbox.html", {"open_id": request.GET.get("c", "")})


@staff
def contact_messages(request):
    if request.method == "POST":
        ContactMessage.objects.filter(pk=request.POST.get("id")).update(is_handled=request.POST.get("handled") == "1")
        return redirect("dashboard:contact_messages")
    return render(request, "dashboard/contact_messages.html", {"page_obj": _page(request, ContactMessage.objects.all())})


@staff
def newsletter(request):
    subs = NewsletterSubscriber.objects.filter(is_active=True).order_by("-created_at")
    members = User.objects.filter(profile__marketing_opt_in=True).exclude(email="")
    if request.GET.get("export") == "csv":
        emails = {s.email: s.created_at.date() for s in subs}
        for u in members:
            emails.setdefault(u.email.lower(), u.date_joined.date())
        return _csv_response("newsletter.csv", ["email", "since"], sorted(emails.items()))
    return render(request, "dashboard/newsletter.html", {"page_obj": _page(request, subs, 50), "members": members.count()})


@staff
def stock_alerts(request):
    qs = (StockAlert.objects.filter(notified_at__isnull=True).values("product__id", "product__name", "product__stock")
          .annotate(n=Count("id")).order_by("-n"))
    return render(request, "dashboard/stock_alerts.html", {"rows": qs})


# =====================================================================
# REPORTS
# =====================================================================
@staff
def reports(request):
    today = timezone.localdate()
    d_from = parse_date(request.GET.get("from", "") or "") or today - timedelta(days=29)
    d_to = parse_date(request.GET.get("to", "") or "") or today
    orders = Order.objects.filter(status__in=REVENUE, created_at__date__gte=d_from, created_at__date__lte=d_to)
    items = OrderItem.objects.filter(order__in=orders)
    line_total = Sum(F("unit_price") * F("quantity"))

    totals = orders.aggregate(revenue=Sum("total"), n=Count("id"), discount=Sum("discount"), delivery=Sum("delivery_fee"))
    totals["aov"] = (totals["revenue"] / totals["n"]) if totals["n"] else 0
    totals["units"] = items.aggregate(u=Sum("quantity"))["u"] or 0

    by_day = list(orders.annotate(d=TruncDate("created_at")).values("d").annotate(t=Sum("total"), n=Count("id")).order_by("d"))
    by_product = items.values("product_name", "brand_name").annotate(units=Sum("quantity"), revenue=line_total).order_by("-revenue")[:25]
    by_brand = items.values("brand_name").annotate(units=Sum("quantity"), revenue=line_total).order_by("-revenue")
    by_dept = (items.values("variant__product__category__department__name")
               .annotate(units=Sum("quantity"), revenue=line_total).order_by("-revenue"))
    by_city = orders.values("city").annotate(n=Count("id"), t=Sum("total")).order_by("-t")[:10]
    coupons = orders.exclude(coupon_code="").values("coupon_code").annotate(n=Count("id"), d=Sum("discount")).order_by("-n")
    by_source = orders.values("source", "medium").annotate(n=Count("id"), t=Sum("total")).order_by("-t")
    by_campaign = orders.exclude(campaign="").values("source", "campaign").annotate(n=Count("id"), t=Sum("total")).order_by("-t")[:15]

    if request.GET.get("export") == "csv":
        return _csv_response(f"sales_{d_from}_{d_to}.csv", ["Product", "Brand", "Units", "Revenue"],
                             [[r["product_name"], r["brand_name"], r["units"], r["revenue"]] for r in
                              items.values("product_name", "brand_name").annotate(units=Sum("quantity"), revenue=line_total).order_by("-revenue")])

    return render(request, "dashboard/reports.html", {
        "d_from": d_from, "d_to": d_to, "totals": totals,
        "chart_labels": json.dumps([r["d"].strftime("%b %d") for r in by_day]),
        "chart_values": json.dumps([float(r["t"]) for r in by_day]),
        "by_product": by_product, "by_brand": by_brand, "by_dept": by_dept, "by_city": by_city, "coupons": coupons,
        "by_source": by_source, "by_campaign": by_campaign,
    })


# =====================================================================
# SETTINGS
# =====================================================================
@staff
def shop_settings(request):
    obj = SiteSettings.load()
    form = forms.SiteSettingsForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Shop settings saved.")
        return redirect("dashboard:settings")
    return render(request, "dashboard/settings.html", {"form": form})
