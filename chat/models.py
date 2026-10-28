from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Conversation(models.Model):
    STATUS_CHOICES = (("open", "Open"), ("closed", "Resolved"))

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="conversations")
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    guest_name = models.CharField(max_length=100, blank=True)
    guest_contact = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="open")
    page_url = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-last_message_at"]

    def __str__(self):
        return f"Chat with {self.display_name}"

    @property
    def display_name(self):
        if self.user_id:
            return self.user.get_full_name() or self.user.username
        return self.guest_name or "Guest"

    @property
    def contact(self):
        if self.user_id:
            phone = getattr(getattr(self.user, "profile", None), "phone", "")
            return " · ".join(x for x in [self.user.email, phone] if x)
        return self.guest_contact


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_staff = models.BooleanField(default=False)
    body = models.TextField(max_length=1000)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def as_dict(self):
        local = timezone.localtime(self.created_at)
        return {
            "id": self.id,
            "body": self.body,
            "is_staff": self.is_staff,
            "sender": (self.sender.first_name or self.sender.username) if (self.is_staff and self.sender) else "",
            "time": local.strftime("%H:%M"),
            "date": local.strftime("%b %d"),
            "is_read": self.is_read,
        }
