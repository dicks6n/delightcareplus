"""
Ad Studio: ready-to-post ad images and captions made from a product.

Formats
    post    1080 × 1080   Instagram / Facebook feed, WhatsApp catalog
    story   1080 × 1920   Instagram & Facebook Stories, WhatsApp Status, TikTok
    wide    1200 × 628    Facebook / Google link ads, X, LinkedIn
Styles
    dark    the shop's own dark green look
    light   the product's collection colours (France / Japan / USA)
    offer   the offer (e.g. "20% OFF") takes centre stage
Stories keep text out of the top and bottom ~250 px, where Instagram puts its own buttons.
"""
import io
import random
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw, ImageFilter

from catalog.imaging import PALETTES, S, _fit_lines, _icon_font, font, hex2rgb, mix

ICONS_ARROW = 0xf061  # Font Awesome arrow-right

FORMATS = {
    "post": ("Square post", 1080, 1080),
    "story": ("Story / Status / TikTok", 1080, 1920),
    "wide": ("Wide ad (Facebook, Google)", 1200, 628),
}
STYLES = {"dark": "Dark (shop colours)", "light": "Light (collection colours)", "offer": "Big offer"}

LOGO_DIR = Path(settings.BASE_DIR) / "static" / "img"
DARK = {"bg1": (8, 12, 9), "bg2": (24, 38, 20), "glow": (144, 188, 121), "ink": (255, 255, 255),
        "soft": (201, 214, 195), "accent": (168, 217, 144), "badge": (242, 201, 76), "badge_ink": (28, 30, 18),
        "cta": (144, 188, 121), "cta_ink": (12, 20, 10), "line": (255, 255, 255, 40), "logo": "logo-mark-light.png"}


def _light_theme(code):
    p = PALETTES.get(code, PALETTES["default"])
    primary = hex2rgb(p["primary"])[:3]
    return {"bg1": hex2rgb(p["bg1"])[:3], "bg2": hex2rgb(p["bg2"])[:3], "glow": (255, 255, 255),
            "ink": hex2rgb(p["ink"])[:3], "soft": mix(hex2rgb(p["ink"]), (255, 255, 255), .3)[:3],
            "accent": primary, "badge": hex2rgb(p["accent"])[:3], "badge_ink": (255, 255, 255),
            "cta": primary, "cta_ink": (255, 255, 255), "line": primary + (60,), "logo": "logo-mark-dark.png"}


# ------------------------------------------------------------------ drawing helpers
def _background(w, h, t, seed):
    img = Image.new("RGBA", (w, h))
    grad = Image.new("RGBA", (1, h))
    for y in range(h):
        grad.putpixel((0, y), mix(t["bg1"] + (255,), t["bg2"] + (255,), (y / h) ** 1.3))
    img = grad.resize((w, h))
    rnd = random.Random(seed)
    glow = Image.new("RGBA", (w, h), t["glow"] + (0,))
    gd = ImageDraw.Draw(glow)
    for _ in range(3):
        r = rnd.randint(int(min(w, h) * .25), int(min(w, h) * .55))
        cx, cy = rnd.randint(0, w), rnd.randint(0, h)
        gd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=t["glow"] + (46,))
    return Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(min(w, h) // 8)))


def _card(img, photo, box, radius):
    """Product photo on a rounded card with a soft shadow."""
    x0, y0, x1, y1 = [int(v) for v in box]
    w, h = x1 - x0, y1 - y0
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((x0 + 10 * S, y0 + 26 * S, x1 + 10 * S, y1 + 26 * S), radius=radius, fill=(0, 0, 0, 120))
    img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(28 * S)))
    pic = photo.convert("RGB")
    side = min(pic.size)
    pic = pic.crop(((pic.width - side) // 2, (pic.height - side) // 2, (pic.width + side) // 2, (pic.height + side) // 2))
    pic = pic.resize((w, h), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
    pic.putalpha(mask)
    img.alpha_composite(pic, (x0, y0))
    ImageDraw.Draw(img).rounded_rectangle(box, radius=radius, outline=(255, 255, 255, 70), width=2 * S)
    return img


def _logo(img, xy, height, t, center=False, text=True):
    mark = Image.open(LOGO_DIR / t["logo"]).convert("RGBA")
    scale = height / mark.height
    mark = mark.resize((int(mark.width * scale), int(height)), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    f = font("sans", 600, height // S * .42)
    label_w = d.textlength("Delight Care Plus", font=f) + height * .25 if text else 0
    x, y = xy
    if center:
        x = x - (mark.width + label_w) / 2
    img.alpha_composite(mark, (int(x), int(y)))
    if text:
        d.text((x + mark.width + height * .22, y + height / 2), "Delight Care Plus", font=f, fill=t["ink"], anchor="lm")
    return img


def _pill(d, x, y, text, fnt, fill, ink, pad_x=34, pad_y=18, anchor="l", arrow=True):
    """Rounded call-to-action button; the arrow is drawn from the icon font (the text fonts have no →)."""
    icon = _icon_font(fnt.size / S * .8) if arrow else None
    gap = fnt.size * .45
    text_w = d.textlength(text, font=fnt)
    icon_w = d.textlength(chr(ICONS_ARROW), font=icon) + gap if arrow else 0
    w = text_w + icon_w + 2 * pad_x * S
    h = fnt.size + 2 * pad_y * S
    if anchor == "c":
        x -= w / 2
    elif anchor == "r":
        x -= w
    d.rounded_rectangle((x, y, x + w, y + h), radius=h / 2, fill=fill)
    tx = x + pad_x * S
    d.text((tx, y + h / 2), text, font=fnt, fill=ink, anchor="lm")
    if arrow:
        d.text((tx + text_w + gap, y + h / 2), chr(ICONS_ARROW), font=icon, fill=ink, anchor="lm")
    return x, y, x + w, y + h


def _coupon(d, x, y, code, t, anchor="l"):
    f = font("sans", 600, 26)
    label = f"Use code  {code}"
    w = d.textlength(label, font=f) + 56 * S
    h = f.size + 34 * S
    if anchor == "c":
        x -= w / 2
    # dashed border
    dash, gap = 14 * S, 9 * S
    for (ax, ay, bx, by) in ((x, y, x + w, y), (x, y + h, x + w, y + h), (x, y, x, y + h), (x + w, y, x + w, y + h)):
        length = max(abs(bx - ax), abs(by - ay))
        pos = 0
        while pos < length:
            end = min(pos + dash, length)
            if ax == bx:
                d.line((ax, ay + pos, bx, ay + end), fill=t["badge"], width=3 * S)
            else:
                d.line((ax + pos, ay, ax + end, by), fill=t["badge"], width=3 * S)
            pos += dash + gap
    d.text((x + w / 2, y + h / 2), label, font=f, fill=t["ink"], anchor="mm")
    return y + h


def _badge(d, cx, cy, r, text, t):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=t["badge"])
    fb, lines = _fit_lines(d, text.upper(), "sans", 700, r * 1.5, int(r / S * .55), 14, max_lines=2)
    lh = fb.size * 1.05
    y = cy - lh * (len(lines) - 1) / 2
    for line in lines:
        d.text((cx, y), line, font=fb, fill=t["badge_ink"], anchor="mm")
        y += lh


def _price(d, x, y, price, old, t, size=52, anchor="l"):
    fp, fo = font("sans", 700, size), font("sans", 400, size * .55)
    w = d.textlength(price, font=fp) + (d.textlength(old, font=fo) + 22 * S if old else 0)
    if anchor == "c":
        x -= w / 2
    d.text((x, y), price, font=fp, fill=t["ink"])
    if old:
        ox = x + d.textlength(price, font=fp) + 22 * S
        oy = y + fp.size - fo.size - 6 * S
        d.text((ox, oy), old, font=fo, fill=t["soft"])
        ow = d.textlength(old, font=fo)
        d.line((ox, oy + fo.size * .6, ox + ow, oy + fo.size * .6), fill=t["soft"], width=3 * S)
    return y + fp.size


def _text_block(d, x, y, text, kind, weight, size, min_size, width, lines, fill, anchor="l", leading=1.12):
    if not text:
        return y
    f, rows = _fit_lines(d, text, kind, weight, width, size, min_size, max_lines=lines)
    for row in rows:
        d.text((x, y), row, font=f, fill=fill, anchor="mt" if anchor == "c" else "lt")
        y += f.size * leading
    return y


# ------------------------------------------------------------------ main
def render_ad(photo, fmt="post", style="dark", headline="", sub="", price="", old_price="", badge="", coupon="",
              cta="Shop now", footer="", collection="default", big_offer=""):
    _, W1, H1 = FORMATS.get(fmt, FORMATS["post"])
    W, H = W1 * S, H1 * S
    t = _light_theme(collection) if style == "light" else dict(DARK)
    img = _background(W, H, t, headline or "ad")
    d = ImageDraw.Draw(img)
    serif = "serif"
    offer_mode = style == "offer" and big_offer

    if fmt == "story":
        img = _logo(img, (W / 2, 150 * S), 92 * S, t, center=True)
        side = 600 * S
        card = ((W - side) / 2, 300 * S, (W + side) / 2, 300 * S + side)
        img = _card(img, photo, card, 46 * S)
        d = ImageDraw.Draw(img)
        if badge:
            _badge(d, card[2] - 100 * S, card[1] + 100 * S, 78 * S, badge, t)
        y = card[3] + 60 * S
        if offer_mode:
            y = _text_block(d, W / 2, y, big_offer, "sans", 700, 120, 60, W - 160 * S, 1, t["badge"], "c")
            y = _text_block(d, W / 2, y + 6 * S, headline, serif, 700, 56, 34, W - 160 * S, 2, t["ink"], "c")
        else:
            y = _text_block(d, W / 2, y, headline, serif, 700, 72, 40, W - 160 * S, 3, t["ink"], "c")
        y = _text_block(d, W / 2, y + 14 * S, sub, "sans", 400, 30, 22, W - 200 * S, 2, t["soft"], "c", 1.3)
        if price:
            y = _price(d, W / 2, y + 24 * S, price, old_price, t, 58, "c")
        if coupon:
            y = _coupon(d, W / 2, y + 28 * S, coupon, t, "c")
        # Button and contact line sit just above Instagram's reply bar (bottom 250 px)
        _pill(d, W / 2, H - 420 * S, cta, font("sans", 700, 36), t["cta"], t["cta_ink"], 56, 24, "c")
        if footer:
            d.text((W / 2, H - 290 * S), footer, font=font("sans", 500, 26), fill=t["soft"], anchor="mm")

    elif fmt == "wide":
        m = 40 * S
        card = (m, m + 24 * S, m + (H - 2 * m - 48 * S), H - m - 24 * S)
        img = _card(img, photo, card, 30 * S)
        d = ImageDraw.Draw(img)
        if badge:
            _badge(d, card[2] - 72 * S, card[1] + 72 * S, 56 * S, badge, t)
        x = card[2] + 56 * S
        width = W - x - m
        img = _logo(img, (x, 40 * S), 54 * S, t)
        d = ImageDraw.Draw(img)
        y = 128 * S
        if offer_mode:
            y = _text_block(d, x, y, big_offer, "sans", 700, 76, 40, width, 1, t["badge"])
            y = _text_block(d, x, y + 4 * S, headline, serif, 700, 40, 26, width, 2, t["ink"])
        else:
            y = _text_block(d, x, y, headline, serif, 700, 52, 28, width, 3, t["ink"])
        y = _text_block(d, x, y + 8 * S, sub, "sans", 400, 24, 18, width, 2, t["soft"], leading=1.3)
        if price:
            y = _price(d, x, y + 16 * S, price, old_price, t, 44)
        if coupon:
            y = _coupon(d, x, y + 18 * S, coupon, t)
        fc = font("sans", 700, 28)
        pill_h = fc.size + 32 * S
        cta_y = min(max(y + 24 * S, H - pill_h - 80 * S), H - pill_h - 56 * S)
        _pill(d, x, cta_y, cta, fc, t["cta"], t["cta_ink"], 40, 16)
        if footer:
            d.text((x, H - 30 * S), footer, font=font("sans", 500, 20), fill=t["soft"], anchor="ls")

    else:  # post
        m = 56 * S
        img = _logo(img, (m, 48 * S), 72 * S, t)
        d = ImageDraw.Draw(img)
        card = (m, 170 * S, m + 500 * S, 670 * S)
        img = _card(img, photo, card, 36 * S)
        d = ImageDraw.Draw(img)
        if badge:
            _badge(d, card[2] - 84 * S, card[1] + 84 * S, 66 * S, badge, t)
        x = card[2] + 56 * S
        width = W - x - m
        y = card[1] + 6 * S
        if offer_mode:
            y = _text_block(d, x, y, big_offer, "sans", 700, 92, 44, width, 2, t["badge"])
            y = _text_block(d, x, y + 6 * S, headline, serif, 700, 44, 28, width, 3, t["ink"])
        else:
            y = _text_block(d, x, y, headline, serif, 700, 58, 30, width, 4, t["ink"])
        y = _text_block(d, x, y + 14 * S, sub, "sans", 400, 26, 18, width, 4, t["soft"], leading=1.3)
        if price:
            y = _price(d, x, y + 22 * S, price, old_price, t, 50)
        if coupon:
            y = _coupon(d, x, y + 24 * S, coupon, t)
        # bottom band: CTA + contact line
        band_y = H - 300 * S
        d.line((m, band_y, W - m, band_y), fill=t["line"], width=2 * S)
        _pill(d, W / 2, band_y + 70 * S, cta, font("sans", 700, 40), t["cta"], t["cta_ink"], 60, 24, "c")
        if footer:
            d.text((W / 2, H - 60 * S), footer, font=font("sans", 500, 26), fill=t["soft"], anchor="mm")

    return img.resize((W1, H1), Image.LANCZOS).convert("RGB")


def jpeg(img, quality=90):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, optimize=True)
    return buf.getvalue()
