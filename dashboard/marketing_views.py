"""Seller Center → Marketing: ad settings and feeds, Ad Studio, tracked links, email campaigns, referrals."""
import io
import zipfile
from datetime import timedelta

from django import forms as djforms
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from PIL import Image

from accounts.models import PointsTransaction
from cart.models import Coupon
from catalog.models import Product
from core.models import SiteSettings
from marketing import adstudio, emailing
from marketing.captions import captions
from marketing.models import EmailCampaign, TrackedLink
from orders.models import Order

from . import forms
from .forms import StyledMixin

staff = staff_member_required(login_url="accounts:login")
REVENUE = ["PAID", "PROCESSING", "PACKED", "SHIPPED", "OUT_FOR_DELIVERY", "DELIVERED"]


def _base_url(request):
    return request.build_absolute_uri("/").rstrip("/")


# ===================================================================== hub
@staff
def marketing(request):
    shop = SiteSettings.load()
    form = forms.MarketingSettingsForm(request.POST or None, instance=shop)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Marketing settings saved.")
        return redirect("dashboard:marketing")

    since = timezone.now() - timedelta(days=30)
    orders = Order.objects.filter(status__in=REVENUE, created_at__gte=since)
    sources = (orders.exclude(source="").values("source", "medium")
               .annotate(n=Count("id"), revenue=Sum("total")).order_by("-revenue")[:8])
    untracked = orders.filter(source="").aggregate(n=Count("id"), revenue=Sum("total"))
    links = _link_stats(TrackedLink.objects.all()[:8])
    referral = {
        "codes": Coupon.objects.filter(referrer__isnull=False).count(),
        "orders": Order.objects.filter(coupon_code__in=Coupon.objects.filter(referrer__isnull=False).values("code"),
                                       status__in=REVENUE).count(),
        "points": PointsTransaction.objects.filter(reason__startswith="Friend's first order").aggregate(s=Sum("points"))["s"] or 0,
    }
    base = _base_url(request)
    feeds = [
        ("Meta (Instagram & Facebook Shop, WhatsApp catalog)", "fa-brands fa-meta", base + reverse("marketing:feed_meta"),
         "Commerce Manager → Catalogue → Data sources → Data feed → Scheduled feed → paste the link, daily."),
        ("TikTok catalog", "fa-brands fa-tiktok", base + reverse("marketing:feed_tiktok"),
         "TikTok Ads Manager → Assets → Catalogs → Add products → Data feed → paste the link, daily."),
        ("Google Merchant Center", "fa-brands fa-google", base + reverse("marketing:feed_google"),
         "Merchant Center → Products → Add product source → Scheduled fetch → paste the link, daily."),
        ("Sitemap (Google Search Console)", "fa-solid fa-sitemap", base + "/sitemap.xml",
         "Search Console → Sitemaps → paste the link → Submit."),
    ]
    return render(request, "dashboard/marketing.html", {
        "form": form, "shop": shop, "sources": sources, "untracked": untracked, "links": links,
        "referral": referral, "feeds": feeds,
        "pixels": [("Meta Pixel", shop.meta_pixel_id), ("TikTok Pixel", shop.tiktok_pixel_id), ("Google Analytics", shop.ga4_id)],
        "campaigns": EmailCampaign.objects.all()[:5],
        "audience_size": len(emailing.audience_emails("everyone")),
    })


def _link_stats(links):
    rows = []
    for link in links:
        o = Order.objects.filter(status__in=REVENUE, source=link.source, campaign=link.campaign or link.slug)
        if link.medium:
            o = o.filter(medium=link.medium)
        agg = o.aggregate(n=Count("id"), revenue=Sum("total"))
        rows.append({"link": link, "orders": agg["n"], "revenue": agg["revenue"] or 0,
                     "rate": (agg["n"] / link.clicks * 100) if link.clicks else 0})
    return rows


@staff
def links(request):
    return render(request, "dashboard/links.html", {"rows": _link_stats(TrackedLink.objects.all()),
                                                    "base": _base_url(request)})


class TrackedLinkForm(StyledMixin, djforms.ModelForm):
    class Meta:
        model = TrackedLink
        fields = ["slug", "source", "medium", "campaign", "destination", "note"]

    slug = djforms.CharField(max_length=40, help_text=TrackedLink._meta.get_field("slug").help_text)

    def clean_slug(self):
        from django.utils.text import slugify
        v = slugify(self.cleaned_data["slug"])[:40]
        if not v:
            raise djforms.ValidationError("Use letters or numbers, e.g. ig-bio.")
        if TrackedLink.objects.filter(slug=v).exclude(pk=self.instance.pk).exists():
            raise djforms.ValidationError(f"/go/{v} is already used — pick another name.")
        return v

    def clean_destination(self):
        from marketing.views import is_local
        v = self.cleaned_data["destination"].strip()
        base = settings.SITE_URL.rstrip("/")
        if v.startswith(base):
            v = v[len(base):] or "/"
        if not is_local(v):
            raise djforms.ValidationError("Use a page on this shop, e.g. / or /shop/c/collagen/ (copy it from the address bar).")
        return v


@staff
def link_edit(request, pk=None):
    obj = get_object_or_404(TrackedLink, pk=pk) if pk else None
    initial = {"destination": request.GET.get("to", "/"), "source": request.GET.get("source", "")}
    form = TrackedLinkForm(request.POST or None, instance=obj, initial=None if obj else initial)
    if request.method == "POST":
        if request.POST.get("delete") and obj:
            obj.delete()
            messages.success(request, "Link deleted.")
            return redirect("dashboard:links")
        if form.is_valid():
            link = form.save()
            messages.success(request, f"Link ready: {_base_url(request)}{link.get_absolute_url()}")
            return redirect("dashboard:links")
    return render(request, "dashboard/link_form.html", {"form": form, "obj": obj, "base": _base_url(request)})


# ===================================================================== ad studio
def _ad_params(request, product):
    g = request.GET
    shop = SiteSettings.load()
    on_sale = product.compare_price and product.compare_price > product.price
    default_badge = f"-{product.discount_percent}%" if on_sale else ("Best seller" if product.is_best_seller else ("New" if product.is_new else ""))
    phone = shop.whatsapp_number
    local = ("0" + phone[3:]) if phone.startswith("254") else phone
    pretty = f"{local[:4]} {local[4:7]} {local[7:]}".strip()
    return {
        "fmt": g.get("fmt", "post") if g.get("fmt") in adstudio.FORMATS else "post",
        "style": g.get("style", "dark") if g.get("style") in adstudio.STYLES else "dark",
        "headline": g.get("headline", product.name)[:120],
        "sub": g.get("sub", product.short_description)[:200],
        "badge": g.get("badge", default_badge)[:14],
        "big_offer": g.get("big_offer", f"{product.discount_percent}% OFF" if on_sale else "")[:20],
        "coupon": g.get("coupon", "").upper()[:20],
        "cta": g.get("cta", "Shop now")[:24],
        "show_price": g.get("show_price", "1") == "1",
        "footer": g.get("footer", f"{settings.SITE_URL.split('://')[-1].rstrip('/').removeprefix('www.')}  ·  WhatsApp {pretty}")[:70],
    }


def _render(product, p, fmt=None):
    photo_field = product.showcase_image()
    photo = Image.open(photo_field.path) if photo_field else Image.new("RGB", (800, 800), (240, 236, 228))
    on_sale = product.compare_price and product.compare_price > product.price
    return adstudio.render_ad(
        photo, fmt or p["fmt"], p["style"], headline=p["headline"], sub=p["sub"],
        price=f"KES {product.price:,.0f}" if p["show_price"] else "",
        old_price=f"KES {product.compare_price:,.0f}" if (p["show_price"] and on_sale) else "",
        badge=p["badge"], coupon=p["coupon"], cta=p["cta"], footer=p["footer"],
        collection=product.brand.country_code if product.brand else "default", big_offer=p["big_offer"])


@staff
def ad_studio(request):
    products = Product.objects.filter(is_active=True).select_related("brand").order_by("name")
    product = products.filter(pk=request.GET.get("product")).first() if request.GET.get("product") else None
    product = product or products.filter(is_best_seller=True).first() or products.first()
    ctx = {"products": products, "product": product, "formats": adstudio.FORMATS, "styles": adstudio.STYLES,
           "coupons": Coupon.objects.filter(is_active=True, referrer__isnull=True)}
    if product:
        p = _ad_params(request, product)
        shop = SiteSettings.load()
        query = request.GET.copy()
        query["product"] = product.pk
        ctx.update({"p": p, "query": query.urlencode(),
                    "captions": captions(product, _base_url(request), offer=p["big_offer"] or p["badge"], coupon=p["coupon"],
                                         price_text=f"KES {product.price:,.0f}" if p["show_price"] else "",
                                         whatsapp=p["footer"].split("WhatsApp")[-1].strip() if "WhatsApp" in p["footer"] else "")})
    return render(request, "dashboard/ad_studio.html", ctx)


@staff
def ad_image(request, pk):
    product = get_object_or_404(Product, pk=pk)
    p = _ad_params(request, product)
    img = _render(product, p)
    if request.GET.get("preview"):
        img.thumbnail((900, 900))
    response = HttpResponse(adstudio.jpeg(img, 86 if request.GET.get("preview") else 92), content_type="image/jpeg")
    if request.GET.get("download"):
        response["Content-Disposition"] = f'attachment; filename="{product.slug}-{p["fmt"]}-{p["style"]}.jpg"'
    return response


@staff
def ad_pack(request, pk):
    """All three sizes in one zip, plus the captions."""
    product = get_object_or_404(Product, pk=pk)
    p = _ad_params(request, product)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for fmt in adstudio.FORMATS:
            z.writestr(f"{product.slug}-{fmt}.jpg", adstudio.jpeg(_render(product, p, fmt), 92))
        caps = captions(product, _base_url(request), offer=p["big_offer"] or p["badge"], coupon=p["coupon"],
                        price_text=f"KES {product.price:,.0f}" if p["show_price"] else "")
        z.writestr("captions.txt", "\n\n".join(f"===== {c['label']} =====\n{c['text']}" for c in caps.values()))
    response = HttpResponse(buf.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{product.slug}-ads.zip"'
    return response


# ===================================================================== email campaigns
class CampaignForm(StyledMixin, djforms.ModelForm):
    class Meta:
        model = EmailCampaign
        fields = ["subject", "heading", "body", "products", "coupon", "button_text", "button_link", "audience"]
        widgets = {"body": djforms.Textarea(attrs={"rows": 7}), "products": djforms.SelectMultiple(attrs={"size": 8})}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["products"].queryset = Product.objects.filter(is_active=True).order_by("name")
        self.fields["coupon"].queryset = Coupon.objects.filter(is_active=True, referrer__isnull=True)


@staff
def campaigns(request):
    rows = EmailCampaign.objects.all()
    sizes = {a: len(emailing.audience_emails(a)) for a, _ in EmailCampaign.AUDIENCES}
    for c in rows:
        o = Order.objects.filter(status__in=REVENUE, source="email", campaign=f"campaign-{c.pk}").aggregate(n=Count("id"), r=Sum("total"))
        c.orders, c.revenue = o["n"], o["r"] or 0
    return render(request, "dashboard/campaigns.html", {"rows": rows, "sizes": sizes})


@staff
def campaign_edit(request, pk=None):
    obj = get_object_or_404(EmailCampaign, pk=pk) if pk else None
    if obj and obj.sent_at and request.method == "POST":
        messages.error(request, "This campaign has been sent. Duplicate it to send again.")
        return redirect("dashboard:campaign", pk=obj.pk)
    form = CampaignForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, "Campaign saved. Send yourself a test, then send it.")
        return redirect("dashboard:campaign", pk=obj.pk)
    sizes = {a: len(emailing.audience_emails(a)) for a, _ in EmailCampaign.AUDIENCES}
    return render(request, "dashboard/campaign_form.html", {"form": form, "obj": obj, "sizes": sizes})


@staff
def campaign_preview(request, pk):
    from django.template.loader import render_to_string
    campaign = get_object_or_404(EmailCampaign, pk=pk)
    ctx = emailing.campaign_context(campaign, _base_url(request))
    return HttpResponse(render_to_string("emails/campaign.html", {**ctx, "unsubscribe_url": "#"}))


@staff
@require_POST
def campaign_send(request, pk):
    campaign = get_object_or_404(EmailCampaign, pk=pk)
    if request.POST.get("test"):
        to = request.POST.get("test_email") or request.user.email
        if not to:
            messages.error(request, "Add an email address for the test.")
        elif emailing.send_campaign(campaign, _base_url(request), only_to=to):
            messages.success(request, f"Test sent to {to}.")
        else:
            messages.error(request, "The test couldn't be sent — check the email settings in .env (EMAIL_HOST_USER / PASSWORD).")
        return redirect("dashboard:campaign", pk=pk)
    if campaign.sent_at:
        messages.error(request, "This campaign was already sent.")
        return redirect("dashboard:campaign", pk=pk)
    n = emailing.send_campaign(campaign, _base_url(request))
    if n:
        messages.success(request, f"Sent to {n} people.")
    else:
        messages.error(request, "Nothing was sent — no one in this audience yet, or the email settings in .env need checking.")
    return redirect("dashboard:campaign", pk=pk)


@staff
@require_POST
def campaign_duplicate(request, pk):
    campaign = get_object_or_404(EmailCampaign, pk=pk)
    products = list(campaign.products.all())
    campaign.pk, campaign.sent_at, campaign.sent_count = None, None, 0
    campaign.subject = f"{campaign.subject} (copy)"
    campaign.save()
    campaign.products.set(products)
    return redirect("dashboard:campaign", pk=campaign.pk)
