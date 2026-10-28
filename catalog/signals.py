"""Email 'back in stock' alerts when a product goes from 0 to available."""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from core.mail import send

from .models import Product


@receiver(pre_save, sender=Product)
def remember_old_stock(sender, instance, **kwargs):
    instance._old_stock = (Product.objects.filter(pk=instance.pk).values_list("stock", flat=True).first()
                           if instance.pk else None)


@receiver(post_save, sender=Product)
def notify_back_in_stock(sender, instance, created, **kwargs):
    old = getattr(instance, "_old_stock", None)
    if created or old is None or old > 0 or instance.stock <= 0 or not instance.is_active:
        return
    for alert in instance.stock_alerts.filter(notified_at__isnull=True):
        if send(f"Back in stock: {instance.name}", "emails/back_in_stock.html", {"product": instance}, [alert.email]):
            alert.notified_at = timezone.now()
            alert.save(update_fields=["notified_at"])
