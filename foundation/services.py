"""Donation payments: M-Pesa STK push, callback handling and confirmation emails."""
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core import mail
from orders import mpesa

from .models import Donation

logger = logging.getLogger("orders")


def mpesa_account():
    """Foundation PayBill if configured, otherwise the shop's (see FOUNDATION_MPESA_* in settings)."""
    return {"shortcode": settings.FOUNDATION_MPESA_SHORTCODE, "passkey": settings.FOUNDATION_MPESA_PASSKEY,
            "party_b": settings.FOUNDATION_MPESA_PARTY_B,
            "transaction_type": settings.FOUNDATION_MPESA_TRANSACTION_TYPE}


def send_stk(donation):
    result = mpesa.stk_push(donation.phone, donation.amount, donation.reference, "Donation",
                            callback=settings.FOUNDATION_MPESA_CALLBACK_URL, account=mpesa_account())
    if result["ok"]:
        donation.checkout_request_id = result["checkout_request_id"]
        donation.merchant_request_id = result["merchant_request_id"]
        donation.result_desc = ""
        donation.status = "PENDING"
    else:
        donation.checkout_request_id = ""
        donation.result_desc = result["error"][:255]
    donation.save(update_fields=["checkout_request_id", "merchant_request_id", "result_desc", "status"])
    return result["ok"]


def query(donation):
    return mpesa.stk_query(donation.checkout_request_id, account=mpesa_account())


def mark_paid(donation, reference="", note=""):
    """Idempotent: marks the donation received, refreshes the fundraiser total and emails a thank-you."""
    with transaction.atomic():
        d = Donation.objects.select_for_update().get(pk=donation.pk)
        if d.status == "PAID":
            return d
        d.status = "PAID"
        d.paid_at = timezone.now()
        if reference:
            d.payment_reference = reference[:40]
        if note:
            d.result_desc = note[:255]
        d.save(update_fields=["status", "paid_at", "payment_reference", "result_desc"])
        d.campaign.refresh_totals()
    if d.email:
        mail.send(f"Thank you for your donation to {d.campaign.title}", "emails/donation_receipt.html",
                  {"donation": d, "campaign": d.campaign}, [d.email])
    organiser = d.campaign.organiser
    if organiser and organiser.email and organiser.email != d.email:
        mail.send(f"New donation: KES {d.amount:,} to {d.campaign.title}", "emails/donation_organiser.html",
                  {"donation": d, "campaign": d.campaign}, [organiser.email])
    return d


def mark_unpaid(donation, status="REFUNDED"):
    donation.status = status
    donation.save(update_fields=["status"])
    donation.campaign.refresh_totals()


def handle_callback(cb):
    """Process a Daraja stkCallback dict. Returns True if it belonged to a donation."""
    donation = Donation.objects.filter(checkout_request_id=cb.get("CheckoutRequestID") or "-").first()
    if not donation:
        return False
    if donation.is_paid:
        return True
    if str(cb.get("ResultCode")) == "0":
        meta = {i.get("Name"): i.get("Value") for i in cb.get("CallbackMetadata", {}).get("Item", [])}
        try:
            amount = int(float(meta.get("Amount", 0)))
        except (TypeError, ValueError):
            amount = 0
        receipt = str(meta.get("MpesaReceiptNumber", ""))
        if amount and amount != donation.amount:
            # Count what actually arrived, not what was pledged.
            donation.amount = amount
            donation.save(update_fields=["amount"])
        mark_paid(donation, reference=receipt, note=f"M-Pesa receipt {receipt}")
    else:
        donation.status = "FAILED"
        donation.result_desc = str(cb.get("ResultDesc", "Payment was not completed"))[:255]
        donation.save(update_fields=["status", "result_desc"])
    return True
