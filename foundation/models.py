"""Delight Care Plus Foundation — fundraisers (campaigns), donations and progress updates."""
import secrets

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Count, Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class Campaign(models.Model):
    CATEGORY_CHOICES = (
        ("medical", "Medical & treatment"),
        ("wellness", "Health & wellness"),
        ("education", "Education"),
        ("community", "Community"),
        ("women", "Women & girls"),
        ("children", "Children"),
        ("emergency", "Emergency relief"),
    )
    CATEGORY_ICONS = {
        "medical": "fa-solid fa-kit-medical", "wellness": "fa-solid fa-heart-pulse",
        "education": "fa-solid fa-graduation-cap", "community": "fa-solid fa-people-roof",
        "women": "fa-solid fa-person-dress", "children": "fa-solid fa-children",
        "emergency": "fa-solid fa-truck-medical",
    }
    STATUS_CHOICES = (
        ("PENDING", "Waiting for review"),
        ("ACTIVE", "Live"),
        ("CLOSED", "Closed"),
        ("REJECTED", "Not approved"),
    )

    title = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    summary = models.CharField(max_length=220, help_text="One or two sentences shown on cards and when shared")
    story = models.TextField(help_text="The full story. Blank lines start new paragraphs.")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="medical")
    cover = models.ImageField(upload_to="foundation/", blank=True, null=True)
    video_url = models.URLField(blank=True, help_text="Optional YouTube link")

    beneficiary = models.CharField(max_length=120, help_text="Who the money is for, e.g. 'Amina W.' or 'Kibera Girls School'")
    location = models.CharField(max_length=80, blank=True, help_text="e.g. Nairobi")
    organiser = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="fundraisers")
    organiser_name = models.CharField(max_length=120, blank=True,
                                      help_text="Shown as 'Organised by'. Empty = the Foundation")
    organiser_phone = models.CharField(max_length=20, blank=True)

    goal = models.PositiveIntegerField(help_text="Target in KES")
    end_date = models.DateField(null=True, blank=True, help_text="Optional. Donations stop after this date.")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    is_featured = models.BooleanField(default=False, help_text="Show at the top of the Foundation page")
    is_verified = models.BooleanField(default=False, help_text="The Foundation has checked the documents for this fundraiser")
    is_sample = models.BooleanField(default=False, help_text="Demo fundraiser from the setup script — remove before launch")
    review_note = models.CharField(max_length=255, blank=True, help_text="Private note, or the reason it was not approved")

    # Cached from PAID donations — recalculated by refresh_totals()
    raised = models.PositiveIntegerField(default=0)
    donor_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_featured", "-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:120] or "fundraiser"
            slug, n = base, 2
            while Campaign.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("foundation:campaign", args=[self.slug])

    @property
    def percent(self):
        return min(100, int(self.raised * 100 / self.goal)) if self.goal else 0

    @property
    def icon(self):
        return self.CATEGORY_ICONS.get(self.category, "fa-solid fa-hand-holding-heart")

    @property
    def days_left(self):
        if not self.end_date:
            return None
        return max(0, (self.end_date - timezone.localdate()).days)

    @property
    def is_open(self):
        if self.status != "ACTIVE":
            return False
        return not self.end_date or self.end_date >= timezone.localdate()

    @property
    def display_organiser(self):
        return self.organiser_name or "Delight Care Plus Foundation"

    def paragraphs(self):
        return [p.strip() for p in self.story.replace("\r\n", "\n").split("\n\n") if p.strip()]

    def refresh_totals(self):
        agg = self.donations.filter(status="PAID").aggregate(total=Sum("amount"), n=Count("id"))
        self.raised, self.donor_count = int(agg["total"] or 0), agg["n"] or 0
        Campaign.objects.filter(pk=self.pk).update(raised=self.raised, donor_count=self.donor_count)


class Donation(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Awaiting payment"),
        ("VERIFY", "To confirm (Airtel)"),
        ("PAID", "Received"),
        ("FAILED", "Not completed"),
        ("REFUNDED", "Refunded"),
    )
    METHOD_CHOICES = (("mpesa", "M-Pesa"), ("airtel", "Airtel Money"), ("manual", "Recorded by staff"))

    reference = models.CharField(max_length=16, unique=True, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, related_name="donations")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="donations")

    amount = models.PositiveIntegerField(help_text="KES")
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    message = models.CharField(max_length=300, blank=True, help_text="Words of support shown on the fundraiser")
    is_anonymous = models.BooleanField(default=False, help_text="Hide the donor's name on the public page")

    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default="mpesa")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    checkout_request_id = models.CharField(max_length=80, blank=True, db_index=True)
    merchant_request_id = models.CharField(max_length=80, blank=True)
    payment_reference = models.CharField(max_length=40, blank=True, help_text="M-Pesa receipt or Airtel transaction ID")
    result_desc = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} · KES {self.amount}"

    def save(self, *args, **kwargs):
        if not self.reference:
            while True:
                ref = "DCF" + secrets.token_hex(4).upper()[:7]
                if not Donation.objects.filter(reference=ref).exists():
                    self.reference = ref
                    break
        super().save(*args, **kwargs)

    @property
    def public_name(self):
        return "Anonymous" if self.is_anonymous else (self.name.split()[0] if self.name else "A friend")

    @property
    def is_paid(self):
        return self.status == "PAID"


class CampaignUpdate(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="updates")
    title = models.CharField(max_length=120)
    body = models.TextField(max_length=3000)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
