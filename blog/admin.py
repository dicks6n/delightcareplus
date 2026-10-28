from django.contrib import admin

from .models import Post

admin.site.register(Post, list_display=("title", "topic", "is_published", "published_at"), prepopulated_fields={"slug": ("title",)})
