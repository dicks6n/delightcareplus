from django.contrib import admin

from .models import Campaign, CampaignUpdate, Donation


class UpdateInline(admin.StackedInline):
    model = CampaignUpdate
    extra = 0


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "category", "goal", "raised", "donor_count", "is_featured", "created_at")
    list_filter = ("status", "category", "is_featured", "is_verified")
    search_fields = ("title", "beneficiary", "organiser_name")
    readonly_fields = ("raised", "donor_count")
    inlines = [UpdateInline]


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ("reference", "campaign", "name", "amount", "method", "status", "payment_reference", "created_at")
    list_filter = ("status", "method")
    search_fields = ("reference", "name", "phone", "email", "payment_reference")
    readonly_fields = ("reference", "checkout_request_id", "merchant_request_id")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.campaign.refresh_totals()
