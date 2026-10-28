"""
Studio-style product images drawn with Pillow — used for sample products and
brand banners until real photos are uploaded.

    img = render_product("Vitamin C Glow Serum", "Japan", "serum", "30ml", palette)
    img.save("x.jpg", quality=88)
"""
import math
import random
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_DIR = Path(__file__).parent / "assets" / "fonts"
S = 2  # supersampling factor
SIZE = 1200


def font(kind="sans", weight=600, size=40):
    name = {"sans": "poppins", "serif": "playfair-display"}[kind]
    w = {400: 400, 600: 600, 700: 700}.get(weight, 600)
    return ImageFont.truetype(str(FONT_DIR / f"{name}-latin-{w}-normal.woff"), size * S)


def hex2rgb(h, a=255):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def mix(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)) + (255,)


PALETTES = {
    # France collection: navy, cream and gold
    "FR": {"bg1": "#f6f1e7", "bg2": "#e7dcc8", "primary": "#1e2a4a", "accent": "#c9a45c", "label": "#fbf8f1",
           "ink": "#1e2a4a", "glass": "#cfd8e6", "font": "serif"},
    # Japan — soft blush, white and sakura
    "JP": {"bg1": "#fdf3f1", "bg2": "#f5d9d6", "primary": "#e98c97", "accent": "#b4475a", "label": "#ffffff",
           "ink": "#5b2a33", "glass": "#fbe3e6", "font": "sans"},
    # USA — clean wellness green and white
    "US": {"bg1": "#eef5ec", "bg2": "#d3e6cd", "primary": "#2f6b3f", "accent": "#e8a33d", "label": "#ffffff",
           "ink": "#173823", "glass": "#d9ead3", "font": "sans"},
    "default": {"bg1": "#eef3ea", "bg2": "#d7e4cf", "primary": "#2d5016", "accent": "#90bc79", "label": "#ffffff",
                "ink": "#1f2a1c", "glass": "#e3eedc", "font": "sans"},
}


# ------------------------------------------------------------------ helpers
def _background(p, seed):
    W = SIZE * S
    img = Image.new("RGBA", (W, W), hex2rgb(p["bg1"]))
    top, bottom = hex2rgb(p["bg1"]), hex2rgb(p["bg2"])
    grad = Image.new("RGBA", (1, W))
    for y in range(W):
        grad.putpixel((0, y), mix(top, bottom, (y / W) ** 1.4))
    img = grad.resize((W, W))
    d = ImageDraw.Draw(img)
    rnd = random.Random(seed)
    # soft orbs
    for _ in range(3):
        r = rnd.randint(180, 420) * S
        cx, cy = rnd.randint(0, W), rnd.randint(0, int(W * .7))
        orb = Image.new("RGBA", (W, W), hex2rgb(p["label"], 0))
        ImageDraw.Draw(orb).ellipse((cx - r, cy - r, cx + r, cy + r), fill=hex2rgb(p["label"], 110))
        img = Image.alpha_composite(img, orb.filter(ImageFilter.GaussianBlur(60 * S)))
    # podium
    d = ImageDraw.Draw(img)
    pod = Image.new("RGBA", (W, W), (255, 255, 255, 0))
    pd = ImageDraw.Draw(pod)
    pd.ellipse((W * .14, W * .80, W * .86, W * .94), fill=hex2rgb(p["label"], 200))
    pd.ellipse((W * .14, W * .78, W * .86, W * .92), fill=mix(hex2rgb(p["bg2"]), (255, 255, 255), .55))
    img = Image.alpha_composite(img, pod)
    return img


def _shadow(img, box, strength=90, blur=28):
    W = img.size[0]
    sh = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse(box, fill=(0, 0, 0, strength))
    return Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(blur * S)))


def _highlight(img, box, radius):
    W = img.size[0]
    hl = Image.new("RGBA", (W, W), (255, 255, 255, 0))
    x0, y0, x1, y1 = box
    w = x1 - x0
    ImageDraw.Draw(hl).rounded_rectangle((x0 + w * .12, y0 + (y1 - y0) * .06, x0 + w * .22, y1 - (y1 - y0) * .1),
                                         radius=radius, fill=(255, 255, 255, 120))
    return Image.alpha_composite(img, hl.filter(ImageFilter.GaussianBlur(6 * S)))


def _fit_lines(draw, text, fnt_kind, weight, max_w, start_size, min_size, max_lines=3):
    words = text.split()
    size = start_size
    while size >= min_size:
        f = font(fnt_kind, weight, size)
        lines, cur = [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if draw.textlength(trial, font=f) <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        if len(lines) <= max_lines and all(draw.textlength(l, font=f) <= max_w for l in lines):
            return f, lines
        size -= 2
    f = font(fnt_kind, weight, min_size)
    return f, lines[:max_lines]


def _label(img, box, brand, name, size_label, p, align_top=False):
    """Paper label with brand, product name and size."""
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius=10 * S, fill=hex2rgb(p["label"]))
    d.line((x0 + 18 * S, y0 + 14 * S, x1 - 18 * S, y0 + 14 * S), fill=hex2rgb(p["accent"]), width=3 * S)
    cx = (x0 + x1) / 2
    inner = (x1 - x0) - 40 * S
    fb = font(p["font"], 700, 26)
    btxt = brand.upper()
    # letter-spaced brand
    spaced = " ".join(btxt) if len(btxt) < 10 else btxt
    while d.textlength(spaced, font=fb) > inner and fb.size > 14 * S:
        fb = font(p["font"], 700, fb.size // S - 2)
    y = y0 + 28 * S
    d.text((cx, y), spaced, font=fb, fill=hex2rgb(p["primary"]), anchor="mt")
    y += fb.size + 12 * S
    fn, lines = _fit_lines(d, name, p["font"], 600, inner, 34, 16, max_lines=4)
    for line in lines:
        d.text((cx, y), line, font=fn, fill=hex2rgb(p["ink"]), anchor="mt")
        y += int(fn.size * 1.18)
    if size_label:
        fs = font("sans", 400, 20)
        d.text((cx, y1 - 22 * S), size_label, font=fs, fill=hex2rgb(p["ink"], 170), anchor="mb")
    return img


# ------------------------------------------------------------------ objects
def _dropper(img, p, brand, name, size_label):
    W = img.size[0]
    cx = W / 2
    bw, bh = W * .30, W * .40
    x0, y1 = cx - bw / 2, W * .875
    y0 = y1 - bh
    img = _shadow(img, (cx - bw * .65, y1 - 26 * S, cx + bw * .65, y1 + 30 * S))
    d = ImageDraw.Draw(img)
    # glass body (amber-ish tint from primary)
    body = mix(hex2rgb(p["primary"]), (255, 255, 255), .15)
    d.rounded_rectangle((x0, y0, x0 + bw, y1), radius=40 * S, fill=body)
    # shoulder + neck
    d.rounded_rectangle((cx - bw * .22, y0 - 40 * S, cx + bw * .22, y0 + 30 * S), radius=14 * S, fill=body)
    # collar (gold) and rubber bulb
    d.rounded_rectangle((cx - bw * .26, y0 - 110 * S, cx + bw * .26, y0 - 30 * S), radius=10 * S, fill=hex2rgb(p["accent"]))
    d.rounded_rectangle((cx - bw * .14, y0 - 250 * S, cx + bw * .14, y0 - 100 * S), radius=60 * S, fill=hex2rgb("#1b1b1f"))
    img = _highlight(img, (x0, y0, x0 + bw, y1), 30 * S)
    return _label(img, (x0 + 24 * S, y0 + bh * .22, x0 + bw - 24 * S, y1 - bh * .12), brand, name, size_label, p)


def _jar(img, p, brand, name, size_label):
    W = img.size[0]
    cx = W / 2
    jw, jh = W * .46, W * .26
    y1 = W * .875
    y0 = y1 - jh
    img = _shadow(img, (cx - jw * .6, y1 - 24 * S, cx + jw * .6, y1 + 34 * S))
    d = ImageDraw.Draw(img)
    body = hex2rgb(p["label"])
    d.rounded_rectangle((cx - jw / 2, y0, cx + jw / 2, y1), radius=34 * S, fill=body)
    d.ellipse((cx - jw / 2, y1 - 40 * S, cx + jw / 2, y1 + 20 * S), fill=mix(body, (0, 0, 0), .06))
    # lid
    lh = jh * .42
    d.rounded_rectangle((cx - jw / 2 - 6 * S, y0 - lh, cx + jw / 2 + 6 * S, y0 + 10 * S), radius=24 * S, fill=hex2rgb(p["primary"]))
    d.rectangle((cx - jw / 2 - 6 * S, y0 - 8 * S, cx + jw / 2 + 6 * S, y0 + 2 * S), fill=hex2rgb(p["accent"]))
    img = _highlight(img, (cx - jw / 2, y0 - lh, cx + jw / 2, y0), 14 * S)
    return _label(img, (cx - jw / 2 + 34 * S, y0 + 22 * S, cx + jw / 2 - 34 * S, y1 - 18 * S), brand, name, size_label, p)


def _sachet(img, p, brand, name, size_label):
    W = img.size[0]
    cx = W / 2
    sw, sh = W * .44, W * .58
    x0, y0 = cx - sw / 2, W * .20
    img = _shadow(img, (cx - sw * .55, y0 + sh - 20 * S, cx + sw * .55, y0 + sh + 40 * S), strength=70)
    sach = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(sach)
    d.rounded_rectangle((x0, y0, x0 + sw, y0 + sh), radius=22 * S, fill=hex2rgb(p["primary"]))
    # crimped edges
    for i in range(int(sw // (16 * S))):
        xx = x0 + 8 * S + i * 16 * S
        d.polygon([(xx, y0), (xx + 8 * S, y0 + 14 * S), (xx + 16 * S, y0)], fill=hex2rgb(p["bg1"]))
        d.polygon([(xx, y0 + sh), (xx + 8 * S, y0 + sh - 14 * S), (xx + 16 * S, y0 + sh)], fill=hex2rgb(p["bg1"]))
    # face illustration circle
    r = sw * .2
    d.ellipse((cx - r, y0 + sh * .14, cx + r, y0 + sh * .14 + 2 * r), fill=hex2rgb(p["label"], 235))
    fd = ImageDraw.Draw(sach)
    ey = y0 + sh * .14 + r * .85
    fd.arc((cx - r * .5, ey - 10 * S, cx - r * .15, ey + 10 * S), 200, 340, fill=hex2rgb(p["ink"]), width=3 * S)
    fd.arc((cx + r * .15, ey - 10 * S, cx + r * .5, ey + 10 * S), 200, 340, fill=hex2rgb(p["ink"]), width=3 * S)
    fd.arc((cx - r * .3, ey + r * .25, cx + r * .3, ey + r * .65), 20, 160, fill=hex2rgb(p["accent"]), width=4 * S)
    # slight tilt
    sach = sach.rotate(-4, resample=Image.BICUBIC, center=(cx, y0 + sh / 2))
    img = Image.alpha_composite(img, sach)
    img = _highlight(img, (x0, y0, x0 + sw, y0 + sh), 20 * S)
    return _label(img, (x0 + 40 * S, y0 + sh * .52, x0 + sw - 40 * S, y0 + sh * .9), brand, name, size_label, p)


def _bottle(img, p, brand, name, size_label, capsules=True):
    W = img.size[0]
    cx = W / 2
    bw, bh = W * .36, W * .46
    y1 = W * .875
    y0 = y1 - bh
    img = _shadow(img, (cx - bw * .62, y1 - 24 * S, cx + bw * .62, y1 + 32 * S))
    d = ImageDraw.Draw(img)
    body = hex2rgb(p["label"])
    d.rounded_rectangle((cx - bw / 2, y0, cx + bw / 2, y1), radius=46 * S, fill=body)
    d.rounded_rectangle((cx - bw * .32, y0 - 34 * S, cx + bw * .32, y0 + 20 * S), radius=12 * S, fill=body)
    # ribbed cap
    ch = 110 * S
    d.rounded_rectangle((cx - bw * .36, y0 - 34 * S - ch, cx + bw * .36, y0 - 26 * S), radius=14 * S, fill=hex2rgb(p["primary"]))
    for i in range(1, 14):
        xx = cx - bw * .36 + i * (bw * .72 / 14)
        d.line((xx, y0 - 30 * S - ch, xx, y0 - 30 * S), fill=mix(hex2rgb(p["primary"]), (0, 0, 0), .2), width=2 * S)
    # coloured band label
    d.rounded_rectangle((cx - bw / 2, y0 + bh * .16, cx + bw / 2, y1 - bh * .1), radius=8 * S, fill=hex2rgb(p["primary"]))
    img = _highlight(img, (cx - bw / 2, y0, cx + bw / 2, y1), 30 * S)
    img = _label(img, (cx - bw / 2 + 26 * S, y0 + bh * .22, cx + bw / 2 - 26 * S, y1 - bh * .16), brand, name, size_label, p)
    if capsules:
        d = ImageDraw.Draw(img)
        rnd = random.Random(name)
        for i in range(4):
            x = cx + (bw * .62 + i * 46 * S) * (1 if i % 2 else -1) * .9
            y = y1 + 4 * S - rnd.randint(0, 20) * S
            ang = rnd.randint(-40, 40)
            cap = Image.new("RGBA", (120 * S, 60 * S), (0, 0, 0, 0))
            cd = ImageDraw.Draw(cap)
            cd.rounded_rectangle((0, 0, 120 * S, 48 * S), radius=24 * S, fill=hex2rgb(p["accent"]))
            cd.rounded_rectangle((60 * S, 0, 120 * S, 48 * S), radius=24 * S, fill=mix(hex2rgb(p["accent"]), (255, 255, 255), .55))
            cd.rectangle((58 * S, 0, 64 * S, 48 * S), fill=hex2rgb(p["accent"]))
            cap = cap.rotate(ang, expand=True, resample=Image.BICUBIC)
            img.alpha_composite(cap, (int(x - cap.width / 2), int(y - cap.height / 2)))
    return img


def _tube(img, p, brand, name, size_label):
    W = img.size[0]
    cx = W / 2
    tw, th = W * .26, W * .58
    y1 = W * .875
    y0 = y1 - th
    img = _shadow(img, (cx - tw * .8, y1 - 24 * S, cx + tw * .8, y1 + 30 * S))
    d = ImageDraw.Draw(img)
    # pump bottle
    d.rounded_rectangle((cx - tw / 2, y0, cx + tw / 2, y1), radius=36 * S, fill=hex2rgb(p["label"]))
    d.rounded_rectangle((cx - tw * .25, y0 - 70 * S, cx + tw * .25, y0 + 10 * S), radius=10 * S, fill=hex2rgb(p["primary"]))
    d.rounded_rectangle((cx - tw * .08, y0 - 140 * S, cx + tw * .08, y0 - 60 * S), radius=6 * S, fill=hex2rgb(p["primary"]))
    d.rounded_rectangle((cx - tw * .08, y0 - 150 * S, cx + tw * .5, y0 - 118 * S), radius=10 * S, fill=hex2rgb(p["primary"]))
    d.rectangle((cx - tw / 2, y1 - th * .08, cx + tw / 2, y1 - th * .05), fill=hex2rgb(p["accent"]))
    img = _highlight(img, (cx - tw / 2, y0, cx + tw / 2, y1), 24 * S)
    return _label(img, (cx - tw / 2 + 16 * S, y0 + th * .18, cx + tw / 2 - 16 * S, y1 - th * .14), brand, name, size_label, p)


def _tea(img, p, brand, name, size_label):
    W = img.size[0]
    cx = W / 2
    bw, bh, dep = W * .42, W * .44, W * .10
    x0, y1 = cx - bw / 2 - dep / 3, W * .875
    y0 = y1 - bh
    img = _shadow(img, (x0 - 30 * S, y1 - 26 * S, x0 + bw + dep + 30 * S, y1 + 30 * S))
    d = ImageDraw.Draw(img)
    front = hex2rgb(p["primary"])
    side = mix(front, (0, 0, 0), .25)
    top = mix(front, (255, 255, 255), .25)
    d.polygon([(x0 + bw, y0), (x0 + bw + dep, y0 - dep * .6), (x0 + bw + dep, y1 - dep * .6), (x0 + bw, y1)], fill=side)
    d.polygon([(x0, y0), (x0 + dep, y0 - dep * .6), (x0 + bw + dep, y0 - dep * .6), (x0 + bw, y0)], fill=top)
    d.rectangle((x0, y0, x0 + bw, y1), fill=front)
    # leaves
    rnd = random.Random(name)
    for i in range(3):
        lx, ly = x0 + bw * (.25 + i * .25), y0 + bh * .16
        leaf = Image.new("RGBA", (90 * S, 50 * S), (0, 0, 0, 0))
        ImageDraw.Draw(leaf).ellipse((0, 0, 90 * S, 50 * S), fill=hex2rgb(p["accent"]))
        leaf = leaf.rotate(rnd.randint(-50, 50), expand=True, resample=Image.BICUBIC)
        img.alpha_composite(leaf, (int(lx - leaf.width / 2), int(ly - leaf.height / 2)))
    img = _label(img, (x0 + 30 * S, y0 + bh * .3, x0 + bw - 30 * S, y1 - bh * .08), brand, name, size_label, p)
    # loose tea cup beside
    d = ImageDraw.Draw(img)
    cxp, cyp, r = x0 - 30 * S, y1 - 30 * S, 80 * S
    d.ellipse((cxp - r, cyp - r * .35, cxp + r, cyp + r * .35), fill=hex2rgb(p["label"]))
    d.ellipse((cxp - r * .8, cyp - r * .25, cxp + r * .8, cyp + r * .2), fill=hex2rgb("#b9873f"))
    return img


def _powder(img, p, brand, name, size_label):
    return _jar(img, p, brand, name, size_label)


RENDERERS = {
    "serum": _dropper, "toner": _tube, "cleanser": _tube, "cream": _jar, "mask": _sachet,
    "capsules": _bottle, "tablets": _bottle, "gummies": lambda *a: _bottle(*a, capsules=False),
    "liquid": lambda *a: _bottle(*a, capsules=False), "powder": _powder, "tea": _tea,
    "other": lambda *a: _bottle(*a, capsules=False),
}


def render_product(name, brand, form="other", size_label="", country="default", seed=None):
    p = PALETTES.get(country, PALETTES["default"])
    img = _background(p, seed or name)
    img = RENDERERS.get(form, RENDERERS["other"])(img, p, brand, name, size_label)
    return img.resize((SIZE, SIZE), Image.LANCZOS).convert("RGB")


def render_banner(title, tagline, country, width=1600, height=700, text=True):
    """Wide brand banner; with text=False it is just the brand's colours (for pages that overlay their own text)."""
    p = PALETTES.get(country, PALETTES["default"])
    W, H = width * S, height * S
    img = Image.new("RGBA", (W, H), hex2rgb(p["bg2"]))
    grad = Image.new("RGBA", (W, 1))
    for x in range(W):
        grad.putpixel((x, 0), mix(hex2rgb(p["primary"]), hex2rgb(p["bg2"]), (x / W) ** .8))
    img = grad.resize((W, H))
    rnd = random.Random(title)
    for _ in range(5):
        r = rnd.randint(120, 380) * S
        cx, cy = rnd.randint(W // 3, W), rnd.randint(0, H)
        orb = Image.new("RGBA", (W, H), hex2rgb(p["label"], 0))
        ImageDraw.Draw(orb).ellipse((cx - r, cy - r, cx + r, cy + r), fill=hex2rgb(p["label"], 70))
        img = Image.alpha_composite(img, orb.filter(ImageFilter.GaussianBlur(50 * S)))
    if not text:
        return img.resize((width, height), Image.LANCZOS).convert("RGB")
    d = ImageDraw.Draw(img)
    f1 = font("serif" if country == "FR" else "sans", 700, 110)
    d.text((90 * S, H / 2 - 40 * S), title, font=f1, fill=(255, 255, 255, 255), anchor="ls")
    f2 = font("sans", 400, 36)
    d.text((94 * S, H / 2 + 40 * S), tagline, font=f2, fill=(255, 255, 255, 220), anchor="ls")
    return img.resize((width, height), Image.LANCZOS).convert("RGB")


def render_placeholder():
    p = PALETTES["default"]
    img = _background(p, "placeholder")
    d = ImageDraw.Draw(img)
    W = img.size[0]
    f = font("serif", 600, 60)
    d.text((W / 2, W / 2), "Delight Care Plus", font=f, fill=hex2rgb(p["primary"], 160), anchor="mm")
    return img.resize((800, 800), Image.LANCZOS).convert("RGB")


def render_promo(country, product_images, width=1600, height=600):
    """Slideshow banner: brand colours on the left (the site writes the text there),
    a fan of product photos on the right."""
    img = render_banner("promo", "", country, width, height, text=False).convert("RGBA")
    cards = product_images[:3]
    if not cards:
        return img.convert("RGB")
    size = int(height * 0.62)
    # (centre x as a share of width, centre y as a share of height, tilt) for up to three cards
    spots = [(0.74, 0.50, -4), (0.56, 0.56, 6), (0.89, 0.58, 8)][:len(cards)]
    order = sorted(range(len(cards)), key=lambda i: -spots[i][1] if i else 99)  # main card drawn last
    for i in order:
        cx, cy, tilt = spots[i]
        s = size if i == 0 else int(size * 0.82)
        card = cards[i].convert("RGB").resize((s, s), Image.LANCZOS).convert("RGBA")
        mask = Image.new("L", (s, s), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, s, s), radius=int(s * 0.08), fill=255)
        card.putalpha(mask)
        pad = int(s * 0.25)
        layer = Image.new("RGBA", (s + pad * 2, s + pad * 2), (0, 0, 0, 0))
        shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle((pad + 10, pad + 24, pad + s + 10, pad + s + 24),
                                                 radius=int(s * 0.08), fill=(0, 0, 0, 120))
        layer = Image.alpha_composite(layer, shadow.filter(ImageFilter.GaussianBlur(22)))
        layer.alpha_composite(card, (pad, pad))
        layer = layer.rotate(tilt, resample=Image.BICUBIC, expand=False)
        img.alpha_composite(layer, (int(width * cx - layer.size[0] / 2), int(height * cy - layer.size[1] / 2)))
    return img.convert("RGB")


# ------------------------------------------------------------------ infographics
# Product posters in the style shoppers see on marketplaces: the pack, a headline,
# ingredient call-outs with icons and a row of benefits. Text comes from the product's
# own details, so keep those accurate (no certification badges are drawn).
ICONS = {
    "leaf": 0xf06c, "droplet": 0xf043, "heart": 0xf004, "bolt": 0xf0e7, "shield": 0xf3ed, "brain": 0xf5dc,
    "bone": 0xf5d7, "seedling": 0xf4d8, "sun": 0xf185, "moon": 0xf186, "capsules": 0xf46b, "flask": 0xf0c3,
    "eye": 0xf06e, "run": 0xf70c, "spa": 0xf5bb, "fire": 0xf06d, "mars": 0xf222, "venus": 0xf221,
    "lungs": 0xf604, "bed": 0xf236, "lemon": 0xf094, "fish": 0xf578, "atom": 0xf5d2, "care": 0xf4be,
    "wand": 0xe2ca, "feather": 0xf52d, "dna": 0xf471, "mortar": 0xf5a7, "scale": 0xf24e, "hourglass": 0xf252,
    "sparkles": 0xe2ca, "star": 0xf005, "mug": 0xf7b6, "apple": 0xf5d1, "gem": 0xf3a5, "hand": 0xf256,
    "check": 0xf058, "vial": 0xf492, "wheat": 0xe2cd,
}
# Words in a benefit or ingredient → the icon that suits it (first match wins)
ICON_WORDS = [
    (("liver", "detox", "thistle", "dandelion"), "leaf"), (("hydrat", "moist", "hyaluron", "water", "dry"), "droplet"),
    (("heart", "omega", "coq10", "circulat", "cholesterol"), "heart"), (("energy", "vitality", "stamina", "nmn", "maca"), "bolt"),
    (("immun", "defen", "protect", "zinc", "antioxid", "glutathione"), "shield"), (("brain", "focus", "memory"), "brain"),
    (("joint", "bone", "calcium", "cartilage", "glucosamine", "chondroitin", "k2", "d3"), "bone"),
    (("digest", "gut", "probiotic", "berberine", "metabol"), "seedling"), (("spf", "sun"), "sun"),
    (("sleep", "calm", "stress", "magnesium", "ashwagandha", "relax"), "moon"), (("eye", "lutein"), "eye"),
    (("vitamin c", "citrus", "lemon"), "lemon"), (("fish", "dha", "epa"), "fish"), (("collagen", "elastic", "firm"), "dna"),
    (("bright", "glow", "radian", "even", "spot", "dull"), "sparkles"), (("hair", "nail", "biotin", "keratin"), "gem"),
    (("tea", "herbal", "ritual"), "mug"), (("weight", "slim", "shape"), "scale"), (("men", "prostate", "palmetto"), "mars"),
    (("women", "hormon"), "venus"), (("turmeric", "curcumin", "ginger", "extract", "root", "plant"), "mortar"),
    (("acne", "pore", "oil", "clear"), "spa"), (("ageing", "aging", "line", "wrinkle", "youth"), "hourglass"),
    (("gentle", "sensitive", "sooth"), "feather"), (("protein", "muscle"), "run"), (("skin", "complexion"), "spa"),
]


def icon_for(text, default="check"):
    t = text.lower()
    for words, icon in ICON_WORDS:
        # match at the start of a word, so "lightweight" doesn't count as "weight"
        if any(re.search(r"(?<![a-z])" + re.escape(w), t) for w in words):
            return icon
    return default


def _icon_font(size):
    return ImageFont.truetype(str(FONT_DIR / "fa-solid-900.ttf"), int(size * S))


def _wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for w in text.split():
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=fnt) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _contrast_with_white(rgb):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    lum = 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2])
    return 1.05 / (lum + 0.05)


def render_cutout(name, brand, form="other", size_label="", country="default"):
    """The pack on a transparent background, trimmed to its edges."""
    p = PALETTES.get(country, PALETTES["default"])
    canvas = Image.new("RGBA", (SIZE * S, SIZE * S), hex2rgb(p["bg1"], 0))
    img = RENDERERS.get(form, RENDERERS["other"])(canvas, p, brand, name, size_label)
    return img.crop(img.getbbox())


def render_infographic(name, brand, form="other", size_label="", country="default", callouts=(), badges=(),
                       kicker=""):
    """Square product poster. callouts: [(icon, title, text)] (up to 3); badges: [(icon, text)] (up to 3)."""
    p = PALETTES.get(country, PALETTES["default"])
    W = SIZE * S
    ink, primary, accent = hex2rgb(p["ink"]), hex2rgb(p["primary"]), hex2rgb(p["accent"])
    white = (255, 255, 255, 255)

    # Background: soft paper gradient, a few marble veins and a molecule network in the corner
    img = Image.new("RGBA", (W, W))
    grad = Image.new("RGBA", (1, W))
    for y in range(W):
        grad.putpixel((0, y), mix((255, 255, 255), hex2rgb(p["bg1"]), (y / W) ** .9))
    img = grad.resize((W, W))
    rnd = random.Random(name)
    veins = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    vd = ImageDraw.Draw(veins)
    for _ in range(6):
        x, y = rnd.randint(0, W), rnd.randint(0, W)
        pts = [(x, y)]
        for _ in range(8):
            x += rnd.randint(-160, 160) * S
            y += rnd.randint(40, 160) * S
            pts.append((x, y))
        vd.line(pts, fill=mix(hex2rgb(p["bg2"]), (120, 120, 120), .25)[:3] + (70,), width=2 * S, joint="curve")
    img = Image.alpha_composite(img, veins.filter(ImageFilter.GaussianBlur(2 * S)))
    net = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    nd = ImageDraw.Draw(net)
    nodes = [(rnd.randint(0, int(W * .22)), rnd.randint(int(W * .2), int(W * .75))) for _ in range(9)]
    for i, a in enumerate(nodes):
        for b in nodes[i + 1:i + 3]:
            nd.line((a, b), fill=primary[:3] + (55,), width=2 * S)
    for (x, y) in nodes:
        nd.ellipse((x - 7 * S, y - 7 * S, x + 7 * S, y + 7 * S), fill=accent[:3] + (110,))
    img = Image.alpha_composite(img, net)
    d = ImageDraw.Draw(img)

    # Headline
    margin = 56 * S
    fh, lines = _fit_lines(d, name.upper(), "sans", 700, W - 2 * margin, 64, 38, max_lines=2)
    y = 48 * S
    for line in lines:
        d.text((W / 2, y), line, font=fh, fill=ink, anchor="mt")
        y += int(fh.size * 1.08)
    sub = " · ".join(t for t in (size_label, kicker) if t).upper()
    if sub:
        fs = font("sans", 600, 22)
        d.text((W / 2, y + 18 * S), "  ".join(sub.split(" ")), font=fs, fill=primary, anchor="mt")
        y += fs.size + 18 * S
    top = y + 34 * S

    # Pack on the left with a glow and a podium
    strip_h = 190 * S
    area = (20 * S, top, int(W * .52), W - strip_h - 24 * S)
    glow = Image.new("RGBA", (W, W), hex2rgb(p["bg2"], 0))  # transparent in the glow colour, so the blur has no grey halo
    gx, gy = (area[0] + area[2]) / 2, (area[1] + area[3]) / 2
    gr = (area[2] - area[0]) * .48
    ImageDraw.Draw(glow).ellipse((gx - gr, gy - gr, gx + gr, gy + gr), fill=hex2rgb(p["bg2"], 200))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(40 * S)))
    d = ImageDraw.Draw(img)
    pod_y = area[3] - 40 * S
    d.ellipse((area[0] + 30 * S, pod_y - 34 * S, area[2] - 30 * S, pod_y + 34 * S), fill=mix(hex2rgb(p["bg2"]), (255, 255, 255), .45))
    pack = render_cutout(name, brand, form, size_label, country)
    scale = min((area[2] - area[0] - 10 * S) / pack.width, (area[3] - area[1] - 10 * S) / pack.height)
    pack = pack.resize((int(pack.width * scale), int(pack.height * scale)), Image.LANCZOS)
    px_, py_ = int(gx - pack.width / 2), int(pod_y - pack.height + 10 * S)
    img.alpha_composite(pack, (px_, py_))
    d = ImageDraw.Draw(img)

    # Call-out cards on the right, joined to the pack by dotted leader lines
    cards = list(callouts)[:3]
    if cards:
        cx0, cx1 = int(W * .53), W - margin + 24 * S
        avail = area[3] - top
        gap = 22 * S
        ch = int((avail - gap * (len(cards) - 1)) / len(cards))
        ch = min(ch, 250 * S)
        cy = top + (avail - (ch * len(cards) + gap * (len(cards) - 1))) / 2
        ft, fb, fi = font("sans", 700, 32), font("sans", 400, 23), _icon_font(40)
        for icon, title, text in cards:
            box = (cx0, cy, cx1, cy + ch)
            shadow = Image.new("RGBA", (W, W), (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle((box[0], box[1] + 10 * S, box[2], box[3] + 10 * S), radius=24 * S, fill=(0, 0, 0, 40))
            img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(14 * S)))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle(box, radius=24 * S, fill=(255, 255, 255, 240), outline=hex2rgb(p["bg2"]), width=2 * S)
            # leader line from the pack to the card
            lx0, ly = min(px_ + pack.width * .8, box[0] - 40 * S), cy + ch / 2
            for x in range(int(lx0), int(box[0]) - 6 * S, 14 * S):
                d.ellipse((x, ly - 2.5 * S, x + 5 * S, ly + 2.5 * S), fill=accent)
            d.ellipse((lx0 - 9 * S, ly - 9 * S, lx0 + 9 * S, ly + 9 * S), fill=white, outline=accent, width=4 * S)
            # icon disc
            r = 44 * S
            icx, icy = box[0] + 28 * S + r, cy + ch / 2
            d.ellipse((icx - r, icy - r, icx + r, icy + r), fill=hex2rgb(p["bg2"]))
            d.text((icx, icy), chr(ICONS.get(icon, ICONS["check"])), font=fi, fill=primary, anchor="mm")
            # words
            tx = icx + r + 22 * S
            tw = box[2] - tx - 24 * S
            tlines = _wrap(d, title, ft, tw)[:2]
            blines = _wrap(d, text, fb, tw)
            room = int((ch - 36 * S - len(tlines) * ft.size * 1.15) // (fb.size * 1.3))
            blines = blines[:max(room, 0)]
            block = len(tlines) * ft.size * 1.15 + len(blines) * fb.size * 1.3
            ty = cy + (ch - block) / 2
            for line in tlines:
                d.text((tx, ty), line, font=ft, fill=ink)
                ty += ft.size * 1.15
            for line in blines:
                d.text((tx, ty), line, font=fb, fill=mix(ink, (255, 255, 255), .25))
                ty += fb.size * 1.3
            cy += ch + gap

    # Benefit strip along the bottom, darkened until white text is easy to read (4.5:1)
    items = list(badges)[:3]
    sy0 = W - strip_h
    strip = primary
    while _contrast_with_white(strip) < 4.5:
        strip = mix(strip, ink, .15)
    d.rectangle((0, sy0, W, W), fill=strip)
    d.line((0, sy0, W, sy0), fill=accent, width=6 * S)
    if items:
        colw = W / len(items)
        fi, fl = _icon_font(34), font("sans", 600, 24)
        for i, (icon, label) in enumerate(items):
            cx = colw * i + colw / 2
            r = 38 * S
            cyy = sy0 + 30 * S + r
            d.ellipse((cx - r, cyy - r, cx + r, cyy + r), fill=white)
            d.text((cx, cyy), chr(ICONS.get(icon, ICONS["check"])), font=fi, fill=strip, anchor="mm")
            ly = cyy + r + 12 * S
            for line in _wrap(d, label, fl, colw - 50 * S)[:2]:
                d.text((cx, ly), line, font=fl, fill=white, anchor="mt")
                ly += fl.size * 1.15
            if i:
                d.line((colw * i, sy0 + 34 * S, colw * i, W - 34 * S), fill=(255, 255, 255, 60), width=2 * S)
    return img.resize((SIZE, SIZE), Image.LANCZOS).convert("RGB")
