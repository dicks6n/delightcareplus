from django.contrib import admin

from .models import Coupon, DeliveryZone

admin.site.register(Coupon, list_display=("code", "discount_type", "value", "used_count", "is_active"))
admin.site.register(DeliveryZone, list_display=("name", "pickup_fee", "home_fee", "extra_kg_fee", "delivery_days"))
