from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class TrackedLink(models.Model):
    """A short link like /go/jane-ig for a bio, post, influencer or ad. Counts clicks and the sales it brings."""
    slug = models.SlugField(max_length=40, unique=True, help_text="Short name in the link, e.g. jane-ig → /go/jane-ig")
    destination = models.CharField(max_length=300, default="/", help_text="Page to open, e.g. / or /shop/p/… or /shop/c/collagen/")
    source = models.CharField(max_length=60, help_text="Where the link is posted: instagram, tiktok, facebook, whatsapp, google, influencer…")
    medium = models.CharField(max_length=60, blank=True, help_text="e.g. bio, story, post, paid, influencer, sms")
    campaign = models.CharField(max_length=100, blank=True, help_text="e.g. december-sale, collagen-launch")
    note = models.CharField(max_length=160, blank=True, help_text="Just for you, e.g. 'Jane's TikTok, paid KES 5,000'")
    clicks = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.slug = slugify(self.slug) or slugify(f"{self.source}-{self.campaign}")[:40]
        self.source = slugify(self.source)
        self.medium = slugify(self.medium)
        self.campaign = slugify(self.campaign)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"/go/{self.slug}"

    def get_absolute_url(self):
        return reverse("marketing:go", args=[self.slug])


class EmailCampaign(models.Model):
    AUDIENCES = (
        ("subscribers", "Newsletter subscribers"),
        ("customers", "Customers who opted in to offers"),
        ("everyone", "Subscribers + opted-in customers"),
    )
    subject = models.CharField(max_length=150)
    heading = models.CharField(max_length=150, help_text="Big title at the top of the email")
    body = models.TextField(help_text="Your message. Blank lines start new paragraphs.")
    products = models.ManyToManyField("catalog.Product", blank=True, help_text="Shown as a product grid (up to 6)")
    coupon = models.ForeignKey("cart.Coupon", null=True, blank=True, on_delete=models.SET_NULL,
                               help_text="Optional: shown as a code box")
    button_text = models.CharField(max_length=40, default="Shop now")
    button_link = models.CharField(max_length=300, default="/shop/")
    audience = models.CharField(max_length=15, choices=AUDIENCES, default="everyone")
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.subject


class SavedBag(models.Model):
    """A member's bag, saved so it follows them across devices and can be used for a reminder."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="saved_bag")
    items = models.JSONField(default=dict)   # {variant_id: quantity}
    updated_at = models.DateTimeField(auto_now=True)
    reminded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Bag of {self.user}"
