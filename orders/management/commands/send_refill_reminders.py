"""
Run once a day (cron / PythonAnywhere scheduled task):
    python manage.py send_refill_reminders
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.mail import send
from orders.models import RefillReminder


class Command(BaseCommand):
    help = "Email customers whose supplements/teas are about to run out."

    def handle(self, *args, **opts):
        due = RefillReminder.objects.filter(sent_at__isnull=True, cancelled=False,
                                            due_on__lte=timezone.localdate()).select_related("product", "order")
        sent = 0
        for r in due:
            if not r.product.is_active:
                r.cancelled = True
                r.save(update_fields=["cancelled"])
                continue
            if send(f"Running low on {r.product.name}? 🌿", "emails/refill_reminder.html",
                    {"reminder": r, "product": r.product, "order": r.order}, [r.email]):
                r.sent_at = timezone.now()
                r.save(update_fields=["sent_at"])
                sent += 1
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} refill reminder(s)."))
