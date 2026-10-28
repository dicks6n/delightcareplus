from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import F, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from blog.models import Post
from catalog.models import Brand, Department, Product

from .models import Banner, ContactMessage, NewsletterSubscriber, Testimonial


def home(request):
    live = Product.objects.live().select_related("brand", "category").prefetch_related("variants", "images").with_ratings()
    recent_ids = request.session.get("recently_viewed", [])
    recently_viewed = sorted(live.filter(id__in=recent_ids), key=lambda p: recent_ids.index(p.id))[:4]

    # Photos the hero cycles through (Motion transitions on the home page)
    hero_pool = [{"img": p.showcase_image().url, "url": p.get_absolute_url(), "name": p.name}
                 for p in live.filter(Q(is_best_seller=True) | Q(is_featured=True)).exclude(image="")
                 .prefetch_related("images")[:9]]

    return render(request, "core/home.html", {
        "banners": Banner.objects.filter(is_active=True).exclude(image=""),
        "hero_pool": hero_pool,
        "departments": Department.objects.filter(is_active=True).prefetch_related("categories"),
        "brands": Brand.objects.filter(is_featured=True),
        "best_sellers": live.filter(is_best_seller=True)[:8],
        "new_arrivals": live.filter(is_new=True)[:8],
        "on_sale": live.filter(compare_price__gt=F("price"))[:4],
        "skincare": live.filter(category__department__slug="skincare")[:4],
        "teas": live.filter(category__department__slug="tea")[:4],
        "recently_viewed": recently_viewed,
        "testimonials": Testimonial.objects.filter(is_active=True)[:6],
        "posts": Post.objects.filter(is_published=True)[:3],
    })


def about(request):
    return render(request, "core/about.html", {"brands": Brand.objects.all()})


def faq(request):
    return render(request, "core/faq.html")


def policy(request, page):
    pages = {"delivery": "Delivery Information", "returns": "Returns & Refunds",
             "privacy": "Privacy Policy", "terms": "Terms & Conditions"}
    if page not in pages:
        return redirect("core:home")
    from cart.models import DeliveryZone
    return render(request, "core/policy.html", {"page": page, "title": pages[page],
                                                "zones": DeliveryZone.objects.filter(is_active=True)})


def contact(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()[:100]
        message = request.POST.get("message", "").strip()[:3000]
        email = request.POST.get("email", "").strip()[:254]
        if not name or not message:
            messages.error(request, "Please tell us your name and your message.")
        else:
            ContactMessage.objects.create(
                name=name, email=email, message=message,
                phone=request.POST.get("phone", "").strip()[:20],
                subject=request.POST.get("subject", "").strip()[:150],
            )
            messages.success(request, "Thanks! We'll get back to you within one working day. 💚")
            return redirect("core:contact")
    return render(request, "core/contact.html")


@require_POST
def newsletter(request):
    email = request.POST.get("email", "").strip().lower()
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"ok": False, "message": "Please enter a valid email address."})
    sub, created = NewsletterSubscriber.objects.get_or_create(email=email)
    if not created and sub.is_active:
        return JsonResponse({"ok": True, "message": "You're already in the Wellness Club 💚"})
    sub.is_active = True
    sub.save()
    return JsonResponse({"ok": True, "message": "Welcome to the Wellness Club! 🌿"})


def page_not_found(request, exception):
    return render(request, "404.html", status=404)


def server_error(request):
    return render(request, "500.html", status=500)
