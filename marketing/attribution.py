"""
Remember which ad, post or link brought a visitor, so their order can be credited to it.

Sources, in order of preference:
  1. utm_source / utm_medium / utm_campaign tags (Ad Studio captions and /go/ links add these)
  2. ?ref=CODE refer-a-friend links
  3. Click IDs that ad platforms add: fbclid (Meta), ttclid (TikTok), gclid (Google)
  4. The referring website (Google search, Instagram, Facebook…), on the first visit only
The latest tagged visit wins, so an order is credited to the ad that brought the customer back.
"""
from urllib.parse import urlparse

from django.utils.text import slugify

SESSION_KEY = "attribution"
REF_KEY = "referral_code"

CLICK_IDS = {"fbclid": ("meta", "paid"), "ttclid": ("tiktok", "paid"), "gclid": ("google", "paid")}
REFERRERS = [  # (part of the referring host, source, medium)
    ("instagram.", "instagram", "social"), ("facebook.", "facebook", "social"), ("fb.", "facebook", "social"),
    ("tiktok.", "tiktok", "social"), ("t.co", "twitter", "social"), ("twitter.", "twitter", "social"),
    ("x.com", "twitter", "social"), ("youtube.", "youtube", "social"), ("pinterest.", "pinterest", "social"),
    ("google.", "google", "organic"), ("bing.", "bing", "organic"), ("yahoo.", "yahoo", "organic"),
    ("jiji.", "jiji", "referral"), ("whatsapp.", "whatsapp", "social"),
]


def _clean(value, n=60):
    return slugify(value or "")[:n]


def capture(request):
    g = request.GET
    data = None
    if g.get("utm_source"):
        data = {"source": _clean(g["utm_source"]), "medium": _clean(g.get("utm_medium")),
                "campaign": _clean(g.get("utm_campaign"), 100)}
    elif g.get("ref"):
        data = {"source": "referral", "medium": "friend", "campaign": _clean(g["ref"], 100)}
    else:
        for key, (source, medium) in CLICK_IDS.items():
            if g.get(key):
                data = {"source": source, "medium": medium, "campaign": ""}
                break
    if data is None and SESSION_KEY not in request.session:
        host = urlparse(request.META.get("HTTP_REFERER", "")).netloc.lower()
        if host and host.split(":")[0] != request.get_host().split(":")[0]:
            for part, source, medium in REFERRERS:
                if part in host:
                    data = {"source": source, "medium": medium, "campaign": ""}
                    break
            else:
                data = {"source": _clean(host.removeprefix("www.")), "medium": "referral", "campaign": ""}
    if data:
        request.session[SESSION_KEY] = data
    if g.get("ref"):
        request.session[REF_KEY] = g["ref"].strip().upper()[:30]


def get(request):
    return request.session.get(SESSION_KEY) or {}


class AttributionMiddleware:
    SKIP = ("/manage/", "/django-admin/", "/static/", "/media/", "/feeds/", "/chat/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "GET" and not request.path.startswith(self.SKIP):
            capture(request)
            if request.GET.get("ref"):
                from .referrals import apply_from_session
                apply_from_session(request)
        return self.get_response(request)
