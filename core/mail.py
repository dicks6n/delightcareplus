"""Send branded HTML email with a plain-text fallback. Never raises."""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger("core")


def send(subject, template, context, to):
    to = [t for t in (to or []) if t]
    if not to:
        return False
    from .models import SiteSettings
    shop = SiteSettings.load()
    ctx = {
        "site_name": settings.SITE_NAME,
        "site_url": settings.SITE_URL.rstrip("/"),
        "whatsapp": shop.whatsapp_number,
        "support_email": shop.support_email,
        **context,
    }
    try:
        html = render_to_string(template, ctx)
        msg = EmailMultiAlternatives(subject, strip_tags(html), settings.DEFAULT_FROM_EMAIL, to)
        msg.attach_alternative(html, "text/html")
        msg.send()
        return True
    except Exception:
        logger.exception("Email '%s' to %s failed", subject, to)
        return False
