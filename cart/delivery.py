"""Find the delivery zone for a town and price a parcel."""
from decimal import Decimal

from .models import DeliveryZone

SESSION_KEY = "delivery"   # {"city": "...", "method": "pickup"|"home"}


def zone_for(city):
    if not city:
        return None
    city_l = city.strip().lower()
    zones = list(DeliveryZone.objects.filter(is_active=True))
    for zone in zones:
        if city_l in (t.lower() for t in zone.town_list):
            return zone
    # Partial match, e.g. "Nairobi" → "Nairobi CBD", "Nakuru town" → "Nakuru"
    if len(city_l) >= 4:
        for zone in zones:
            for t in zone.town_list:
                t = t.lower()
                if len(t) >= 4 and (t in city_l or city_l in t):
                    return zone
    # Unknown town → the last zone (rest of Kenya)
    return DeliveryZone.objects.filter(is_active=True).order_by("-sort_order").first()


def all_towns():
    """[(zone, [towns])] for the checkout dropdown."""
    return [(z, z.town_list) for z in DeliveryZone.objects.filter(is_active=True)]


def quote_table():
    """Cheapest prices per zone, for the delivery info page."""
    return DeliveryZone.objects.filter(is_active=True)


def get_choice(session):
    data = session.get(SESSION_KEY, {})
    method = data.get("method") if data.get("method") in ("pickup", "home") else "home"
    return data.get("city", ""), method


def set_choice(session, city, method):
    session[SESSION_KEY] = {"city": city[:80], "method": method if method in ("pickup", "home") else "home"}
    session.modified = True


def cheapest_fee():
    zone = DeliveryZone.objects.filter(is_active=True).order_by("pickup_fee").first()
    return min(zone.pickup_fee, zone.home_fee) if zone else Decimal("0")
