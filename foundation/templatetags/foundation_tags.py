import re
from urllib.parse import parse_qs, urlparse

from django import template

register = template.Library()


@register.filter
def youtube_embed(url):
    """https://youtu.be/ID, youtube.com/watch?v=ID or /shorts/ID → privacy-friendly embed URL ('' if not YouTube)."""
    if not url:
        return ""
    u = urlparse(url)
    host = (u.hostname or "").lower()
    vid = ""
    if host.endswith("youtu.be"):
        vid = u.path.strip("/")
    elif "youtube" in host:
        vid = parse_qs(u.query).get("v", [""])[0] or (re.findall(r"/(?:shorts|embed|live)/([\w-]+)", u.path) or [""])[0]
    vid = vid.split("/")[0]
    return f"https://www.youtube-nocookie.com/embed/{vid}" if re.fullmatch(r"[\w-]{6,20}", vid or "") else ""


@register.filter
def initials(name):
    parts = [p for p in (name or "").split() if p]
    return ("".join(p[0] for p in parts[:2]) or "?").upper()
