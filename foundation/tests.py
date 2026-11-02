import json
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Campaign, Donation


@override_settings(MPESA_CALLBACK_TOKEN="secret")
class DonationFlowTests(TestCase):
    def setUp(self):
        self.c = Campaign.objects.create(title="Help Amina", summary="s", story="Story", beneficiary="Amina",
                                         goal=10000, status="ACTIVE")

    def _donate(self, **extra):
        data = {"amount": 500, "name": "Jane Doe", "phone": "0712345678", "email": "j@example.com",
                "method": "mpesa", **extra}
        with mock.patch("orders.mpesa.stk_push", return_value={"ok": True, "checkout_request_id": "ws_CO_1",
                                                               "merchant_request_id": "m1"}) as stk:
            r = self.client.post(reverse("foundation:donate", args=[self.c.slug]), data)
        return r, stk

    def _callback(self, code=0, amount=500, token="secret"):
        body = {"Body": {"stkCallback": {"CheckoutRequestID": "ws_CO_1", "ResultCode": code, "ResultDesc": "x",
                "CallbackMetadata": {"Item": [{"Name": "Amount", "Value": amount},
                                              {"Name": "MpesaReceiptNumber", "Value": "SKL123"}]}}}}
        return self.client.post(reverse("foundation:mpesa_callback") + f"?t={token}", json.dumps(body),
                                content_type="application/json")

    def test_mpesa_donation_end_to_end(self):
        r, stk = self._donate()
        d = Donation.objects.get()
        self.assertRedirects(r, reverse("foundation:pay", args=[d.reference]))
        self.assertEqual(stk.call_args.args[0], "254712345678")
        self.assertIn("/foundation/mpesa/callback/", stk.call_args.kwargs["callback"])
        self.assertEqual(self._callback().status_code, 200)
        d.refresh_from_db(); self.c.refresh_from_db()
        self.assertEqual((d.status, d.payment_reference), ("PAID", "SKL123"))
        self.assertEqual((self.c.raised, self.c.donor_count), (500, 1))
        self._callback()  # duplicate callbacks are ignored
        self.c.refresh_from_db()
        self.assertEqual(self.c.raised, 500)
        self.assertEqual(self.client.get(reverse("foundation:pay_status", args=[d.reference])).json()["status"], "paid")

    def test_wrong_token_rejected(self):
        self._donate()
        self.assertEqual(self._callback(token="bad").status_code, 403)
        self.assertEqual(Donation.objects.get().status, "PENDING")

    def test_failed_payment(self):
        self._donate()
        self._callback(code=1032)
        self.assertEqual(Donation.objects.get().status, "FAILED")
        self.c.refresh_from_db()
        self.assertEqual(self.c.raised, 0)

    def test_shop_callback_forwards_donations(self):
        self._donate()
        body = {"Body": {"stkCallback": {"CheckoutRequestID": "ws_CO_1", "ResultCode": 0, "CallbackMetadata": {
            "Item": [{"Name": "Amount", "Value": 500}, {"Name": "MpesaReceiptNumber", "Value": "R1"}]}}}}
        self.client.post("/orders/mpesa/callback/?t=secret", json.dumps(body), content_type="application/json")
        self.assertEqual(Donation.objects.get().status, "PAID")

    def test_validation(self):
        r, stk = self._donate(phone="123")
        self.assertFalse(Donation.objects.exists())
        stk.assert_not_called()
        self._donate(amount=1)
        self.assertFalse(Donation.objects.exists())

    def test_closed_and_pending_campaigns(self):
        self.c.status = "CLOSED"; self.c.save()
        self._donate()
        self.assertFalse(Donation.objects.exists())
        self.c.status = "PENDING"; self.c.save()
        self.assertEqual(self.client.get(self.c.get_absolute_url()).status_code, 404)

    def test_other_people_cannot_see_donation(self):
        self._donate()
        d = Donation.objects.get()
        self.client.logout(); self.client.cookies.clear()
        self.assertEqual(self.client.get(reverse("foundation:pay", args=[d.reference])).status_code, 404)

    def test_airtel_then_staff_confirm(self):
        self._donate(method="airtel", phone="")
        d = Donation.objects.get()
        self.client.post(reverse("foundation:airtel", args=[d.reference]), {"reference": "AT123456"})
        d.refresh_from_db()
        self.assertEqual(d.status, "VERIFY")
        staff = User.objects.create_user("s", password="pw12345678", is_staff=True)
        self.client.force_login(staff)
        self.client.post(reverse("dashboard:foundation_donation_action", args=[d.pk]), {"action": "confirm"})
        self.c.refresh_from_db()
        self.assertEqual(self.c.raised, 500)
        self.client.post(reverse("dashboard:foundation_donation_action", args=[d.pk]), {"action": "refund"})
        self.c.refresh_from_db()
        self.assertEqual(self.c.raised, 0)


class StartFundraiserTests(TestCase):
    def test_member_submits_and_staff_approves(self):
        u = User.objects.create_user("m", email="m@example.com", password="pw12345678")
        self.client.force_login(u)
        r = self.client.post(reverse("foundation:start"), {
            "title": "Fees for Tom", "category": "education", "beneficiary": "Tom", "goal": 20000,
            "summary": "s", "story": "story", "organiser_phone": "0712345678", "agree": "on"})
        self.assertRedirects(r, reverse("foundation:mine"))
        c = Campaign.objects.get()
        self.assertEqual((c.status, c.organiser, c.organiser_phone), ("PENDING", u, "254712345678"))
        self.assertEqual(self.client.get(c.get_absolute_url()).status_code, 200)  # owner preview
        staff = User.objects.create_user("s", password="pw12345678", is_staff=True)
        self.client.force_login(staff)
        for name in ("dashboard:foundation", "dashboard:foundation_donations", "dashboard:foundation_donation_add"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:foundation_campaign", args=[c.pk])).status_code, 200)
        self.client.post(reverse("dashboard:foundation_status", args=[c.pk]), {"status": "ACTIVE"})
        c.refresh_from_db()
        self.assertEqual(c.status, "ACTIVE")
        from django.core import mail
        self.assertTrue(any("live" in m.subject for m in mail.outbox))

    def test_pages_render(self):
        Campaign.objects.create(title="A", summary="s", story="x", beneficiary="b", goal=1000, status="ACTIVE",
                                video_url="https://youtu.be/dQw4w9WgXcQ", is_featured=True)
        for url in ("/", "/foundation/", "/foundation/about/", "/foundation/f/a/", "/sitemap.xml",
                    "/foundation/?category=medical&q=a&sort=raised"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertContains(self.client.get("/foundation/f/a/"), "youtube-nocookie.com/embed/dQw4w9WgXcQ")
