"""Safaricom Daraja STK Push helpers."""
import base64
import logging
from datetime import datetime

import requests
from django.conf import settings

logger = logging.getLogger("orders")


def format_phone(phone):
    """Any Kenyan format → 2547XXXXXXXX / 2541XXXXXXXX. Returns '' if invalid."""
    digits = "".join(filter(str.isdigit, phone or ""))
    if digits.startswith("254"):
        digits = digits[3:]
    elif digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 9 and digits[0] in "71":
        return f"254{digits}"
    return ""


def _token():
    key, secret = settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET
    if not key or not secret:
        raise RuntimeError("M-Pesa keys are not configured (MPESA_CONSUMER_KEY / MPESA_CONSUMER_SECRET).")
    auth = base64.b64encode(f"{key}:{secret}".encode()).decode()
    r = requests.get(
        f"{settings.MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials",
        headers={"Authorization": f"Basic {auth}"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _account(account=None):
    """The PayBill/Till to charge. Defaults to the shop's; the Foundation can pass its own."""
    acc = {"shortcode": settings.MPESA_SHORTCODE, "passkey": settings.MPESA_PASSKEY,
           "party_b": settings.MPESA_PARTY_B, "transaction_type": settings.MPESA_TRANSACTION_TYPE}
    acc.update({k: v for k, v in (account or {}).items() if v})
    return acc


def _password(account=None):
    acc = _account(account)
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    raw = f"{acc['shortcode']}{acc['passkey']}{ts}"
    return base64.b64encode(raw.encode()).decode(), ts


def callback_url(base=None):
    url = base or settings.MPESA_CALLBACK_URL
    if settings.MPESA_CALLBACK_TOKEN:
        url += ("&" if "?" in url else "?") + "t=" + settings.MPESA_CALLBACK_TOKEN
    return url


def stk_push(phone, amount, reference, description, callback=None, account=None):
    """Returns {'ok': True, 'checkout_request_id', 'merchant_request_id'} or {'ok': False, 'error'}.

    `callback` overrides MPESA_CALLBACK_URL and `account` (shortcode/passkey/party_b/transaction_type)
    overrides the shop PayBill — the Foundation uses both.
    """
    try:
        acc = _account(account)
        password, ts = _password(account)
        payload = {
            "BusinessShortCode": acc["shortcode"],
            "Password": password,
            "Timestamp": ts,
            "TransactionType": acc["transaction_type"],
            "Amount": max(1, int(round(amount))),
            "PartyA": phone,
            "PartyB": acc["party_b"],
            "PhoneNumber": phone,
            "CallBackURL": callback_url(callback),
            "AccountReference": reference[:12],
            "TransactionDesc": description[:13],
        }
        r = requests.post(
            f"{settings.MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers={"Authorization": f"Bearer {_token()}"},
            timeout=30,
        )
        data = r.json()
        if r.status_code == 200 and str(data.get("ResponseCode")) == "0":
            return {"ok": True, "checkout_request_id": data["CheckoutRequestID"],
                    "merchant_request_id": data.get("MerchantRequestID", "")}
        return {"ok": False, "error": data.get("errorMessage") or data.get("ResponseDescription") or "M-Pesa rejected the request."}
    except Exception as exc:  # network, config, bad JSON
        logger.exception("STK push failed")
        return {"ok": False, "error": str(exc) if settings.DEBUG else "Could not reach M-Pesa. Please try again."}


def stk_query(checkout_request_id, account=None):
    """Returns {'status': 'paid'|'pending'|'failed', 'desc': str, 'receipt': str}."""
    try:
        password, ts = _password(account)
        r = requests.post(
            f"{settings.MPESA_BASE_URL}/mpesa/stkpushquery/v1/query",
            json={"BusinessShortCode": _account(account)["shortcode"], "Password": password,
                  "Timestamp": ts, "CheckoutRequestID": checkout_request_id},
            headers={"Authorization": f"Bearer {_token()}"},
            timeout=30,
        )
        data = r.json()
        code = str(data.get("ResultCode", ""))
        if code == "0":
            return {"status": "paid", "desc": data.get("ResultDesc", ""), "receipt": ""}
        if code in ("", "1037") or "processed" in str(data.get("errorMessage", "")).lower():
            return {"status": "pending", "desc": data.get("ResultDesc", "Waiting for PIN"), "receipt": ""}
        return {"status": "failed", "desc": data.get("ResultDesc", "Payment failed"), "receipt": ""}
    except Exception:
        logger.exception("STK query failed")
        return {"status": "pending", "desc": "Still checking…", "receipt": ""}
