from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class Post(models.Model):
    TOPICS = (
        ("skincare", "Skincare"),
        ("supplements", "Supplements"),
        ("nutrition", "Nutrition"),
        ("tea", "Tea & Rituals"),
        ("wellness", "Wellness"),
        ("news", "Brand News"),
    )

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    topic = models.CharField(max_length=20, choices=TOPICS, default="wellness")
    excerpt = models.CharField(max_length=300, blank=True)
    body = models.TextField()
    cover = models.ImageField(upload_to="blog/", blank=True, null=True)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    related_products = models.ManyToManyField("catalog.Product", blank=True)
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(default=timezone.now)
    views = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-published_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:200] or "post"
            slug, n = base, 2
            while Post.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("blog:detail", args=[self.slug])

    @property
    def read_minutes(self):
        return max(1, len(self.body.split()) // 200)
