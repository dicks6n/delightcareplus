from django.urls import path

from . import feeds, views

app_name = "marketing"

urlpatterns = [
    path("feeds/google.xml", feeds.google, name="feed_google"),
    path("feeds/meta.csv", feeds.meta, name="feed_meta"),
    path("feeds/tiktok.csv", feeds.tiktok, name="feed_tiktok"),
    path("go/<slug:slug>/", views.go, name="go"),
    path("unsubscribe/<str:token>/", views.unsubscribe, name="unsubscribe"),
]
