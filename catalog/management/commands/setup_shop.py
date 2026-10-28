"""
Set up a fresh Delight Care Plus shop:

    python manage.py setup_shop            # structure + sample products with generated photos
    python manage.py setup_shop --no-samples

Safe to run again — existing rows are kept, missing ones are added.
Sample products are flagged is_sample=True so you can remove them in one click
(Seller Center → Products → Remove samples) once your real products are in.
"""
import hashlib
import io
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from blog.models import Post
from cart.models import Coupon, DeliveryZone
from catalog.catalog_data import PRODUCTS, REPLACED_SAMPLES, SAFETY
from catalog.imaging import render_banner, render_promo
from catalog.photos import auto_infographic, make_photos
from catalog.models import Brand, Category, Concern, Department, Product
from core.models import Banner, SiteSettings

DEPARTMENTS = [
    ("Supplements", "fa-solid fa-capsules", "Daily supplements for every part of your body — from liver and heart to skin, hair and energy.", [
        ("Collagen", "fa-solid fa-dna"), ("Skin, Hair & Nails", "fa-solid fa-spa"), ("Immune Support", "fa-solid fa-shield-virus"),
        ("Energy & Vitality", "fa-solid fa-bolt"), ("Liver Health", "fa-solid fa-leaf"),
        ("Kidney Health", "fa-solid fa-droplet"), ("Lung Health", "fa-solid fa-lungs"),
        ("Heart Health", "fa-solid fa-heart-pulse"), ("Digestive Health", "fa-solid fa-seedling"),
        ("Brain & Focus", "fa-solid fa-brain"), ("Joint & Bone", "fa-solid fa-bone"),
        ("Weight Management", "fa-solid fa-scale-balanced"), ("Women's Health", "fa-solid fa-venus"),
        ("Men's Health", "fa-solid fa-mars"), ("Sleep & Stress", "fa-solid fa-moon"),
    ]),
    ("Skincare", "fa-solid fa-spa", "Serums, face masks and facial care from our France and Japan collections.", [
        ("Face Masks", "fa-solid fa-masks-theater"), ("Serums", "fa-solid fa-eye-dropper"),
        ("Cleansers", "fa-solid fa-soap"), ("Toners & Essences", "fa-solid fa-bottle-droplet"),
        ("Moisturisers", "fa-solid fa-jar"), ("Eye Care", "fa-regular fa-eye"), ("Sun Care", "fa-solid fa-sun"),
    ]),
    ("Tea", "fa-solid fa-mug-hot", "Herbal and wellness teas for detox, digestion, beauty and better sleep.", [
        ("Detox Tea", "fa-solid fa-leaf"), ("Slimming Tea", "fa-solid fa-scale-balanced"),
        ("Herbal Wellness Tea", "fa-solid fa-mug-saucer"), ("Beauty Tea", "fa-solid fa-wand-magic-sparkles"),
        ("Sleep & Calm Tea", "fa-solid fa-moon"),
    ]),
]

CONCERNS = [
    ("Acne & breakouts", "skin", "😣"), ("Dark spots", "skin", "🌗"), ("Dull skin", "skin", "✨"),
    ("Dryness", "skin", "💧"), ("Fine lines", "skin", "⏳"), ("Oily skin & pores", "skin", "🫧"),
    ("Sensitive skin", "skin", "🌸"),
    ("Immunity", "body", "🛡️"), ("Energy", "body", "⚡"), ("Digestion", "body", "🌿"),
    ("Liver detox", "body", "🍃"), ("Heart health", "body", "❤️"), ("Joints", "body", "🦴"),
    ("Focus & memory", "body", "🧠"), ("Hair & nails", "body", "💅"),
    ("Sleep", "lifestyle", "🌙"), ("Weight", "lifestyle", "⚖️"), ("Stress", "lifestyle", "🧘"),
]

BRANDS = [
    # Shown to customers only as collections (France / Japan / USA): supplier brand names stay off the site.
    ("France", "France", "FR", "#1e2a4a", "Skincare and beauty-from-within supplements.",
     "Our France collection: gentle skincare, plus collagen, glutathione and vitamin supplements that support beauty from within."),
    ("Japan", "Japan", "JP", "#e98c97", "Face masks, essences and serums.",
     "Our Japan collection: light layers, hydration first, and a mask whenever your skin needs it."),
    ("USA", "USA", "US", "#2f6b3f", "Daily wellness supplements and teas.",
     "Our USA collection: easy capsules, powders and teas for energy, immunity, digestion and more."),
]

# Brand names used by earlier versions of this setup, stored as fingerprints (first 16 hex characters of the
# SHA-256 of the lower-cased name) so the supplier names are not written in the code.
LEGACY_BRANDS = {"a37ed7f0ea66c6fc": "France", "9fe91541ca3734cd": "Japan", "53cd0f4db2e24f6b": "USA"}

ZONES = [
    ("Nairobi CBD & nearby", 100, 200, 50, "Same / next day",
     ["Nairobi CBD", "Upper Hill", "Westlands", "Kilimani", "Kileleshwa", "Lavington", "Parklands", "Ngara", "South B", "South C",
      "Hurlingham", "Gigiri"]),
    ("Greater Nairobi", 150, 300, 50, "1–2 days",
     ["Kasarani", "Roysambu", "Kahawa", "Embakasi", "Donholm", "Umoja", "Karen", "Lang'ata", "Rongai", "Kitengela", "Syokimau",
      "Athi River", "Ngong", "Ruaka", "Kikuyu", "Kiambu", "Ruiru", "Juja", "Thika", "Limuru"]),
    ("Major towns", 250, 450, 80, "2–3 days",
     ["Mombasa", "Kisumu", "Nakuru", "Eldoret", "Nyeri", "Machakos", "Meru", "Naivasha", "Kericho", "Kakamega", "Embu",
      "Nanyuki", "Malindi", "Kisii", "Kitale", "Bungoma", "Narok", "Voi", "Kilifi", "Nyahururu"]),
    ("Rest of Kenya", 350, 600, 100, "3–5 days",
     ["Garissa", "Lodwar", "Marsabit", "Wajir", "Mandera", "Lamu", "Isiolo", "Kitui", "Homa Bay", "Migori", "Busia", "Siaya",
      "Kapenguria", "Maralal", "Moyale", "Other town"]),
]

# (name, brand, category, form, size, price, compare, step, servings, per_day, concerns, short, benefits, how_to_use, skin)
SAMPLES = [
    # ---- France collection
    ("Vitamin C Brightening Serum", "France", "Serums", "serum", "30ml", 3200, 3900, "treat", 0, 1,
     ["Dark spots", "Dull skin"], "A light vitamin C serum for a brighter, more even-looking glow.",
     "Brighter-looking skin\nHelps even out tone\nLightweight, absorbs fast", "Apply 3–4 drops to clean skin every morning, before moisturiser and sunscreen.", "All skin types"),
    ("Gentle Micellar Cleansing Water", "France", "Cleansers", "cleanser", "400ml", 1800, None, "cleanse", 0, 1,
     ["Sensitive skin"], "No-rinse micellar cleansing water that lifts make-up and dirt.",
     "Removes make-up and sunscreen\nNo rinsing needed\nGentle on sensitive skin", "Soak a cotton pad and sweep over face and eyes. No need to rinse.", "All skin types, including sensitive"),
    ("Hyaluronic Hydra Cream", "France", "Moisturisers", "cream", "50ml", 2900, None, "moisturise", 0, 1,
     ["Dryness", "Fine lines"], "Rich-but-light daily cream with hyaluronic acid for plump, soft skin.",
     "All-day hydration\nSofter, smoother feel\nWorks under make-up", "Massage into face and neck morning and night.", "Normal, dry, combination"),
    ("Thermal Water Soothing Toner", "France", "Toners & Essences", "toner", "200ml", 1600, None, "tone", 0, 1,
     ["Sensitive skin", "Dryness"], "A calming toner that preps skin and refreshes it during the day.",
     "Soothes and refreshes\nPreps skin for serum\nAlcohol-free", "Pat into skin after cleansing, or mist through the day.", "Sensitive, dry"),
    ("Mineral Sun Fluid SPF 50", "France", "Sun Care", "cleanser", "50ml", 2400, None, "protect", 0, 1,
     ["Dark spots", "Sensitive skin"], "Invisible mineral sunscreen made for daily wear in strong sun.",
     "High protection\nNo white cast on most skin tones\nLight, non-greasy", "Apply generously as the last step every morning. Reapply every 2 hours outdoors.", "All skin types"),
    ("Collagen Beauty Capsules", "France", "Skin, Hair & Nails", "capsules", "60 capsules", 3500, 4200, "supplement", 60, 2,
     ["Fine lines", "Hair & nails", "Dull skin"], "Daily marine collagen with vitamin C to support skin from within.",
     "Supports skin elasticity\nStronger-feeling nails and hair\nWith vitamin C", "Take 2 capsules a day with water, ideally in the morning.", ""),
    ("Liver Detox Milk Thistle", "France", "Liver Health", "capsules", "60 capsules", 2600, None, "supplement", 60, 2,
     ["Liver detox", "Digestion"], "Milk thistle and artichoke to support normal liver function.",
     "Supports liver health\nWith milk thistle & artichoke\nGentle daily formula", "Take 2 capsules a day with a meal.", ""),
    # ---- Japan collection
    ("Sakura Hyaluronic Sheet Mask", "Japan", "Face Masks", "mask", "5 masks", 1500, 1900, "mask", 0, 1,
     ["Dryness", "Dull skin"], "Soft cotton sheet masks soaked in a cherry-blossom hydrating essence.",
     "Instant hydration boost\nSofter, glowing skin in 15 minutes\nGentle on sensitive skin", "After cleansing, apply the mask for 15–20 minutes. Pat in the remaining essence. Use 2–3× a week.", "All skin types"),
    ("Rice Ceramide Night Cream", "Japan", "Moisturisers", "cream", "50g", 2700, None, "moisturise", 0, 1,
     ["Dryness", "Sensitive skin"], "A rice and ceramide cream for overnight comfort.",
     "Strengthens the skin barrier\nDeep overnight moisture\nNon-sticky", "Apply as the last step of your evening routine.", "Dry, normal, sensitive"),
    ("Green Tea Pore Clay Mask", "Japan", "Face Masks", "mask", "100g", 1900, None, "mask", 0, 1,
     ["Oily skin & pores", "Acne & breakouts"], "A green tea clay mask that absorbs excess oil and refines pores.",
     "Absorbs excess oil\nHelps reduce the look of pores\nFresh, clean feel", "Apply a thin layer to clean skin, leave 10 minutes, rinse with warm water. Use 1–2× a week.", "Oily, combination"),
    ("Hydrating Rice Essence Toner", "Japan", "Toners & Essences", "toner", "150ml", 2100, None, "tone", 0, 1,
     ["Dull skin", "Dryness"], "A milky rice-water essence for a soft, dewy glow.",
     "Dewy, glass-skin glow\nLayers well with serums\nHydrates without heaviness", "Pat 2–3 drops into skin after cleansing, morning and night.", "All skin types"),
    ("Niacinamide Clear Skin Serum", "Japan", "Serums", "serum", "30ml", 2800, 3300, "treat", 0, 1,
     ["Acne & breakouts", "Oily skin & pores", "Dark spots"], "10% niacinamide serum to balance oil and smooth texture.",
     "Balances oily skin\nSmoother-looking texture\nHelps fade marks", "Apply 3 drops after toner, morning and/or evening.", "Oily, combination, acne-prone"),
    ("Gentle Foaming Face Wash", "Japan", "Cleansers", "cleanser", "120ml", 1400, None, "cleanse", 0, 1,
     ["Acne & breakouts", "Oily skin & pores"], "A soft-foam cleanser that cleans deeply without the tight feeling.",
     "Deep yet gentle clean\nLow-pH formula\nNo tight feeling", "Lather with water, massage for 30 seconds, rinse. Morning and night.", "All skin types"),
    ("Brightening Eye Patches", "Japan", "Eye Care", "mask", "60 patches", 2200, None, "", 0, 1,
     ["Fine lines", "Dull skin"], "Cooling hydrogel eye patches for tired, puffy-looking eyes.",
     "Cooling and refreshing\nHelps tired-looking eyes\n30 pairs", "Place under eyes for 15–20 minutes, then pat in the essence.", "All skin types"),
    ("Sakura Beauty Tea", "Japan", "Beauty Tea", "tea", "20 tea bags", 1300, None, "tea", 20, 1,
     ["Dull skin", "Stress"], "A floral green tea blend with sakura and rose for a calm daily ritual.",
     "Floral, caffeine-light blend\nRich in antioxidants\nA calming daily ritual", "Steep one bag in hot (not boiling) water for 3 minutes.", ""),
    # ---- USA collection
    ("Immune Defense Vitamin C + Zinc", "USA", "Immune Support", "tablets", "90 tablets", 1900, 2400, "supplement", 90, 1,
     ["Immunity", "Energy"], "Daily vitamin C, zinc and vitamin D for normal immune function.",
     "Supports normal immunity\nWith zinc & vitamin D\nOne tablet a day", "Take 1 tablet a day with food.", ""),
    ("Multivitamin Energy Gummies", "USA", "Energy & Vitality", "gummies", "60 gummies", 2300, None, "supplement", 60, 2,
     ["Energy", "Immunity"], "Tasty daily multivitamin gummies with B vitamins for energy.",
     "B vitamins for energy\n13 vitamins & minerals\nNatural berry flavour", "Chew 2 gummies a day.", ""),
    ("Omega-3 Fish Oil 1000mg", "USA", "Heart Health", "capsules", "120 softgels", 2800, None, "supplement", 120, 2,
     ["Heart health", "Focus & memory", "Joints"], "High-strength omega-3 for heart, brain and joints.",
     "EPA & DHA omega-3\nSupports heart & brain health\nNo fishy aftertaste", "Take 2 softgels a day with a meal.", ""),
    ("Biotin Hair & Nail Formula", "USA", "Skin, Hair & Nails", "capsules", "60 capsules", 2100, None, "supplement", 60, 1,
     ["Hair & nails"], "Biotin with zinc and selenium for normal hair and nails.",
     "Supports normal hair & nails\nWith zinc & selenium\nOne a day", "Take 1 capsule a day with water.", ""),
    ("Probiotic Gut Balance", "USA", "Digestive Health", "capsules", "30 capsules", 2600, 3100, "supplement", 30, 1,
     ["Digestion", "Immunity"], "Multi-strain probiotic for everyday digestive comfort.",
     "Multi-strain formula\nSupports digestive comfort\nShelf-stable", "Take 1 capsule a day, preferably in the morning.", ""),
    ("Glucosamine Joint Support", "USA", "Joint & Bone", "tablets", "90 tablets", 2900, None, "supplement", 90, 3,
     ["Joints"], "Glucosamine, chondroitin and MSM for active joints.",
     "Supports joint comfort\nGlucosamine + chondroitin + MSM\nFor active lifestyles", "Take 3 tablets a day with food.", ""),
    ("Magnesium Sleep & Calm", "USA", "Sleep & Stress", "capsules", "60 capsules", 1800, None, "supplement", 60, 2,
     ["Sleep", "Stress"], "Magnesium glycinate with chamomile for evening relaxation.",
     "Gentle magnesium glycinate\nHelps you unwind\nNon-habit forming", "Take 2 capsules 30–60 minutes before bed.", ""),
    ("Detox Slim Herbal Tea", "USA", "Detox Tea", "tea", "28 tea bags", 1500, 1800, "tea", 28, 1,
     ["Liver detox", "Digestion", "Weight"], "A refreshing herbal blend with green tea and ginger.",
     "Light, refreshing taste\nWith green tea & ginger\nPart of a balanced routine", "Steep 1 bag in hot water for 4–5 minutes. Enjoy once a day.", ""),
    ("Chamomile Sleep Tea", "USA", "Sleep & Calm Tea", "tea", "20 tea bags", 1200, None, "tea", 20, 1,
     ["Sleep", "Stress"], "Caffeine-free chamomile, lemon balm and lavender for calm evenings.",
     "Caffeine-free\nCalming evening ritual\nSoft floral taste", "Steep 1 bag for 5 minutes, 30 minutes before bed.", ""),
    ("Plant Protein Shake Vanilla", "USA", "Weight Management", "powder", "500g", 3400, None, "supplement", 20, 1,
     ["Weight", "Energy"], "Smooth pea & rice protein shake with 20g protein per serving.",
     "20g plant protein\nKeeps you full for longer\nDairy-free", "Mix 1 scoop with 250ml water or milk.", ""),
]

POSTS = [
    ("How to layer your skincare (the right order)", "skincare",
     "Cleanse, tone, treat, moisturise, protect — the simple order that makes every product work better.",
     "Using great products in the wrong order wastes them. The rule of thumb is thinnest to thickest.\n\n"
     "1. Cleanse — remove dirt, oil and sunscreen.\n2. Tone or essence — prep and hydrate.\n3. Serum — your targeted treatment "
     "(vitamin C in the morning, niacinamide or retinol-style serums at night).\n4. Moisturise — seal everything in.\n5. Sunscreen "
     "every morning — the most important anti-ageing step in Kenya's strong sun.\n\nAdd a sheet mask 2–3 times a week after "
     "toning. Not sure what fits your skin? Try our Routine Finder."),
    ("Supplements 101: how to choose what you actually need", "supplements",
     "Start with your goal, check the dose, and give it time — a simple guide to daily supplements.",
     "Supplements work best when they fill a real gap. Start with one goal — energy, immunity, skin, joints or sleep — and choose "
     "one product for it.\n\nLook at the daily dose and how long one pack lasts. Most supplements need 6–8 weeks of daily use "
     "before you notice a difference, so consistency matters more than the brand.\n\nIf you're pregnant, breastfeeding, have a "
     "medical condition or take medication, check with your doctor first."),
]


class Command(BaseCommand):
    help = "Create departments, categories, brands, delivery zones and (optionally) sample products with photos."

    def add_arguments(self, parser):
        parser.add_argument("--no-samples", action="store_true", help="Skip sample products")

    def handle(self, *args, **opts):
        SiteSettings.load()
        self._rename_supplier_brands()
        self._structure()
        self._catalog()
        if not opts["no_samples"]:
            self._samples()
        self._banners()
        self.stdout.write(self.style.SUCCESS("✅ Shop is ready. Create your admin login with: python manage.py createsuperuser"))

    def _structure(self):
        for i, (name, icon, desc, cats) in enumerate(DEPARTMENTS):
            dept, _ = Department.objects.get_or_create(name=name, defaults={"icon": icon, "description": desc, "sort_order": i})
            for j, (cname, cicon) in enumerate(cats):
                Category.objects.get_or_create(name=cname, department=dept, defaults={"icon": cicon, "sort_order": j})
        for i, (name, group, emoji) in enumerate(CONCERNS):
            Concern.objects.get_or_create(name=name, defaults={"group": group, "emoji": emoji, "sort_order": i})
        for i, (name, country, code, color, tagline, story) in enumerate(BRANDS):
            b, created = Brand.objects.get_or_create(name=name, defaults={
                "country": country, "country_code": code, "accent_color": color, "tagline": tagline,
                "story": story, "sort_order": i})
            if not b.banner:
                buf = io.BytesIO()
                render_banner(name, tagline, code, text=False).save(buf, "JPEG", quality=86, optimize=True)
                b.banner.save(f"{b.slug}-banner.jpg", ContentFile(buf.getvalue()), save=True)
        for i, (name, pickup, home, extra, days, towns) in enumerate(ZONES):
            DeliveryZone.objects.get_or_create(name=name, defaults={
                "towns": "\n".join(towns), "pickup_fee": pickup, "home_fee": home, "extra_kg_fee": extra,
                "delivery_days": days, "sort_order": i})
        Coupon.objects.get_or_create(code="WELCOME10", defaults={
            "description": "10% off your first order", "discount_type": "percent", "value": 10, "min_order_amount": 2000})
        Coupon.objects.get_or_create(code="FREESHIP", defaults={
            "description": "Free delivery on orders over KES 3,000", "discount_type": "free_delivery", "min_order_amount": 3000})
        for title, topic, excerpt, body in POSTS:
            Post.objects.get_or_create(title=title, defaults={"topic": topic, "excerpt": excerpt, "body": body})
        self.stdout.write("• Departments, categories, concerns, brands, delivery zones, coupons and guides ready")

    def _samples(self):
        created = 0
        for (name, brand_name, cat_name, form, size, price, compare, step, servings, per_day, concerns,
             short, benefits, how, skin) in SAMPLES:
            brand = Brand.objects.get(name=brand_name)
            if name in REPLACED_SAMPLES or Product.objects.filter(name=name, brand=brand).exists():
                continue
            p = Product.objects.create(
                name=name, brand=brand, category=Category.objects.get(name=cat_name), form=form, size_label=size,
                price=Decimal(price), compare_price=Decimal(compare) if compare else None, stock=40,
                routine_step=step, servings_per_pack=servings, daily_servings=per_day,
                short_description=short, benefits=benefits, how_to_use=how, skin_type=skin,
                description=f"{short}\n\nThis is a sample product created by the setup script. Replace the name, photos and "
                            f"description with the real product details from Seller Center → Products.",
                is_best_seller=created % 4 == 0, is_featured=created % 3 == 0, is_sample=True,
                is_vegan=form in ("tea", "serum", "toner"), is_cruelty_free=brand.country_code in ("FR", "JP"),
            )
            p.concerns.set(Concern.objects.filter(name__in=concerns))
            self._photos(p, *auto_infographic(p))
            p.default_variant()
            created += 1
            self.stdout.write(f"  + {name}")
        self.stdout.write(f"• {created} sample products created (marked as samples)")

    def _banners(self):
        """One home-page slide per collection, built from its product photos (only for collections without one)."""
        from PIL import Image

        made = 0
        for i, brand in enumerate(Brand.objects.order_by("sort_order")):
            if Banner.objects.filter(link=brand.get_absolute_url()).exists():
                continue
            photos = []
            for p in brand.products.exclude(image="").order_by("-is_best_seller", "id")[:3]:
                with p.showcase_image().open("rb") as fh:
                    photos.append(Image.open(fh).convert("RGB"))
            buf = io.BytesIO()
            render_promo(brand.country_code, photos).save(buf, "JPEG", quality=86, optimize=True)
            banner = Banner(title=f"{brand.flag} {brand.name} collection", subtitle=brand.tagline, button_text=f"Shop {brand.name}",
                            link=brand.get_absolute_url(), sort_order=i)
            banner.image.save(f"slide-{brand.slug}.jpg", ContentFile(buf.getvalue()), save=True)
            made += 1
        if made:
            self.stdout.write(f"• {made} home slides created (edit in Seller Center → Home banners)")



    def _rename_supplier_brands(self):
        """Shops set up with an earlier version used the supplier brand names. Rename them to the
        France / Japan / USA collections everywhere a customer could see them: brand pages, product
        links, photo file names and home slides."""
        for brand in Brand.objects.all():
            new = LEGACY_BRANDS.get(hashlib.sha256(brand.name.lower().encode()).hexdigest()[:16])
            if not new or Brand.objects.filter(name=new).exists():
                continue
            old = brand.name
            old_slug = brand.slug
            brand.name, brand.slug = new, ""
            brand.save()
            for product in brand.products.all():
                if old_slug in product.slug:
                    product.slug = ""
                    product.save()
                if product.image and old_slug in product.image.name:
                    with product.image.open("rb") as fh:
                        data = fh.read()
                    stale = product.image.name
                    product.image.save(stale.split("/")[-1].replace(old_slug, brand.slug), ContentFile(data), save=True)
                    product.image.storage.delete(stale)
            for product in brand.products.filter(is_sample=True):
                product.images.all().delete()
                self._photos(product, *auto_infographic(product))
            for banner in Banner.objects.filter(title__contains=old):
                banner.image.delete(save=False)
                banner.delete()
            self.stdout.write(f"• Renamed brand {old} → {new}")

    def _catalog(self):
        """The real supplement line-up (catalog/catalog_data.py)."""
        created = 0
        for item in PRODUCTS:
            brand = Brand.objects.get(name=item["brand"])
            if Product.objects.filter(name=item["name"], brand=brand).exists():
                continue
            category = Category.objects.get(name=item["category"])
            description = item["short"]
            if item.get("warning"):
                description += "\n\n⚠️ " + item["warning"]
            description += "\n\n" + SAFETY
            p = Product.objects.create(
                name=item["name"], brand=brand, category=category, form=item["form"], size_label=item["size"],
                sku=item.get("sku", ""), price=Decimal(item["price"]), stock=30, routine_step="supplement",
                short_description=item["short"], description=description, benefits=item["benefits"],
                ingredients=item["ingredients"], how_to_use="Follow the directions on the label.",
                is_best_seller=item.get("best", False), is_featured=item.get("featured", False), is_new=item.get("new", False),
            )
            p.concerns.set(Concern.objects.filter(name__in=item["concerns"]))
            self._photos(p, item["callouts"], item["badges"], "Food supplement")
            p.default_variant()
            created += 1
            self.stdout.write(f"  + {p.name}")
        self.stdout.write(f"• {created} products from the supplement line-up added")

    def _photos(self, p, callouts, badges, kicker):
        make_photos(p, callouts, badges, kicker)
