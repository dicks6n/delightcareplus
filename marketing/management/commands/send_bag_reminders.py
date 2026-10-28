from django.conf import settings
from django.core.management.base import BaseCommand

from marketing.emailing import send_bag_reminders


class Command(BaseCommand):
    help = "Email members who left items in their bag (run every few hours, or daily)."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=3, help="Bag untouched for at least this many hours")

    def handle(self, *args, hours=3, **opts):
        n = send_bag_reminders(settings.SITE_URL, older_than_hours=hours)
        self.stdout.write(f"Sent {n} bag reminder(s).")
