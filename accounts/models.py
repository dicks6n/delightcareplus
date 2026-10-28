from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    """Saved delivery details so checkout is one tap next time."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=80, blank=True)
    address = models.TextField(blank=True)
    skin_type = models.CharField(max_length=40, blank=True)
    marketing_opt_in = models.BooleanField(default=False)

    def __str__(self):
        return f"Profile of {self.user.username}"


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)


class WishlistItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wishlist")
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "product")
        ordering = ["-created_at"]


class PointsTransaction(models.Model):
    """Glow Points ledger. Balance = sum of points."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="points")
    points = models.IntegerField(help_text="Positive = earned, negative = spent")
    reason = models.CharField(max_length=120)
    order = models.ForeignKey("orders.Order", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}: {self.points:+d} ({self.reason})"


def points_balance(user):
    if not user.is_authenticated:
        return 0
    return user.points.aggregate(t=models.Sum("points"))["t"] or 0
