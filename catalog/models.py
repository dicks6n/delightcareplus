from decimal import Decimal

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count, Q
from django.urls import reverse
from django.utils.text import slugify


def unique_slug(instance, value, field="slug"):
    """slugify(value), adding -2, -3… until it's unique for this model."""
    base = slugify(value)[:180] or "item"
    slug, n = base, 2
    model = type(instance)
    while model.objects.filter(**{field: slug}).exclude(pk=instance.pk).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


# =============================================
# BRAND
# =============================================
class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    country = models.CharField(max_length=60, blank=True, help_text="e.g. France")
    country_code = models.CharField(max_length=2, blank=True, help_text="Two letters for the flag, e.g. FR, JP, US")
    tagline = models.CharField(max_length=160, blank=True)
    story = models.TextField(blank=True, help_text="Shown on the brand page")
    logo = models.ImageField(upload_to="brands/", blank=True, null=True)
    banner = models.ImageField(upload_to="brands/", blank=True, null=True)
    accent_color = models.CharField(max_length=7, default="#90bc79", help_text="Hex colour used on the brand page")
    is_featured = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        self.country_code = self.country_code.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:brand", args=[self.slug])

    @property
    def flag(self):
        """Emoji flag from the 2-letter country code."""
        if len(self.country_code) != 2:
            return ""
        return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in self.country_code)


# =============================================
# DEPARTMENT → CATEGORY
# =============================================
class Department(models.Model):
    """Top-level shelf: Supplements, Skincare, Tea …"""
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    icon = models.CharField(max_length=60, default="fa-solid fa-leaf", help_text="Font Awesome class")
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="departments/", blank=True, null=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:department", args=[self.slug])


class Category(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    icon = models.CharField(max_length=60, default="fa-solid fa-leaf")
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="categories/", blank=True, null=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["department__sort_order", "sort_order", "name"]
        verbose_name_plural = "Categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.department.name} › {self.name}"

    def get_absolute_url(self):
        return reverse("catalog:category", args=[self.slug])


# =============================================
# CONCERN (shop by need: Acne, Sleep, Immunity…)
# =============================================
class Concern(models.Model):
    GROUPS = (("skin", "Skin"), ("body", "Body & Health"), ("lifestyle", "Lifestyle"))
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=80, unique=True, blank=True)
    group = models.CharField(max_length=10, choices=GROUPS, default="skin")
    icon = models.CharField(max_length=60, default="fa-solid fa-circle-check")
    emoji = models.CharField(max_length=8, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["group", "sort_order", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:concern", args=[self.slug])


# =============================================
# PRODUCT
# =============================================
class ProductQuerySet(models.QuerySet):
    def live(self):
        return self.filter(is_active=True)

    def with_ratings(self):
        return self.annotate(
            avg_rating=Avg("reviews__rating", filter=Q(reviews__is_approved=True)),
            review_count=Count("reviews", filter=Q(reviews__is_approved=True), distinct=True),
        )


class Product(models.Model):
    FORM_CHOICES = (
        ("capsules", "Capsules"),
        ("tablets", "Tablets"),
        ("powder", "Powder"),
        ("liquid", "Liquid / Drink"),
        ("gummies", "Gummies"),
        ("serum", "Serum"),
        ("mask", "Face Mask"),
        ("cream", "Cream"),
        ("cleanser", "Cleanser"),
        ("toner", "Toner / Essence"),
        ("tea", "Tea"),
        ("other", "Other"),
    )

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    form = models.CharField(max_length=20, choices=FORM_CHOICES, default="other")
    sku = models.CharField(max_length=40, blank=True)

    short_description = models.CharField(max_length=220, blank=True, help_text="One line shown on product cards")
    description = models.TextField(blank=True)
    benefits = models.TextField(blank=True, help_text="One benefit per line")
    ingredients = models.TextField(blank=True)
    how_to_use = models.TextField(blank=True)
    skin_type = models.CharField(max_length=120, blank=True, help_text="e.g. All skin types, Oily, Dry")
    size_label = models.CharField(max_length=40, blank=True, help_text="e.g. 30ml, 60 capsules, 20 tea bags")
    weight_grams = models.PositiveIntegerField(default=0, help_text="Packed weight, used for delivery pricing. 0 = typical weight for the product type")

    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                        help_text="Old price — shows a sale badge when higher than price")
    stock = models.PositiveIntegerField(default=50)

    image = models.ImageField(upload_to="products/", blank=True, null=True, help_text="Main photo")

    # ⭐ Shop-by-concern + routine finder
    concerns = models.ManyToManyField(Concern, blank=True, related_name="products")
    routine_step = models.CharField(max_length=12, blank=True, choices=(
        ("cleanse", "1 · Cleanse"), ("tone", "2 · Tone / Essence"), ("treat", "3 · Serum / Treat"),
        ("mask", "Weekly mask"), ("moisturise", "4 · Moisturise"), ("protect", "5 · Protect (SPF)"),
        ("supplement", "Daily supplement"), ("tea", "Daily tea"),
    ), help_text="Where this fits in a routine (used by the Routine Finder)")

    # ⭐ How long one pack lasts → "Lasts 30 days" + refill reminders
    servings_per_pack = models.PositiveIntegerField(default=0, help_text="e.g. 60 capsules, 20 tea bags, 30 doses. 0 = not shown")
    daily_servings = models.PositiveIntegerField(default=1, help_text="How many per day, e.g. 2 capsules")

    # ⭐ Trust badges
    is_vegan = models.BooleanField(default=False)
    is_halal = models.BooleanField(default=False)
    is_cruelty_free = models.BooleanField(default=False)
    is_fragrance_free = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_best_seller = models.BooleanField(default=False)
    is_new = models.BooleanField(default=True)
    is_sample = models.BooleanField(default=False, help_text="Demo product created by the setup script — replace before launch")

    views = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, f"{self.brand.name if self.brand else ''} {self.name}")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:product", args=[self.slug])

    @property
    def discount_percent(self):
        if self.compare_price and self.compare_price > self.price:
            return int((self.compare_price - self.price) * 100 / self.compare_price)
        return 0

    TYPICAL_WEIGHT = {"capsules": 200, "tablets": 200, "powder": 400, "liquid": 600, "gummies": 250,
                      "serum": 150, "mask": 60, "cream": 250, "cleanser": 220, "toner": 250, "tea": 180, "other": 300}

    @property
    def shipping_weight(self):
        """Grams used for delivery pricing."""
        return self.weight_grams or self.TYPICAL_WEIGHT.get(self.form, 300)

    @property
    def days_supply(self):
        if self.servings_per_pack and self.daily_servings:
            return self.servings_per_pack // self.daily_servings
        return 0

    @property
    def badges(self):
        out = []
        if self.is_vegan:
            out.append(("fa-solid fa-seedling", "Vegan"))
        if self.is_halal:
            out.append(("fa-solid fa-moon", "Halal"))
        if self.is_cruelty_free:
            out.append(("fa-solid fa-paw", "Cruelty-free"))
        if self.is_fragrance_free:
            out.append(("fa-solid fa-wind", "Fragrance-free"))
        return out

    def latest_batch(self):
        return self.batches.order_by("-expiry_date").first()

    @property
    def savings(self):
        return (self.compare_price - self.price) if self.discount_percent else 0

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def low_stock(self):
        return 0 < self.stock <= 5

    @property
    def benefit_list(self):
        return [b.strip(" -•\t") for b in self.benefits.splitlines() if b.strip()]

    def rating_summary(self):
        avg = getattr(self, "avg_rating", None)
        count = getattr(self, "review_count", None)
        if count is None:
            agg = self.reviews.filter(is_approved=True).aggregate(avg=Avg("rating"), count=Count("id"))
            avg, count = agg["avg"], agg["count"]
        return {"avg": round(avg or 0, 1), "count": count or 0}

    def default_variant(self):
        """The variant used when the shopper doesn't choose one (created on demand)."""
        variant = self.variants.order_by("sort_order", "id").first()
        if not variant:
            variant = self.variants.create(label=self.size_label or "Standard", price=self.price, stock=self.stock)
        return variant

    def showcase_image(self):
        """A clean photo for the home hero and slides: the first gallery photo (the studio shot
        for generated products), else the main photo."""
        extra = list(self.images.all())[:1]  # uses prefetch_related("images") when the list view has it
        return extra[0].image if extra else self.image

    def gallery(self):
        """Main image first, then extra photos."""
        images = []
        if self.image:
            images.append(self.image)
        images += [img.image for img in self.images.all()]
        return images


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/gallery/")
    alt = models.CharField(max_length=160, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"Photo of {self.product.name}"


class Variant(models.Model):
    """A buyable option — size, pack or shade. Every cart line points at a Variant."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    label = models.CharField(max_length=60, help_text="e.g. 30ml, 60 caps, Pack of 5")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.PositiveIntegerField(default=50)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.product.name} — {self.label}"


# =============================================
# BATCH — authenticity & expiry
# =============================================
class Batch(models.Model):
    """Every stock delivery you receive. Customers verify the code printed on their box."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="batches")
    code = models.CharField(max_length=40, unique=True, help_text="Batch / lot number printed on the pack")
    manufactured_on = models.DateField(null=True, blank=True)
    expiry_date = models.DateField()
    imported_on = models.DateField(null=True, blank=True)
    supplier = models.CharField(max_length=120, blank=True, help_text="Who you bought it from (not shown publicly)")
    quantity = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-expiry_date"]
        verbose_name_plural = "Batches"

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} — {self.product.name}"

    @property
    def is_expired(self):
        from django.utils import timezone
        return self.expiry_date < timezone.localdate()


# =============================================
# BACK-IN-STOCK ALERT
# =============================================
class StockAlert(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock_alerts")
    email = models.EmailField()
    notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("product", "email")


# =============================================
# REVIEW
# =============================================
class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=120, blank=True)
    comment = models.TextField(blank=True)
    is_verified_buyer = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("product", "user")

    def __str__(self):
        return f"{self.product.name} — {self.rating}★ by {self.user.username}"


def money(value):
    return Decimal(value).quantize(Decimal("0.01"))
