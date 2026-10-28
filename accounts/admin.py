from django.contrib import admin

from .models import PointsTransaction, Profile, WishlistItem

admin.site.register(Profile, list_display=("user", "phone", "city"), search_fields=("user__username", "user__email", "phone"))
admin.site.register(WishlistItem)
admin.site.register(PointsTransaction, list_display=("user", "points", "reason", "created_at"))
