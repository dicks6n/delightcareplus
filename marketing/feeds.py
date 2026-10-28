"""
Product catalogs for advertising, refreshed automatically from the shop:

  /feeds/google.xml   Google Merchant Center (Shopping ads, free listings)
  /feeds/meta.csv     Meta Commerce Manager (Instagram & Facebook Shop, catalog ads, WhatsApp catalog)
  /feeds/tiktok.csv   TikTok catalog (TikTok Shop ads / video shopping ads)

Paste the link into each platform as a "scheduled feed" so prices and stock stay in sync.
"""
import csv
from xml.sax.saxutils import escape

from django.http import HttpResponse
from django.utils.html import strip_tags
from django.views.decorators.cache import cache_page

from catalog.models import Product
from core.models import SiteSettings

CATEGORY = {  # Google product taxonomy (also understood by Meta and TikTok)
    "Supplements": "Health & Beauty > Health Care > Fitness & Nutrition > Vitamins & Supplements",
    "Skincare": "Health & Beauty > Personal Care > Cosmetics > Skin Care",
    "Tea": "Food, Beverages & Tobacco > Beverages > Tea & Infusions",
}


def _products():
    return (Product.objects.live().filter(price__gt=0).exclude(image="")
            .select_related("brand", "category__department").prefetch_related("images", "variants"))


def _rows(request):
    shop = SiteSettings.load()
    base = request.build_absolute_uri("/").rstrip("/")
    for p in _products():
        dept = p.category.department.name if p.category else ""
        on_sale = p.compare_price and p.compare_price > p.price
        description = strip_tags(p.short_description or p.description or p.name)
        if p.benefits:
            description += " " + " · ".join(p.benefit_list)
        yield {
            "id": str(p.id),  # must match the content_id the tracking code sends (static/js/tracking.js)
            "title": p.name[:150],
            "description": description[:4900],
            "link": base + p.get_absolute_url(),
            "image": base + p.image.url,
            "extra_images": [base + i.image.url for i in p.images.all()[:10]],
            "availability": "in stock" if p.in_stock else "out of stock",
            "price": f"{(p.compare_price if on_sale else p.price):.2f} KES",
            "sale_price": f"{p.price:.2f} KES" if on_sale else "",
            "brand": shop.feed_brand or "Delight Care Plus",
            "category": CATEGORY.get(dept, "Health & Beauty"),
            "product_type": " > ".join(x for x in (dept, p.category.name if p.category else "") if x),
            "collection": p.brand.name if p.brand else "",
            "inventory": p.stock,
        }


@cache_page(60 * 15)
def google(request):
    items = []
    for r in _rows(request):
        extra = "".join(f"<g:additional_image_link>{escape(u)}</g:additional_image_link>" for u in r["extra_images"])
        sale = f"<g:sale_price>{r['sale_price']}</g:sale_price>" if r["sale_price"] else ""
        label = f"<g:custom_label_0>{escape(r['collection'])}</g:custom_label_0>" if r["collection"] else ""
        items.append(
            "<item>"
            f"<g:id>{escape(r['id'])}</g:id><title>{escape(r['title'])}</title>"
            f"<description>{escape(r['description'])}</description><link>{escape(r['link'])}</link>"
            f"<g:image_link>{escape(r['image'])}</g:image_link>{extra}"
            f"<g:availability>{r['availability']}</g:availability><g:price>{r['price']}</g:price>{sale}"
            f"<g:brand>{escape(r['brand'])}</g:brand><g:condition>new</g:condition><g:identifier_exists>no</g:identifier_exists>"
            f"<g:google_product_category>{escape(r['category'])}</g:google_product_category>"
            f"<g:product_type>{escape(r['product_type'])}</g:product_type>{label}"
            "</item>"
        )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0"><channel>'
           f"<title>Delight Care Plus</title><link>{escape(request.build_absolute_uri('/'))}</link>"
           "<description>Supplements, skincare and wellness tea</description>" + "".join(items) + "</channel></rss>")
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")


def _csv(header, rows, filename):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(header)
    writer.writerows(rows)
    return response


@cache_page(60 * 15)
def meta(request):
    header = ["id", "title", "description", "availability", "condition", "price", "sale_price", "link", "image_link",
              "additional_image_link", "brand", "google_product_category", "product_type", "inventory", "custom_label_0"]
    rows = [[r["id"], r["title"], r["description"], r["availability"], "new", r["price"], r["sale_price"], r["link"],
             r["image"], ",".join(r["extra_images"]), r["brand"], r["category"], r["product_type"], r["inventory"],
             r["collection"]] for r in _rows(request)]
    return _csv(header, rows, "delightcareplus-meta.csv")


@cache_page(60 * 15)
def tiktok(request):
    header = ["sku_id", "title", "description", "availability", "condition", "price", "sale_price", "link", "image_link",
              "additional_image_link", "brand", "google_product_category", "product_type", "inventory"]
    rows = [[r["id"], r["title"], r["description"], r["availability"], "new", r["price"], r["sale_price"], r["link"],
             r["image"], ",".join(r["extra_images"]), r["brand"], r["category"], r["product_type"], r["inventory"]]
            for r in _rows(request)]
    return _csv(header, rows, "delightcareplus-tiktok.csv")
