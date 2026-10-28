"""Marketing emails: campaigns to subscribers and opted-in customers, and abandoned-bag reminders.

Only people who said yes to offers are emailed (newsletter sign-up, or the box at account sign-up),
and every email has a one-click unsubscribe link, as the Data Protection Act expects.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags

from core.models import NewsletterSubscriber, SiteSettings

from .views import unsubscribe_token, with_utm

logger = logging.getLogger("core")
BATCH = 50


def audience_emails(audience):
    """Unique, lower-case addresses for a campaign audience (people who opted in only)."""
    emails = []
    if audience in ("subscribers", "everyone"):
        emails += NewsletterSubscriber.objects.filter(is_active=True).values_list("email", flat=True)
    if audience in ("customers", "everyone"):
        emails += (User.objects.filter(is_active=True, profile__marketing_opt_in=True).exclude(email="")
                   .values_list("email", flat=True))
    unsubscribed = {e.lower() for e in NewsletterSubscriber.objects.filter(is_active=False).values_list("email", flat=True)}
    seen, out = set(), []
    for e in emails:
        e = e.strip().lower()
        if e and e not in seen and e not in unsubscribed:
            seen.add(e)
            out.append(e)
    return out


def _context(base_url):
    shop = SiteSettings.load()
    return {"site_name": settings.SITE_NAME, "site_url": base_url.rstrip("/"), "whatsapp": shop.whatsapp_number,
            "support_email": shop.support_email}


def _message(subject, template, ctx, email, base_url, connection):
    unsubscribe = base_url.rstrip("/") + reverse("marketing:unsubscribe", args=[unsubscribe_token(email)])
    html = render_to_string(template, {**ctx, "unsubscribe_url": unsubscribe})
    msg = EmailMultiAlternatives(subject, strip_tags(html), settings.DEFAULT_FROM_EMAIL, [email], connection=connection,
                                 headers={"List-Unsubscribe": f"<{unsubscribe}>"})
    msg.attach_alternative(html, "text/html")
    return msg


def campaign_context(campaign, base_url):
    base = base_url.rstrip("/")
    utm = lambda url: with_utm(url if url.startswith("http") else base + url, "email", "newsletter",
                               f"campaign-{campaign.pk}")
    products = [{"p": p, "url": utm(p.get_absolute_url()), "image": base + p.showcase_image().url if p.image else ""}
                for p in campaign.products.filter(is_active=True).prefetch_related("images")[:6]]
    return {**_context(base_url), "campaign": campaign, "products": products,
            "paragraphs": [x.strip() for x in campaign.body.split("\n\n") if x.strip()],
            "button_url": utm(campaign.button_link or "/shop/")}


def send_campaign(campaign, base_url, only_to=None):
    """Send to the campaign's audience (or just `only_to`, for a test). Returns how many were sent."""
    recipients = [only_to] if only_to else audience_emails(campaign.audience)
    ctx = campaign_context(campaign, base_url)
    sent = 0
    connection = get_connection()
    for i in range(0, len(recipients), BATCH):
        batch = [_message(campaign.subject, "emails/campaign.html", ctx, e, base_url, connection) for e in recipients[i:i + BATCH]]
        try:
            sent += connection.send_messages(batch) or 0
        except Exception:
            logger.exception("Campaign %s: a batch failed", campaign.pk)
    if not only_to:
        campaign.sent_at = timezone.now()
        campaign.sent_count = sent
        campaign.save(update_fields=["sent_at", "sent_count"])
    return sent


def send_bag_reminders(base_url, older_than_hours=3, within_days=7):
    """Email members who left items in their bag (once per bag), if they opted in to offers."""
    from catalog.models import Variant
    from orders.models import Order

    from .models import SavedBag
    now = timezone.now()
    bags = SavedBag.objects.filter(reminded_at__isnull=True, updated_at__lte=now - timedelta(hours=older_than_hours),
                                   updated_at__gte=now - timedelta(days=within_days),
                                   user__is_active=True, user__profile__marketing_opt_in=True).exclude(user__email="")
    connection = get_connection()
    sent = 0
    for bag in bags.select_related("user"):
        if Order.objects.filter(user=bag.user, created_at__gte=bag.updated_at).exists():
            bag.reminded_at = now
            bag.save(update_fields=["reminded_at"])
            continue
        ids = [int(k) for k in bag.items if str(k).isdigit()]
        variants = Variant.objects.filter(id__in=ids, product__is_active=True).select_related("product")
        lines = [{"v": v, "qty": bag.items.get(str(v.id), 1),
                  "image": base_url.rstrip("/") + v.product.showcase_image().url if v.product.image else ""}
                 for v in variants if v.stock > 0]
        if not lines:
            continue
        ctx = {**_context(base_url), "user": bag.user, "lines": lines,
               "bag_url": with_utm(base_url.rstrip("/") + "/cart/", "email", "reminder", "abandoned-bag")}
        try:
            sent += connection.send_messages([_message("You left something in your bag 🛍️", "emails/bag_reminder.html",
                                                       ctx, bag.user.email, base_url, connection)]) or 0
        except Exception:
            logger.exception("Bag reminder to %s failed", bag.user_id)
            continue
        bag.reminded_at = now
        bag.save(update_fields=["reminded_at"])
    return sent
