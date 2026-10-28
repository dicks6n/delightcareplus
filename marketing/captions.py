"""Ready-to-paste captions for an Ad Studio post, with a tracked link per platform.

Wording sticks to what the product page says (no promises to cure or treat anything), which keeps
ads in line with the Pharmacy and Poisons Board's rules for advertising health products.
"""
from marketing.views import with_utm

HASHTAGS = {
    "Supplements": "#SupplementsKenya #WellnessKenya #HealthyLivingKE #NairobiWellness",
    "Skincare": "#SkincareKenya #NairobiSkincare #GlowingSkin #KenyanBeauty",
    "Tea": "#HerbalTea #TeaLoversKenya #WellnessTea #NairobiLiving",
}
ALWAYS = "#DelightCarePlus #ShopKenya #MpesaAccepted"


def captions(product, base_url, offer="", coupon="", price_text="", whatsapp=""):
    dept = product.category.department.name if product.category else ""
    tags = f"{HASHTAGS.get(dept, '#WellnessKenya #BeautyKenya')} {ALWAYS}"
    link = base_url.rstrip("/") + product.get_absolute_url()
    campaign = f"adstudio-{product.slug}"[:100]
    links = {p: with_utm(link, p, "social", campaign) for p in ("instagram", "tiktok", "facebook", "whatsapp")}

    benefits = product.benefit_list[:3]
    ticks = "\n".join(f"✅ {b}" for b in benefits)
    hook = f"🔥 {offer} — " if offer else "✨ "
    code = f"\n🎟️ Use code {coupon} at checkout" if coupon else ""
    price = f"\n💰 {price_text}" if price_text else ""
    wa = f"\n📲 WhatsApp {whatsapp}" if whatsapp else ""
    size = f" ({product.size_label})" if product.size_label and product.size_label.lower() not in product.name.lower() else ""
    short = product.short_description or product.name

    instagram = (f"{hook}{product.name}{size}\n\n{short}\n\n{ticks}{price}{code}\n\n"
                 f"🚚 Delivery countrywide · 💳 Pay with M-Pesa\n🛍️ Tap the link in our bio to order{wa}\n\n{tags}")
    tiktok = (f"{hook}{product.name} {('· ' + offer) if offer else ''}\n{short}{code}\n"
              f"Order: link in bio · M-Pesa · delivery countrywide 🇰🇪\n{tags}").replace("  ", " ")
    facebook = (f"{hook}{product.name}{size}\n\n{short}\n\n{ticks}{price}{code}\n\n"
                f"🚚 We deliver countrywide · 💳 Pay with M-Pesa\n👉 Order here: {links['facebook']}{wa}")
    whatsapp_text = (f"*{product.name}*{size}\n{short}\n\n{ticks}{price}{code}\n\n"
                     f"🚚 Delivery countrywide · 💳 M-Pesa\n👉 Order: {links['whatsapp']}")
    return {
        "instagram": {"label": "Instagram", "icon": "fa-brands fa-instagram", "text": instagram, "link": links["instagram"]},
        "tiktok": {"label": "TikTok", "icon": "fa-brands fa-tiktok", "text": tiktok, "link": links["tiktok"]},
        "facebook": {"label": "Facebook", "icon": "fa-brands fa-facebook", "text": facebook, "link": links["facebook"]},
        "whatsapp": {"label": "WhatsApp Status / broadcast", "icon": "fa-brands fa-whatsapp", "text": whatsapp_text,
                     "link": links["whatsapp"]},
    }
