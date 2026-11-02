"""Delight Care Plus Foundation — public fundraising pages."""
import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core import mail
from core.models import SiteSettings

from . import services
from .forms import CampaignForm, DonateForm, UpdateForm
from .models import Campaign, Donation

logger = logging.getLogger("orders")

PRESETS = [200, 500, 1000, 2500, 5000]
SESSION_DONATIONS = "my_donations"


def _live():
    return Campaign.objects.filter(status__in=("ACTIVE", "CLOSED"))


def _remember(request, donation):
    refs = request.session.get(SESSION_DONATIONS, [])
    if donation.reference not in refs:
        request.session[SESSION_DONATIONS] = (refs + [donation.reference])[-30:]


def _own_donation(request, reference):
    """Donors can only open their own donation pages (same browser session or same account)."""
    d = get_object_or_404(Donation.objects.select_related("campaign"), reference=reference)
    if (reference in request.session.get(SESSION_DONATIONS, []) or request.user.is_staff
            or (request.user.is_authenticated and d.user_id == request.user.id)):
        return d
    raise Http404


def home(request):
    qs = _live().filter(status="ACTIVE")
    cat = request.GET.get("category", "")
    q = request.GET.get("q", "").strip()
    if cat:
        qs = qs.filter(category=cat)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(summary__icontains=q) | Q(beneficiary__icontains=q)
                       | Q(location__icontains=q))
    sort = request.GET.get("sort", "")
    qs = qs.order_by({"new": "-created_at", "raised": "-raised", "popular": "-donor_count"}.get(sort, "-is_featured"),
                     "-created_at")
    page = Paginator(qs, 12).get_page(request.GET.get("page"))

    totals = Donation.objects.filter(status="PAID").aggregate(total=Sum("amount"), n=Count("id"))
    featured = _live().filter(status="ACTIVE", is_featured=True).first()
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "foundation/home.html", {
        "page_obj": page, "featured": featured if not (cat or q or request.GET.get("page")) else None,
        "categories": Campaign.CATEGORY_CHOICES, "category": cat, "q": q, "sort": sort,
        "querystring": params.urlencode(),
        "stats": {"raised": totals["total"] or 0, "donations": totals["n"] or 0,
                  "funded": _live().filter(raised__gte=1).count(),
                  "completed": Campaign.objects.filter(status="CLOSED").count()},
        "completed": Campaign.objects.filter(status="CLOSED").order_by("-updated_at")[:3],
    })


def about(request):
    return render(request, "foundation/about.html")


def campaign(request, slug):
    c = get_object_or_404(Campaign, slug=slug)
    is_owner = request.user.is_authenticated and (request.user.is_staff or c.organiser_id == request.user.id)
    if c.status not in ("ACTIVE", "CLOSED") and not is_owner:
        raise Http404
    donations = c.donations.filter(status="PAID")
    initial = {"method": "mpesa"}
    if request.user.is_authenticated:
        initial["name"] = request.user.get_full_name() or request.user.username
        initial["email"] = request.user.email
    return render(request, "foundation/campaign.html", {
        "c": c, "is_owner": is_owner,
        "recent": donations.order_by("-paid_at")[:8],
        "top": donations.order_by("-amount", "paid_at")[:3],
        "words": donations.exclude(message="").order_by("-paid_at")[:10],
        "updates": c.updates.all(),
        "form": DonateForm(initial=initial), "presets": PRESETS, "min_donation": settings.FOUNDATION_MIN_DONATION,
        "update_form": UpdateForm() if is_owner else None,
        "share_url": request.build_absolute_uri(c.get_absolute_url()),
        "more": _live().filter(status="ACTIVE").exclude(pk=c.pk).order_by("?")[:3],
    })


@require_POST
def donate(request, slug):
    c = get_object_or_404(Campaign, slug=slug)
    if not c.is_open:
        messages.error(request, "This fundraiser is no longer taking donations. Thank you for your kindness!")
        return redirect(c)
    form = DonateForm(request.POST)
    if not form.is_valid():
        for errs in form.errors.values():
            messages.error(request, errs[0])
        return redirect(c.get_absolute_url() + "#donate")
    d = form.cleaned_data
    donation = Donation.objects.create(
        campaign=c, user=request.user if request.user.is_authenticated else None,
        amount=d["amount"], name=d["name"].strip(), email=d.get("email", ""), phone=d.get("phone", ""),
        message=d.get("message", "").strip(), is_anonymous=d.get("is_anonymous", False), method=d["method"],
    )
    _remember(request, donation)
    if donation.method == "mpesa":
        services.send_stk(donation)
    return redirect("foundation:pay", reference=donation.reference)


def pay(request, reference):
    d = _own_donation(request, reference)
    if d.is_paid:
        return redirect("foundation:thanks", reference=d.reference)
    return render(request, "foundation/pay.html", {"d": d, "c": d.campaign,
                                                   "airtel_number": SiteSettings.load().airtel_money_number or settings.AIRTEL_MONEY_NUMBER})


@require_POST
def pay_retry(request, reference):
    d = _own_donation(request, reference)
    if d.is_paid:
        return redirect("foundation:thanks", reference=d.reference)
    from orders.mpesa import format_phone
    phone = format_phone(request.POST.get("phone", "")) or d.phone
    if not phone:
        messages.error(request, "Enter a valid Safaricom number.")
        return redirect("foundation:pay", reference=d.reference)
    d.phone, d.method = phone, "mpesa"
    d.save(update_fields=["phone", "method"])
    if services.send_stk(d):
        messages.success(request, "New M-Pesa prompt sent — check your phone.")
    else:
        messages.error(request, d.result_desc or "Could not send the M-Pesa prompt.")
    return redirect("foundation:pay", reference=d.reference)


def pay_status(request, reference):
    d = _own_donation(request, reference)
    thanks = reverse("foundation:thanks", args=[d.reference])
    if d.is_paid:
        return JsonResponse({"status": "paid", "redirect": thanks})
    if d.status == "FAILED":
        return JsonResponse({"status": "failed", "message": d.result_desc or "Payment was not completed."})
    if request.GET.get("query") and d.checkout_request_id:
        res = services.query(d)
        if res["status"] == "paid":
            services.mark_paid(d, note="Confirmed by M-Pesa status check")
            return JsonResponse({"status": "paid", "redirect": thanks})
        if res["status"] == "failed":
            d.status, d.result_desc = "FAILED", res["desc"][:255]
            d.save(update_fields=["status", "result_desc"])
            return JsonResponse({"status": "failed", "message": d.result_desc})
    return JsonResponse({"status": "pending", "message": d.result_desc or "Waiting for you to enter your M-Pesa PIN…"})


@require_POST
def airtel_submit(request, reference):
    d = _own_donation(request, reference)
    ref = request.POST.get("reference", "").strip()
    if d.is_paid:
        return redirect("foundation:thanks", reference=d.reference)
    if len(ref) < 6:
        messages.error(request, "Enter the transaction ID from your Airtel Money SMS.")
        return redirect("foundation:pay", reference=d.reference)
    d.method, d.status, d.payment_reference = "airtel", "VERIFY", ref[:40]
    d.save(update_fields=["method", "status", "payment_reference"])
    if settings.ADMIN_EMAILS:
        mail.send(f"Airtel donation to confirm: {d.reference} (KES {d.amount:,})", "emails/donation_admin.html",
                  {"donation": d, "campaign": d.campaign}, settings.ADMIN_EMAILS)
    messages.success(request, "Thank you! We'll confirm your Airtel Money donation shortly.")
    return redirect("foundation:thanks", reference=d.reference)


def thanks(request, reference):
    d = _own_donation(request, reference)
    return render(request, "foundation/thanks.html", {
        "d": d, "c": d.campaign, "share_url": request.build_absolute_uri(d.campaign.get_absolute_url())})


@csrf_exempt
@require_POST
def mpesa_callback(request):
    token = settings.MPESA_CALLBACK_TOKEN
    if token and not constant_time_compare(request.GET.get("t", ""), token):
        logger.warning("Foundation M-Pesa callback with a wrong token from %s", request.META.get("REMOTE_ADDR"))
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Rejected"}, status=403)
    try:
        cb = json.loads(request.body).get("Body", {}).get("stkCallback", {})
    except (ValueError, AttributeError):
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Bad payload"})
    if not services.handle_callback(cb):
        logger.warning("Foundation M-Pesa callback for unknown request %s", cb.get("CheckoutRequestID"))
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


# ---------------------------------------------------------------------------
# Start / manage a fundraiser (members)
# ---------------------------------------------------------------------------
@login_required
def start(request):
    form = CampaignForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        c = form.save(commit=False)
        c.organiser = request.user
        c.organiser_name = request.user.get_full_name() or request.user.username
        c.status = "PENDING"
        c.save()
        if settings.ADMIN_EMAILS:
            mail.send(f"New fundraiser to review: {c.title}", "emails/fundraiser_submitted.html",
                      {"campaign": c}, settings.ADMIN_EMAILS)
        messages.success(request, "Thank you! Your fundraiser was sent to the Foundation team. "
                                  "We'll review it (usually within 2 working days) and let you know.")
        return redirect("foundation:mine")
    return render(request, "foundation/start.html", {"form": form})


@login_required
def mine(request):
    campaigns = Campaign.objects.filter(organiser=request.user)
    donations = Donation.objects.filter(user=request.user, status="PAID").select_related("campaign")
    return render(request, "foundation/mine.html", {"campaigns": campaigns, "donations": donations,
                                                    "active": "foundation"})


@login_required
@require_POST
def post_update(request, slug):
    c = get_object_or_404(Campaign, slug=slug)
    if not (request.user.is_staff or c.organiser_id == request.user.id):
        raise Http404
    form = UpdateForm(request.POST)
    if form.is_valid():
        u = form.save(commit=False)
        u.campaign, u.author = c, request.user
        u.save()
        messages.success(request, "Update posted.")
    else:
        messages.error(request, "Add a title and a message for your update.")
    return redirect(c.get_absolute_url() + "#updates")
