# store/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify

# =============================================
# CATEGORY MODEL
# =============================================
# store/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = 'Categories'


class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    
    # ✅ THIS FIELD MUST EXIST
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='products'
    )
    
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    compare_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
    def get_discount_percentage(self):
        if self.compare_price and self.compare_price > self.price:
            return int(((self.compare_price - self.price) / self.compare_price) * 100)
        return 0

# =============================================
# PRODUCT VARIANT MODEL
# =============================================

class ProductVariant(models.Model):
    SIZE_CHOICES = [
        ('S', 'Small'),
        ('M', 'Medium'),
        ('L', 'Large'),
    ]

    product = models.ForeignKey(Product, related_name="variants", on_delete=models.CASCADE)
    size = models.CharField(max_length=1, choices=SIZE_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} - {self.size}"


# =============================================
# ORDER MODEL
# =============================================

class Order(models.Model):
    STATUS_CHOICES = (
        ("PAYMENT_PENDING", "Payment Pending"),
        ("PAID", "Paid"),
        ("PLACED", "Placed"),
        ("PROCESSING", "Processing"),
        ("SHIPPED", "Shipped"),
        ("DELIVERED", "Delivered"),
        ("CANCELLED", "Cancelled"),
        ("FAILED", "Failed"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # Customer details
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=15)
    address = models.TextField()

    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    gst = models.DecimalField(max_digits=10, decimal_places=2)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2)

    # Payment Proof Fields
    utr_last6 = models.CharField(max_length=6, blank=True, null=True)
    payment_screenshot = models.ImageField(upload_to='payment_proofs/', blank=True, null=True)

    # M-PESA FIELDS
    checkout_request_id = models.CharField(max_length=100, blank=True, null=True)
    merchant_request_id = models.CharField(max_length=100, blank=True, null=True)
    mpesa_receipt_number = models.CharField(max_length=50, blank=True, null=True)
    mpesa_result_code = models.CharField(max_length=10, blank=True, null=True)
    mpesa_result_desc = models.TextField(blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PAYMENT_PENDING"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} - {self.user.username}"


# =============================================
# ORDER ITEM MODEL
# =============================================

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    variant = models.ForeignKey("ProductVariant", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.variant.product.name} ({self.variant.size}) x{self.quantity}"



        # store/models.py
class BlogPost(models.Model):
    """Blog posts for content marketing"""
    
    CATEGORY_CHOICES = (
        ('supplements', 'Supplements'),
        ('nutrition', 'Nutrition'),
        ('wellness', 'Wellness'),
        ('lifestyle', 'Lifestyle'),
        ('product', 'Product Updates'),
        ('tips', 'Tips & Tricks'),
        ('research', 'Research'),
    )
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    content = models.TextField()
    excerpt = models.TextField(blank=True, help_text="Short summary of the post")
    
    featured_image = models.ImageField(upload_to='blog/', blank=True, null=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='supplements')
    
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_posts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(blank=True, null=True)
    
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    is_featured = models.BooleanField(default=False)
    views = models.PositiveIntegerField(default=0)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.title
    
    def get_category_display(self):
        category_map = {
            'supplements': 'Supplements',
            'nutrition': 'Nutrition',
            'wellness': 'Wellness',
            'lifestyle': 'Lifestyle',
            'product': 'Product Updates',
            'tips': 'Tips & Tricks',
            'research': 'Research',
        }
        return category_map.get(self.category, self.category)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Blog Posts'