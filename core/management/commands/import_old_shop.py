"""
Copy data from the old Delight Care Plus site (the `store` app) into this one.

    python manage.py import_old_shop /path/to/old/db.sqlite3 --media /path/to/old/media

What comes across: customer accounts (they keep their passwords), categories,
products with sizes and photos, orders (as history), reviews, coupons, blog
posts and newsletter subscribers. Running it twice is safe: anything already
imported is skipped.

The old database is only read, never changed.
"""
import shutil
import sqlite3
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify

from blog.models import Post
from cart.models import Coupon
from catalog.models import Category, Department, Product, Review, Variant
from core.models import NewsletterSubscriber
from orders.models import Order, OrderItem

IMPORTED_NOTE = "Imported from the old website"

# Old status → new status
STATUS = {
    "PAYMENT_PENDING": "PENDING", "PLACED": "PROCESSING", "PAID": "PAID", "PROCESSING": "PROCESSING",
    "PACKED": "PACKED", "SHIPPED": "SHIPPED", "OUT_FOR_DELIVERY": "OUT_FOR_DELIVERY", "DELIVERED": "DELIVERED",
    "CANCELLED": "CANCELLED", "FAILED": "FAILED", "REFUNDED": "REFUNDED",
}
TOPIC = {"supplements": "supplements", "nutrition": "nutrition", "wellness": "wellness", "lifestyle": "wellness",
         "product": "news", "tips": "wellness", "research": "supplements"}
# Old category names → the matching category in the new shop
CATEGORY_ALIASES = {"brain health": "Brain & Focus", "joint health": "Joint & Bone", "bone health": "Joint & Bone",
                    "skin health": "Skin, Hair & Nails", "hair & skin": "Skin, Hair & Nails",
                    "weight loss": "Weight Management", "sleep": "Sleep & Stress", "stress": "Sleep & Stress",
                    "energy": "Energy & Vitality", "immunity": "Immune Support", "digestion": "Digestive Health"}
# Words in an old category name that tell us which department it belongs to
SKINCARE_WORDS = ("skin", "face", "mask", "serum", "cream", "beauty", "cleanser", "toner", "moistur", "sun")
TEA_WORDS = ("tea", "infusion", "herbal drink")


def dec(value, default="0"):
    try:
        return Decimal(str(value if value not in (None, "") else default))
    except InvalidOperation:
        return Decimal(default)


def when(value):
    if not value:
        return None
    dt = parse_datetime(str(value).replace(" ", "T", 1))
    if dt and dt.tzinfo is None:
        from django.utils import timezone
        dt = timezone.make_aware(dt)
    return dt


class Command(BaseCommand):
    help = "Import customers, products, orders and posts from the old Delight Care Plus database."

    def add_arguments(self, parser):
        parser.add_argument("database", help="Path to the old db.sqlite3")
        parser.add_argument("--media", help="Path to the old media folder (to copy product and blog photos)")
        parser.add_argument("--skip-orders", action="store_true", help="Don't import old orders")

    def handle(self, database, media=None, skip_orders=False, **opts):
        path = Path(database)
        if not path.exists():
            raise CommandError(f"Can't find {path}")
        self.media = Path(media) if media else None
        if self.media and not self.media.is_dir():
            raise CommandError(f"{self.media} isn't a folder")
        # Open read-only so the old site can't be damaged
        self.db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self.db.row_factory = sqlite3.Row
        self.tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "store_product" not in self.tables:
            raise CommandError("This doesn't look like the old shop database (no store_product table).")

        with transaction.atomic():
            users = self.import_users()
            cats = self.import_categories()
            products, variants = self.import_products(cats)
            if not skip_orders:
                self.import_orders(users, variants)
            self.import_reviews(users, products)
            self.import_coupons()
            self.import_posts(users)
            self.import_newsletter()
        self.stdout.write(self.style.SUCCESS("✅ Import finished. Check Seller Center → Products to tidy up brands and details."))

    # ------------------------------------------------------------------ helpers
    def rows(self, table):
        if table not in self.tables:
            return []
        return [dict(r) for r in self.db.execute(f'SELECT * FROM "{table}"')]

    def copy_file(self, name):
        """Copy an old media file across; returns the new relative name or ''."""
        if not name or not self.media:
            return ""
        src = self.media / name
        if not src.is_file():
            return ""
        dest = Path(settings.MEDIA_ROOT) / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copy2(src, dest)
        return name

    def say(self, what, created, skipped=0):
        extra = f" ({skipped} already here)" if skipped else ""
        self.stdout.write(f"  • {what}: {created} imported{extra}")

    # ------------------------------------------------------------------ steps
    def import_users(self):
        mapping, created, skipped = {}, 0, 0
        for r in self.rows("auth_user"):
            user = User.objects.filter(username=r["username"]).first()
            if user:
                skipped += 1
            else:
                user = User(username=r["username"], email=r.get("email") or "", first_name=r.get("first_name") or "",
                            last_name=r.get("last_name") or "", is_staff=bool(r.get("is_staff")),
                            is_superuser=bool(r.get("is_superuser")), is_active=bool(r.get("is_active", 1)))
                user.password = r["password"]  # same hashing, so old passwords keep working
                user.save()
                User.objects.filter(pk=user.pk).update(date_joined=when(r.get("date_joined")) or user.date_joined)
                created += 1
            mapping[r["id"]] = user
        self.say("Customer accounts", created, skipped)
        return mapping

    def department_for(self, name):
        n = name.lower()
        if any(w in n for w in TEA_WORDS):
            title = "Tea"
        elif any(w in n for w in SKINCARE_WORDS):
            title = "Skincare"
        else:
            title = "Supplements"
        return Department.objects.get_or_create(name=title)[0]

    def import_categories(self):
        mapping, created = {}, 0
        used = {r["category_id"] for r in self.rows("store_product")}
        for r in self.rows("store_category"):
            if r["id"] not in used:
                continue  # empty old categories (e.g. "General") aren't brought across
            name = CATEGORY_ALIASES.get(r["name"].strip().lower(), r["name"])
            cat = Category.objects.filter(name__iexact=name).first()
            if not cat:
                cat = Category.objects.create(name=r["name"], department=self.department_for(r["name"]),
                                              description=r.get("description") or "",
                                              is_active=bool(r.get("is_active", 1)))
                created += 1
            mapping[r["id"]] = cat
        self.say("Categories", created, len(mapping) - created)
        return mapping

    def import_products(self, cats):
        products, variants, created = {}, {}, 0
        old_variants = {}
        for v in self.rows("store_productvariant"):
            old_variants.setdefault(v["product_id"], []).append(v)
        for r in self.rows("store_product"):
            existing = Product.objects.filter(name__iexact=r["name"], brand__isnull=True).first()
            if existing:
                products[r["id"]] = existing
                for v in old_variants.get(r["id"], []):
                    variants[v["id"]] = existing.variants.filter(label=v["size"]).first()
                continue
            price, compare = dec(r.get("price")), dec(r.get("compare_price"), "0")
            p = Product(
                name=r["name"], description=r.get("description") or "", category=cats.get(r.get("category_id")),
                price=price, compare_price=compare if compare > price else None, stock=r.get("stock") or 0,
                is_active=bool(r.get("is_active", 1)), is_featured=bool(r.get("is_featured")),
                is_best_seller=bool(r.get("is_best_seller")),
                short_description=(r.get("description") or "").strip().split("\n")[0][:200],
            )
            image = self.copy_file(r.get("image"))
            if image:
                p.image.name = image
            p.save()
            if r.get("created_at"):
                Product.objects.filter(pk=p.pk).update(created_at=when(r["created_at"]))
            for i, v in enumerate(old_variants.get(r["id"], [])):
                variants[v["id"]] = Variant.objects.create(product=p, label=v["size"][:60], price=dec(v["price"]),
                                                           stock=v.get("stock") or 0, sort_order=i)
            if not old_variants.get(r["id"]):
                p.default_variant()
            else:
                # Keep the product's own price/stock in step with its first size
                first = p.variants.order_by("sort_order").first()
                Product.objects.filter(pk=p.pk).update(size_label=first.label)
            products[r["id"]] = p
            created += 1
        self.say("Products", created, len(products) - created)
        return products, variants

    def import_orders(self, users, variants):
        created = skipped = 0
        items = {}
        for it in self.rows("store_orderitem"):
            items.setdefault(it["order_id"], []).append(it)
        for r in self.rows("store_order"):
            number = r.get("order_number") or f"DCP-{r['id']:05d}"
            clash = Order.objects.filter(number=number).first()
            if clash and clash.notes == IMPORTED_NOTE:
                skipped += 1
                continue
            if clash:  # a new-site order already uses this number
                number = f"{number}-OLD"
                if Order.objects.filter(number=number).exists():
                    skipped += 1
                    continue
            user = users.get(r.get("user_id"))
            method = (r.get("payment_method") or "").lower()
            method = "airtel" if "airtel" in method else "cod" if ("cod" in method or "deliver" in method) else "mpesa"
            subtotal = dec(r.get("total_price"))
            discount = dec(r.get("discount"))
            o = Order(
                number=number, user=user, full_name=r.get("name") or (user.get_full_name() if user else ""),
                email=user.email if user else "", phone=r.get("phone") or "", address=r.get("address") or "",
                city="", subtotal=subtotal, discount=discount, coupon_code=r.get("coupon_code") or "",
                # The old site added GST and charged no delivery; keep what the customer actually paid
                delivery_fee=Decimal("0"), total=dec(r.get("grand_total"), str(subtotal - discount)),
                payment_method=method,
                payment_reference=(r.get("mpesa_receipt_number") or r.get("utr_last6") or "")[:40],
                checkout_request_id=r.get("checkout_request_id") or None,
                merchant_request_id=r.get("merchant_request_id") or "",
                mpesa_result_desc=(r.get("mpesa_result_desc") or "")[:255],
                courier=r.get("courier") or "", tracking_number=r.get("tracking_number") or "",
                status=STATUS.get(r.get("status"), "PROCESSING"),
                cancellation_reason=r.get("cancellation_reason") or "",
                stock_deducted=True,  # stock was already handled on the old site
                notes=IMPORTED_NOTE,
            )
            if r.get("payment_screenshot"):
                o.payment_proof.name = self.copy_file(r["payment_screenshot"])
            if o.checkout_request_id and Order.objects.filter(checkout_request_id=o.checkout_request_id).exists():
                o.checkout_request_id = None
            o.save()
            stamps = {k: when(r.get(k)) for k in ("created_at", "paid_at", "shipped_at", "delivered_at", "cancelled_at")}
            Order.objects.filter(pk=o.pk).update(**{k: v for k, v in stamps.items()
                                                     if v and hasattr(Order, k)})
            for it in items.get(r["id"], []):
                v = variants.get(it.get("variant_id"))
                OrderItem.objects.create(order=o, variant=v, product_name=v.product.name if v else "Old product",
                                         variant_label=v.label if v else "", unit_price=dec(it.get("price")),
                                         quantity=it.get("quantity") or 1)
            created += 1
        self.say("Orders", created, skipped)

    def import_reviews(self, users, products):
        created = 0
        for r in self.rows("store_review"):
            user, product = users.get(r.get("user_id")), products.get(r.get("product_id"))
            if not user or not product or Review.objects.filter(user=user, product=product).exists():
                continue
            Review.objects.create(user=user, product=product, rating=max(1, min(5, int(r.get("rating") or 5))),
                                  title=r.get("title") or "", comment=r.get("comment") or "",
                                  is_verified_buyer=bool(r.get("is_verified_buyer")),
                                  is_approved=bool(r.get("is_approved", 1)))
            created += 1
        self.say("Reviews", created)

    def import_coupons(self):
        created = 0
        for r in self.rows("store_coupon"):
            if Coupon.objects.filter(code__iexact=r["code"]).exists():
                continue
            Coupon.objects.create(code=r["code"].upper(), value=dec(r.get("value")),
                                  discount_type="fixed" if r.get("discount_type") == "fixed" else "percent",
                                  min_order_amount=dec(r.get("min_order_amount")), max_uses=r.get("max_uses"),
                                  used_count=r.get("used_count") or 0, valid_from=when(r.get("valid_from")),
                                  valid_until=when(r.get("valid_until")), is_active=bool(r.get("is_active", 1)))
            created += 1
        self.say("Coupons", created)

    def import_posts(self, users):
        created = 0
        for r in self.rows("store_blogpost"):
            slug = r.get("slug") or slugify(r["title"])
            if Post.objects.filter(slug=slug).exists():
                continue
            post = Post(title=r["title"], slug=slug, body=r.get("content") or "", excerpt=(r.get("excerpt") or "")[:300],
                        topic=TOPIC.get(r.get("category"), "wellness"), author=users.get(r.get("author_id")),
                        is_published=(r.get("status", "published") == "published"), views=r.get("views") or 0)
            cover = self.copy_file(r.get("featured_image"))
            if cover:
                post.cover.name = cover
            post.save()
            if r.get("published_at") or r.get("created_at"):
                Post.objects.filter(pk=post.pk).update(published_at=when(r.get("published_at") or r.get("created_at")))
            created += 1
        self.say("Blog posts", created)

    def import_newsletter(self):
        created = 0
        for r in self.rows("store_newslettersubscriber"):
            _, made = NewsletterSubscriber.objects.get_or_create(email=r["email"].lower(),
                                                                 defaults={"is_active": bool(r.get("is_active", 1))})
            created += made
        self.say("Newsletter subscribers", created)
