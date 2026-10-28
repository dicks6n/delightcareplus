from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from blog.models import Post
from catalog.models import Brand, Category, Concern, Department, Product


class ProductSitemap(Sitemap):
    changefreq, priority = "weekly", 0.9

    def items(self):
        return Product.objects.live().order_by("id")

    def lastmod(self, obj):
        return obj.updated_at


class ListingSitemap(Sitemap):
    changefreq, priority = "weekly", 0.7

    def items(self):
        return (list(Department.objects.filter(is_active=True)) + list(Category.objects.filter(is_active=True))
                + list(Brand.objects.all()) + list(Concern.objects.all()))


class PostSitemap(Sitemap):
    changefreq, priority = "monthly", 0.6

    def items(self):
        return Post.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.published_at


class PageSitemap(Sitemap):
    changefreq, priority = "monthly", 0.5

    def items(self):
        return ["core:home", "catalog:shop", "catalog:brands", "catalog:routine", "catalog:verify", "blog:list",
                "core:about", "core:faq", "core:contact"]

    def location(self, name):
        return reverse(name)


SITEMAPS = {"products": ProductSitemap, "listings": ListingSitemap, "journal": PostSitemap, "pages": PageSitemap}
