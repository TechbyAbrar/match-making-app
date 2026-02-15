import uuid
import logging
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db.models import F


User = settings.AUTH_USER_MODEL


logger = logging.getLogger(__name__)

class Story(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='stories')
    text = models.TextField(blank=True, null=True)
    media = models.FileField(
        upload_to='stories/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'mp4'])]
    )
    view_count = models.PositiveIntegerField(default=0)
    likes_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(editable=False)
    
    is_deleted = models.BooleanField(default=False)
    

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['expires_at', 'user'])]

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=24)
        super().save(*args, **kwargs)

    def increment_view_count(self, amount=1):
        self.view_count = F('view_count') + amount
        self.save(update_fields=['view_count'])

    def __str__(self):
        return f"{self.user.username}'s story ({self.id})"


class StoryLike(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="story_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('story', 'user')
        indexes = [models.Index(fields=["story", "user"])]
        
    def __str__(self) -> str: # pragma: no cover - trivial
        return f"Like(story={self.story_id}, user={self.user_id})"


# PROFILE SHARING MODEL

class ProfileShare(models.Model):
    sharer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="shares_made"
    )
    shared_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="shares_received"
    )

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("sharer", "shared_user")

    def __str__(self):
        return f"{self.sharer} → {self.shared_user}"


# Block
class UserBlock(models.Model):
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='blocking',
        on_delete=models.CASCADE
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='blocked_by',
        on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('blocker', 'blocked')
        indexes = [
            models.Index(fields=['blocker', 'blocked']),
        ]

    def __str__(self):
        return f"{self.blocker} blocked {self.blocked}"



# report profile
class ReportReason(models.TextChoices):
    FAKE_PROFILE = "Profile is fake", "Profile is fake"
    INAPPROPRIATE = "Inappropriate messages", "Inappropriate messages"
    HARASSMENT = "Harassment or bullying", "Harassment or bullying"
    OFFENSIVE = "Offensive content", "Offensive content"
    TECHNICAL = "Technical problem", "Technical problem"
    OTHER = "Other issues", "Other issues"


class Report(models.Model):
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports_made",
    )
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports_received",
    )
    reason = models.CharField(max_length=50, choices=ReportReason.choices)
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(blank=True, null=True)
    metadata = models.JSONField(blank=True, null=True)  # optional (device, ip, etc)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["reported_user"]),
            models.Index(fields=["reporter"]),
            models.Index(fields=["reported_user", "created_at"]),
        ]

    def __str__(self):
        return f"Report({self.reporter_id} -> {self.reported_user_id} : {self.reason})"



# Face recognition model
class UserFace(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    face_image = models.ImageField(upload_to='faceverify/')
