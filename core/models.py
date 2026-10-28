from django.db import models


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=150, blank=True)
    message = models.TextField(max_length=3000)
    is_handled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name}: {self.subject or self.message[:40]}"


class Banner(models.Model):
    """Home page slider — edit in admin."""
    title = models.CharField(max_length=120)
    subtitle = models.CharField(max_length=220, blank=True)
    button_text = models.CharField(max_length=40, default="Shop now")
    link = models.CharField(max_length=200, default="/shop/")
    image = models.ImageField(upload_to="banners/", blank=True, null=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title


class Testimonial(models.Model):
    name = models.CharField(max_length=80)
    location = models.CharField(max_length=80, blank=True, help_text="e.g. Nairobi")
    quote = models.TextField(max_length=400)
    rating = models.PositiveSmallIntegerField(default=5)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name}: {self.quote[:40]}"


class SiteSettings(models.Model):
    """One row of shop-wide settings, edited from the dashboard (Settings page)."""
    announcement = models.CharField(max_length=160, blank=True,
                                    default="🚚 Delivery countrywide · Pay with M-Pesa · France · Japan · USA collections")
    announcement_link = models.CharField(max_length=200, blank=True, default="/help/delivery/")
    whatsapp_number = models.CharField(max_length=20, default="254795180079", help_text="Format 2547XXXXXXXX")
    support_phone = models.CharField(max_length=30, default="+254 795 180 079")
    support_email = models.EmailField(default="support@delightcareplus.com")
    instagram_url = models.URLField(blank=True)
    tiktok_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    free_delivery_over = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                             help_text="Free delivery when the order reaches this amount. 0 = off")
    pay_on_delivery = models.BooleanField(default=True, help_text="Allow cash / M-Pesa on delivery")
    airtel_money_number = models.CharField(max_length=20, blank=True, help_text="Number customers send Airtel Money to")
    mpesa_paybill_note = models.CharField(max_length=160, blank=True,
                                          help_text="Optional note on the payment page, e.g. Paybill 123456, Account = order number")
    low_stock_alert = models.PositiveIntegerField(default=5, help_text="Products at or below this stock show as low")
    chat_enabled = models.BooleanField(default=True)
    store_open = models.BooleanField(default=True, help_text="Turn off to pause checkout (holiday mode)")
    closed_message = models.CharField(max_length=200, blank=True, default="We're taking a short break — orders reopen soon!")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Shop settings"
        verbose_name_plural = "Shop settings"

    def __str__(self):
        return "Shop settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
