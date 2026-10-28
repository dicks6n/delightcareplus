from django.contrib import admin

from .models import Batch, Brand, Category, Concern, Department, Product, ProductImage, Review, StockAlert, Variant


class VariantInline(admin.TabularInline):
    model = Variant
    extra = 0


class ImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


class BatchInline(admin.TabularInline):
    model = Batch
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "category", "price", "stock", "is_active", "is_best_seller", "is_sample")
    list_filter = ("brand", "category__department", "category", "is_active", "is_sample", "form")
    list_editable = ("price", "stock", "is_active", "is_best_seller")
    search_fields = ("name", "sku", "description")
    filter_horizontal = ("concerns",)
    inlines = [VariantInline, ImageInline, BatchInline]


admin.site.register(Brand)
admin.site.register(Department)
admin.site.register(Category, list_display=("name", "department", "is_active"), list_filter=("department",))
admin.site.register(Concern)
admin.site.register(Review, list_display=("product", "user", "rating", "is_approved"), list_editable=("is_approved",))
admin.site.register(Batch, list_display=("code", "product", "expiry_date", "quantity"), search_fields=("code",))
admin.site.register(StockAlert, list_display=("product", "email", "notified_at"))
