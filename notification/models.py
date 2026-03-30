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
    onesignal_player_id = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=20, choices=Platform.choices)
    is_active = models.BooleanField(default=True)
    app_version = models.CharField(max_length=50, blank=True, default="")
    device_model = models.CharField(max_length=100, blank=True, default="")
    os_version = models.CharField(max_length=50, blank=True, default="")
    last_seen_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # FIX: was missing

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["platform", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user} | {self.platform} | {self.onesignal_player_id[:8]}"


class Notification(models.Model):
    class Type(models.TextChoices):
        CHAT_MESSAGE = "chat_message", "Chat Message"
        CALL_INCOMING = "call_incoming", "Incoming Call"
        CALL_MISSED = "call_missed", "Missed Call"
        VIDEO_INVITE = "video_invite", "Video Invite"
        STORY_NEW = "story_new", "New Story"
        GENERIC = "generic", "Generic"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=50, choices=Type.choices)
    title = models.CharField(max_length=120)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    actor_id = models.UUIDField(null=True, blank=True)
    entity_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.type}] {self.title}"


class NotificationDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name="deliveries"
    )
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notification_deliveries"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    onesignal_notification_id = models.CharField(max_length=255, blank=True, default="")
    error = models.TextField(blank=True, default="")

    # FIX: critical for in-app inbox — was completely missing
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("notification", "recipient")
        indexes = [
            models.Index(fields=["recipient", "status"]),
            models.Index(fields=["recipient", "is_read"]),  # FIX: needed for unread-count
        ]

    def __str__(self):
        return f"{self.recipient} | {self.notification.type} | {self.status}"


class NotificationPreference(models.Model):
    """
    FIX: completely missing from original.
    Per-user opt-in/out for each notification type + global kill switch.
    Auto-created on first access via get_or_create in services.py.
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="notification_preference"
    )
    push_enabled = models.BooleanField(default=True)  # global kill-switch

    # One field per Notification.Type value
    chat_message = models.BooleanField(default=True)
    call_incoming = models.BooleanField(default=True)
    call_missed = models.BooleanField(default=True)
    video_invite = models.BooleanField(default=True)
    story_new = models.BooleanField(default=True)
    generic = models.BooleanField(default=True)

    def is_allowed(self, ntype: str) -> bool:
        if not self.push_enabled:
            return False
        return getattr(self, ntype, True)  # safe fallback: allow unknown types

    def __str__(self):
        return f"NotifPref({self.user})"