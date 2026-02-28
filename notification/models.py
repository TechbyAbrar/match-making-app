import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class Device(models.Model):
    class Platform(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"
        WEB = "web", "Web"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="devices")
    onesignal_player_id = models.CharField(max_length=255, unique=True)  # subscription/player id
    platform = models.CharField(max_length=20, choices=Platform.choices)
    is_active = models.BooleanField(default=True)

    app_version = models.CharField(max_length=50, blank=True, default="")
    device_model = models.CharField(max_length=80, blank=True, default="")
    os_version = models.CharField(max_length=50, blank=True, default="")

    last_seen_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["platform", "is_active"]),
        ]


class Notification(models.Model):
    """
    A single "event" that can be delivered to multiple recipients.
    """
    class Type(models.TextChoices):
        CHAT_MESSAGE = "chat_message", "Chat message"
        CALL_INCOMING = "call_incoming", "Incoming call"
        CALL_MISSED = "call_missed", "Missed call"
        VIDEO_INVITE = "video_invite", "Video invite"
        STORY_NEW = "story_new", "New story"
        GENERIC = "generic", "Generic"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    type = models.CharField(max_length=50, choices=Type.choices)
    title = models.CharField(max_length=120)
    body = models.TextField()

    # Fully flexible custom payload for Flutter routing:
    data = models.JSONField(default=dict, blank=True)

    # Who/what triggered it (optional but useful):
    actor_id = models.UUIDField(null=True, blank=True)
    entity_id = models.UUIDField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)


class NotificationDelivery(models.Model):
    """
    Per-recipient delivery state.
    """
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"  # e.g. no devices

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="deliveries")
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notification_deliveries")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    onesignal_notification_id = models.CharField(max_length=255, blank=True, default="")
    error = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("notification", "recipient")
        indexes = [models.Index(fields=["recipient", "status"])]