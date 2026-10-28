from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.contrib import messages
from django.core import signing
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Profile
from core.models import NewsletterSubscriber

from .models import TrackedLink

UNSUBSCRIBE_SALT = "dcp-unsubscribe"


def robots(request):
    base = request.build_absolute_uri("/").rstrip("/")
    lines = ["User-agent: *", "Disallow: /manage/", "Disallow: /django-admin/", "Disallow: /cart/",
             "Disallow: /orders/", "Disallow: /account/", "Disallow: /chat/", "Disallow: /go/",
             "Disallow: /shop/api/", "Disallow: /shop/compare/", "Disallow: /*?*sort=", "",
             f"Sitemap: {base}/sitemap.xml"]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


def with_utm(url, source, medium="", campaign=""):
    """Add utm_… tags to a link (keeps any query it already has)."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query.update({k: v for k, v in (("utm_source", source), ("utm_medium", medium), ("utm_campaign", campaign)) if v})
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", urlencode(query), parts.fragment))


def is_local(path):
    """Only pages on this shop: '/shop/…' yes; 'https://…' or '//other.site' no."""
    return path.startswith("/") and not path.startswith("//") and "\\" not in path


def go(request, slug):
    """Short tracked link: count the click, then open the page with utm tags so the sale is credited."""
    link = get_object_or_404(TrackedLink, slug=slug)
    TrackedLink.objects.filter(pk=link.pk).update(clicks=F("clicks") + 1)
    destination = link.destination if is_local(link.destination) else "/"
    return redirect(with_utm(destination, link.source, link.medium, link.campaign or link.slug))


def unsubscribe_token(email):
    return signing.dumps(email.lower(), salt=UNSUBSCRIBE_SALT)


def unsubscribe(request, token):
    try:
        email = signing.loads(token, salt=UNSUBSCRIBE_SALT)
    except signing.BadSignature:
        messages.error(request, "That unsubscribe link isn't valid.")
        return redirect("core:home")
    if request.method == "POST":
        NewsletterSubscriber.objects.filter(email__iexact=email).update(is_active=False)
        Profile.objects.filter(user__email__iexact=email).update(marketing_opt_in=False)
        return render(request, "marketing/unsubscribed.html", {"email": email, "done": True})
    return render(request, "marketing/unsubscribed.html", {"email": email, "token": token})
