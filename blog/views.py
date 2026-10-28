from django.core.paginator import Paginator
from django.db.models import F
from django.shortcuts import get_object_or_404, render

from .models import Post


def post_list(request):
    posts = Post.objects.filter(is_published=True)
    topic = request.GET.get("topic", "")
    if topic in dict(Post.TOPICS):
        posts = posts.filter(topic=topic)
    page = Paginator(posts, 9).get_page(request.GET.get("page"))
    return render(request, "blog/list.html", {"page_obj": page, "topic": topic, "topics": Post.TOPICS})


def post_detail(request, slug):
    post = get_object_or_404(Post, slug=slug, is_published=True)
    Post.objects.filter(pk=post.pk).update(views=F("views") + 1)
    more = Post.objects.filter(is_published=True, topic=post.topic).exclude(pk=post.pk)[:3]
    return render(request, "blog/detail.html", {
        "post": post,
        "products": post.related_products.filter(is_active=True).prefetch_related("variants"),
        "more": more,
    })
