from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("messages/", views.messages_api, name="messages"),
    path("send/", views.send, name="send"),
    path("inbox/", views.inbox_list, name="inbox_list"),
    path("inbox/<int:pk>/", views.inbox_thread, name="inbox_thread"),
    path("inbox/<int:pk>/reply/", views.inbox_reply, name="inbox_reply"),
    path("inbox/<int:pk>/status/", views.inbox_status, name="inbox_status"),
]
