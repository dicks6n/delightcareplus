"""Create sample Foundation fundraisers so you can see the design. Remove them in Seller Center → Fundraisers."""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from foundation.models import Campaign, CampaignUpdate, Donation

SAMPLES = [
    {"title": "Help Grace finish her cancer treatment", "category": "medical", "beneficiary": "Grace W.",
     "location": "Nakuru", "goal": 450000, "featured": True, "verified": True, "days": 40, "raised": 0.62,
     "summary": "Grace, a 34-year-old mother of two, needs four more rounds of chemotherapy at Nakuru Level 5 Hospital.",
     "story": "Grace was diagnosed with breast cancer in March. Her family has already sold their dairy cow and used their savings to pay for surgery and the first rounds of chemotherapy.\n\nShe needs four more rounds, plus medicines and transport to the hospital. Her husband works as a boda boda rider and cannot cover the cost alone.\n\nEvery shilling goes towards her treatment bills, which the Foundation pays directly to the hospital."},
    {"title": "School fees for 20 bright girls in Kibera", "category": "education", "beneficiary": "Kibera Girls Mentorship",
     "location": "Nairobi", "goal": 600000, "verified": True, "days": 60, "raised": 0.38,
     "summary": "Keep 20 top-performing girls in secondary school for another year — fees, uniforms and sanitary pads.",
     "story": "These 20 girls scored top marks in KCPE but their families cannot afford secondary school fees.\n\nThe money covers one year of school fees, two uniforms each, and a year's supply of sanitary pads, so no girl misses class.\n\nThe mentorship group will post updates with term reports."},
    {"title": "Clean water tank for Kamuthi health centre", "category": "community", "beneficiary": "Kamuthi Health Centre",
     "location": "Kitui", "goal": 180000, "days": 30, "raised": 0.81,
     "summary": "A 10,000-litre tank and gutters so mothers giving birth at Kamuthi have clean water all year.",
     "story": "Kamuthi Health Centre serves about 6,000 people, but in the dry season nurses buy water from vendors to clean the delivery room.\n\nA 10,000-litre tank with gutters will collect rain from the roof and give the centre clean water all year."},
    {"title": "Dialysis for baby Brian", "category": "children", "beneficiary": "Brian O. (age 4)",
     "location": "Kisumu", "goal": 250000, "days": 25, "raised": 0.22,
     "summary": "Four-year-old Brian needs dialysis three times a week while he waits for a kidney transplant.",
     "story": "Brian was born with a kidney condition. He now needs dialysis three times a week at Jaramogi Oginga Odinga Teaching and Referral Hospital.\n\nHis parents travel two hours each way. Your gift covers sessions, medicines and fare for the next three months."},
    {"title": "Free skin & wellness clinic for elderly women", "category": "wellness", "beneficiary": "Thika Grandmothers Group",
     "location": "Thika", "goal": 90000, "days": 20, "raised": 0.47,
     "summary": "A one-day clinic with health checks, eye tests, sunscreen and vitamins for 150 grandmothers.",
     "story": "Many of the grandmothers in this group raise their grandchildren and rarely see a doctor.\n\nThe clinic will offer blood pressure and sugar checks, eye tests, skincare advice from the Delight Care Plus team, and a pack of sunscreen and multivitamins for each woman."},
    {"title": "Rebuild after the Mathare fire", "category": "emergency", "beneficiary": "Families of Mathare 4A",
     "location": "Nairobi", "goal": 300000, "days": 15, "raised": 0.55,
     "summary": "Mattresses, blankets, cooking sets and school uniforms for 35 families who lost everything in a fire.",
     "story": "A fire in Mathare 4A destroyed 35 homes last week. Families are sleeping in a church hall.\n\nWe are buying mattresses, blankets, cooking sets and replacement school uniforms so children can return to class."},
]
NAMES = ["Wanjiku", "Otieno", "Akinyi", "Kamau", "Achieng", "Mwangi", "Njeri", "Kiprotich", "Atieno", "Mutua",
         "Chebet", "Omondi", "Wambui", "Kariuki", "Nyambura", "Barasa"]
WORDS = ["Get well soon! 💚", "Praying for you and your family.", "Small but from the heart.", "Stay strong!",
         "Proud to support this.", "Tuko pamoja 🙏", "", "", ""]


class Command(BaseCommand):
    help = "Create sample Delight Care Plus Foundation fundraisers (marked as samples)."

    def handle(self, *args, **opts):
        if Campaign.objects.filter(is_sample=True).exists():
            self.stdout.write("Sample fundraisers already exist — nothing to do.")
            return
        rng = random.Random(7)
        now = timezone.now()
        for s in SAMPLES:
            c = Campaign.objects.create(
                title=s["title"], category=s["category"], beneficiary=s["beneficiary"], location=s["location"],
                goal=s["goal"], summary=s["summary"], story=s["story"], status="ACTIVE",
                is_featured=s.get("featured", False), is_verified=s.get("verified", False), is_sample=True,
                end_date=timezone.localdate() + timedelta(days=s["days"]))
            target, total = int(s["goal"] * s["raised"]), 0
            while total < target:
                amount = min(rng.choice([200, 500, 500, 1000, 1000, 2000, 2500, 5000, 10000]), target - total)
                if amount < 10:
                    break
                total += amount
                Donation.objects.create(
                    campaign=c, amount=amount, name=f"{rng.choice(NAMES)} {rng.choice('KMNOWAC')}.",
                    message=rng.choice(WORDS), is_anonymous=rng.random() < 0.15, method="manual", status="PAID",
                    paid_at=now - timedelta(hours=rng.randint(1, 24 * 20)), payment_reference="SAMPLE")
            c.refresh_totals()
            CampaignUpdate.objects.create(campaign=c, title="Thank you for the first donations!",
                                          body="We're overwhelmed by your kindness. We'll share news here as things move forward.")
        self.stdout.write(self.style.SUCCESS(f"Created {len(SAMPLES)} sample fundraisers."))
