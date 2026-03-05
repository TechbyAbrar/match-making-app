#call/models.py
import uuid
from django.conf import settings
from django.db import models

class Call(models.Model):
    class Status(models.TextChoices):
        RINGING = "ringing"
        ACCEPTED = "accepted"
        REJECTED = "rejected"
        MISSED = "missed"
        ENDED = "ended"
        BUSY = "busy"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    channel = models.CharField(max_length=120, unique=True)
    call_type = models.CharField(max_length=10, default="video")  # audio/video

    caller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calls_made")
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calls_received")

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RINGING)

    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    end_reason = models.CharField(max_length=64, null=True, blank=True)

    def __str__(self):
        return f"{self.caller_id}->{self.receiver_id} ({self.status})"