# store/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Product, ProductVariant, Order, OrderItem, Category, BlogPost

# ============================================
# PRODUCT VARIANT INLINE
# ============================================

class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


# ============================================
# PRODUCT ADMIN - ONLY REGISTER ONCE
# ============================================

@admin.register(Product)  # ← This registers Product
class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductVariantInline]
    list_display = ('id', 'name', 'category', 'price', 'stock', 'is_active', 'is_featured', 'created_at')
    list_filter = ('category', 'is_active', 'is_featured', 'created_at')
    search_fields = ('name', 'description', 'category__name')
    list_editable = ('price', 'stock', 'is_active', 'is_featured')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'image', 'category')
        }),
        ('Pricing & Stock', {
            'fields': ('price', 'compare_price', 'stock')
        }),
        ('Status', {
            'fields': ('is_active', 'is_featured')
        }),
    )


# ============================================
# CATEGORY ADMIN
# ============================================

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug', 'icon', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('is_active',)


# ============================================
# BLOG POST ADMIN
# ============================================

@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'category', 'status', 'is_featured', 'views', 'created_at')
    list_filter = ('status', 'category', 'is_featured', 'created_at')
    search_fields = ('title', 'content', 'excerpt')
    prepopulated_fields = {'slug': ('title',)}
    list_editable = ('status', 'is_featured')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'category', 'excerpt')
        }),
        ('Content', {
            'fields': ('content', 'featured_image')
        }),
        ('Status', {
            'fields': ('status', 'is_featured', 'published_at')
        }),
        ('Author & Stats', {
            'fields': ('author', 'views'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('views', 'created_at', 'updated_at')


# ============================================
# ORDER ADMIN
# ============================================

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'name', 'phone', 'grand_total', 'status', 'mpesa_receipt_number', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'name', 'phone', 'utr_last6', 'mpesa_receipt_number')
    list_editable = ('status',)
    
    readonly_fields = ('payment_image_preview', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Customer Info', {
            'fields': ('user', 'name', 'phone', 'address')
        }),
        ('Order Details', {
            'fields': ('total_price', 'gst', 'grand_total', 'status')
        }),
        ('M-Pesa Payment Details', {
            'fields': ('checkout_request_id', 'merchant_request_id', 'mpesa_receipt_number', 'mpesa_result_code', 'mpesa_result_desc'),
            'classes': ('collapse',)
        }),
        ('Payment Proof', {
            'fields': ('utr_last6', 'payment_screenshot', 'payment_image_preview')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def payment_image_preview(self, obj):
        if obj.payment_screenshot:
            return format_html(
                '<img src="{}" width="200" style="border-radius: 8px;" />',
                obj.payment_screenshot.url
            )
        return "No Screenshot"
    payment_image_preview.short_description = "Screenshot Preview"
    
    actions = ['mark_as_paid', 'mark_as_processing', 'mark_as_shipped', 'mark_as_delivered', 'mark_as_cancelled']
    
    def mark_as_paid(self, request, queryset):
        updated = queryset.update(status='PAID')
        self.message_user(request, f'{updated} order(s) marked as Paid.')
    mark_as_paid.short_description = "Mark selected orders as Paid"
    
    def mark_as_processing(self, request, queryset):
        updated = queryset.update(status='PROCESSING')
        self.message_user(request, f'{updated} order(s) marked as Processing.')
    mark_as_processing.short_description = "Mark selected orders as Processing"
    
    def mark_as_shipped(self, request, queryset):
        updated = queryset.update(status='SHIPPED')
        self.message_user(request, f'{updated} order(s) marked as Shipped.')
    mark_as_shipped.short_description = "Mark selected orders as Shipped"
    
    def mark_as_delivered(self, request, queryset):
        updated = queryset.update(status='DELIVERED')
        self.message_user(request, f'{updated} order(s) marked as Delivered.')
    mark_as_delivered.short_description = "Mark selected orders as Delivered"
    
    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status='CANCELLED')
        self.message_user(request, f'{updated} order(s) marked as Cancelled.')
    mark_as_cancelled.short_description = "Mark selected orders as Cancelled"


# ============================================
# ORDER ITEM ADMIN
# ============================================

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'variant', 'quantity', 'price')
    list_filter = ('order__status',)
    search_fields = ('order__user__username', 'variant__product__name')


# ============================================
# PRODUCT VARIANT ADMIN
# ============================================

@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'size', 'price')
    list_filter = ('size', 'product')
    search_fields = ('product__name',)


# ============================================
# ❌ REMOVE THIS IF IT EXISTS - DUPLICATE!
# ============================================
# admin.site.register(Product, ProductAdmin)  # ← REMOVE THIS LINE