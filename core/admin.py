from django.contrib import admin

from .models import Banner, ContactMessage, NewsletterSubscriber, SiteSettings, Testimonial

admin.site.register(SiteSettings)
admin.site.register(Banner, list_display=("title", "sort_order", "is_active"))
admin.site.register(Testimonial)
admin.site.register(ContactMessage, list_display=("name", "subject", "is_handled", "created_at"))
admin.site.register(NewsletterSubscriber, list_display=("email", "is_active", "created_at"))
