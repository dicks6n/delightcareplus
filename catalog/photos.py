"""Generated product photos: the infographic poster (main photo) and a clean studio shot (gallery)."""
import io

from django.core.files.base import ContentFile

from .imaging import icon_for, render_infographic, render_product
from .models import ProductImage


def auto_infographic(p):
    """Infographic text for a product without hand-written call-outs, built from its benefits and concerns."""
    lines = [l.strip() for l in p.benefits.splitlines() if l.strip()][:3]
    callouts = [(icon_for(l), l, "") for l in lines]
    if not callouts and p.short_description:
        callouts = [(icon_for(p.short_description), p.short_description, "")]
    badges = [(icon_for(c.name), c.name) for c in p.concerns.all()[:3]]
    if p.skin_type and len(badges) < 3:
        badges.append(("feather", p.skin_type))
    if len(badges) < 3:
        badges.append(("star", "Daily ritual"))
    dept = p.category.department.name if p.category else ""
    kicker = {"Supplements": "Food supplement", "Tea": "Herbal tea"}.get(dept, dept)
    return callouts, badges[:3], kicker


def _jpeg(img):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88, optimize=True)
    return ContentFile(buf.getvalue())


def make_photos(p, callouts=None, badges=None, kicker=None, studio=True):
    """Set the infographic as the main photo; add a studio shot as the first gallery photo.
    A main photo the shop uploaded itself is kept, moved into the gallery."""
    if callouts is None:
        callouts, badges, kicker = auto_infographic(p)
    code = p.brand.country_code if p.brand else "default"
    brand = p.brand.name if p.brand else ""
    if p.image:
        if p.image.name.split("/")[-1].startswith(p.slug):
            p.image.delete(save=False)  # an older generated poster
        else:
            # their own photo: keep it, as the first gallery photo
            ProductImage.objects.create(product=p, image=p.image.name, alt=p.name, sort_order=0)
    p.image.save(f"{p.slug}.jpg", _jpeg(render_infographic(p.name, brand, p.form, p.size_label, code,
                                                            callouts, badges, kicker)), save=True)
    if studio and not p.images.filter(alt__endswith="studio photo").exists():
        photo = ProductImage(product=p, alt=f"{p.name} studio photo", sort_order=0)
        photo.image.save(f"{p.slug}-studio.jpg", _jpeg(render_product(p.name, brand, p.form, p.size_label, code)), save=True)
