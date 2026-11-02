"""Seller Center → Foundation: review fundraisers, confirm donations, export reports."""
from django import forms as djforms
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core import mail
from foundation import services
from foundation.models import Campaign, CampaignUpdate, Donation

from .forms import StyledMixin
from .views import _csv_response, _page, _qs_without_page, staff


class CampaignAdminForm(StyledMixin, djforms.ModelForm):
    class Meta:
        model = Campaign
        fields = ["title", "status", "category", "beneficiary", "location", "goal", "end_date",
                  "summary", "story", "cover", "video_url", "organiser_name", "organiser_phone",
                  "is_featured", "is_verified", "review_note"]
        widgets = {"story": djforms.Textarea(attrs={"rows": 10}), "summary": djforms.Textarea(attrs={"rows": 2}),
                   "end_date": djforms.DateInput(attrs={"type": "date"})}


class ManualDonationForm(StyledMixin, djforms.ModelForm):
    class Meta:
        model = Donation
        fields = ["campaign", "amount", "name", "phone", "email", "payment_reference", "message", "is_anonymous"]
        labels = {"payment_reference": "Reference (bank slip, cheque, cash receipt…)"}


@staff
def campaigns(request):
    tab = request.GET.get("tab", "all")
    qs = Campaign.objects.select_related("organiser")
    if tab != "all":
        qs = qs.filter(status=tab)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(beneficiary__icontains=q) | Q(organiser_name__icontains=q))
    counts = dict(Campaign.objects.values_list("status").annotate(n=Count("id")))
    tabs = [("all", "All", sum(counts.values()))] + [(k, v, counts.get(k, 0)) for k, v in Campaign.STATUS_CHOICES]

    paid = Donation.objects.filter(status="PAID")
    month = timezone.localdate().replace(day=1)
    kpi = {
        "raised": paid.aggregate(s=Sum("amount"))["s"] or 0,
        "month": paid.filter(paid_at__date__gte=month).aggregate(s=Sum("amount"))["s"] or 0,
        "donations": paid.count(),
        "live": counts.get("ACTIVE", 0),
        "review": counts.get("PENDING", 0),
        "verify": Donation.objects.filter(status="VERIFY").count(),
    }
    return render(request, "dashboard/foundation_campaigns.html", {
        "page_obj": _page(request, qs), "querystring": _qs_without_page(request), "tab": tab, "tabs": tabs,
        "kpi": kpi, "has_samples": Campaign.objects.filter(is_sample=True).exists()})


@staff
def campaign_edit(request, pk=None):
    obj = get_object_or_404(Campaign, pk=pk) if pk else None
    old_status = obj.status if obj else None
    form = CampaignAdminForm(request.POST or None, request.FILES or None, instance=obj,
                             initial=None if obj else {"status": "ACTIVE"})
    if request.method == "POST":
        if request.POST.get("delete") and obj:
            if obj.donations.filter(status="PAID").exists():
                messages.error(request, "This fundraiser has received donations, so it can't be deleted. Close it instead.")
                return redirect("dashboard:foundation_campaign", pk=obj.pk)
            obj.donations.all().delete()
            obj.delete()
            messages.success(request, "Fundraiser deleted.")
            return redirect("dashboard:foundation")
        if form.is_valid():
            c = form.save()
            if old_status == "PENDING" and c.status in ("ACTIVE", "REJECTED") and c.organiser and c.organiser.email:
                mail.send("Your fundraiser is live!" if c.status == "ACTIVE" else "About your fundraiser",
                          "emails/fundraiser_status.html", {"campaign": c}, [c.organiser.email])
            messages.success(request, f"Saved “{c}”.")
            return redirect("dashboard:foundation_campaign", pk=c.pk)
    ctx = {"form": form, "obj": obj}
    if obj:
        ctx["donations"] = obj.donations.all()[:15]
        ctx["updates"] = obj.updates.all()
    return render(request, "dashboard/foundation_campaign_form.html", ctx)


@staff
@require_POST
def campaign_status(request, pk):
    c = get_object_or_404(Campaign, pk=pk)
    status = request.POST.get("status")
    if status in dict(Campaign.STATUS_CHOICES):
        old, c.status = c.status, status
        if request.POST.get("review_note") is not None:
            c.review_note = request.POST["review_note"][:255]
        c.save(update_fields=["status", "review_note", "updated_at"])
        if old == "PENDING" and status in ("ACTIVE", "REJECTED") and c.organiser and c.organiser.email:
            mail.send("Your fundraiser is live!" if status == "ACTIVE" else "About your fundraiser",
                      "emails/fundraiser_status.html", {"campaign": c}, [c.organiser.email])
        messages.success(request, f"“{c}” is now {c.get_status_display().lower()}.")
    return redirect(request.POST.get("next") or "dashboard:foundation")


@staff
@require_POST
def update_delete(request, pk):
    u = get_object_or_404(CampaignUpdate, pk=pk)
    campaign_pk = u.campaign_id
    u.delete()
    messages.success(request, "Update removed.")
    return redirect("dashboard:foundation_campaign", pk=campaign_pk)


@staff
@require_POST
def delete_samples(request):
    samples = Campaign.objects.filter(is_sample=True)
    n = samples.count()
    Donation.objects.filter(campaign__in=samples).delete()
    samples.delete()
    messages.success(request, f"Removed {n} sample fundraiser{'s' if n != 1 else ''}.")
    return redirect("dashboard:foundation")


@staff
def donations(request):
    qs = Donation.objects.select_related("campaign")
    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)
    if request.GET.get("campaign"):
        qs = qs.filter(campaign_id=request.GET["campaign"])
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(reference__icontains=q) | Q(name__icontains=q) | Q(phone__icontains=q)
                       | Q(email__icontains=q) | Q(payment_reference__icontains=q))
    if request.GET.get("export") == "csv":
        return _csv_response("foundation-donations.csv",
                             ["Reference", "Date", "Fundraiser", "Donor", "Phone", "Email", "Amount (KES)", "Method",
                              "Status", "Payment ref", "Anonymous", "Message"],
                             [[d.reference, timezone.localtime(d.created_at).strftime("%Y-%m-%d %H:%M"), d.campaign.title,
                               d.name, d.phone, d.email, d.amount, d.get_method_display(), d.get_status_display(),
                               d.payment_reference, "yes" if d.is_anonymous else "", d.message] for d in qs])
    counts = dict(Donation.objects.values_list("status").annotate(n=Count("id")))
    tabs = [("", "All", sum(counts.values()))] + [(k, v, counts.get(k, 0)) for k, v in Donation.STATUS_CHOICES]
    return render(request, "dashboard/foundation_donations.html", {
        "page_obj": _page(request, qs, 40), "querystring": _qs_without_page(request), "status": status, "tabs": tabs,
        "campaigns": Campaign.objects.order_by("title").only("id", "title"),
        "total": qs.filter(status="PAID").aggregate(s=Sum("amount"))["s"] or 0})


@staff
@require_POST
def donation_action(request, pk):
    d = get_object_or_404(Donation, pk=pk)
    action = request.POST.get("action")
    if action == "confirm" and d.status != "PAID":
        services.mark_paid(d, note=f"Confirmed by {request.user.get_username()}")
        messages.success(request, f"{d.reference} confirmed. KES {d.amount:,} added to “{d.campaign}”.")
    elif action == "reject" and d.status != "PAID":
        services.mark_unpaid(d, status="FAILED")
        messages.success(request, f"{d.reference} marked as not received.")
    elif action == "refund" and d.status == "PAID":
        services.mark_unpaid(d, status="REFUNDED")
        messages.success(request, f"{d.reference} marked as refunded and removed from the total.")
    return redirect(request.POST.get("next") or "dashboard:foundation_donations")


@staff
def donation_add(request):
    form = ManualDonationForm(request.POST or None, initial={"campaign": request.GET.get("campaign")})
    if request.method == "POST" and form.is_valid():
        d = form.save(commit=False)
        d.method, d.status = "manual", "PENDING"
        d.save()
        services.mark_paid(d, note=f"Recorded by {request.user.get_username()}")
        messages.success(request, f"Donation of KES {d.amount:,} recorded for “{d.campaign}”.")
        return redirect("dashboard:foundation_donations")
    return render(request, "dashboard/foundation_donation_form.html", {"form": form})
