from django.contrib import admin

from .models import Order, OrderEvent, OrderItem, RefillReminder


class ItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


class EventInline(admin.TabularInline):
    model = OrderEvent
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("number", "full_name", "phone", "total", "payment_method", "status", "created_at")
    list_filter = ("status", "payment_method", "delivery_method", "created_at")
    search_fields = ("number", "full_name", "phone", "email", "payment_reference")
    readonly_fields = ("number", "created_at", "updated_at", "paid_at", "stock_deducted")
    inlines = [ItemInline, EventInline]


admin.site.register(RefillReminder, list_display=("product", "email", "due_on", "sent_at", "cancelled"))
