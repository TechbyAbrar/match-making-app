from rest_framework import serializers
from django.utils import timezone
from .models import Device, NotificationDelivery, NotificationPreference


class DeviceUpsertSerializer(serializers.Serializer):
    onesignal_player_id = serializers.CharField(max_length=255)
    platform = serializers.ChoiceField(choices=Device.Platform.choices)
    app_version = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    device_model = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    os_version = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")

    def save(self, **kwargs):
        user = self.context["request"].user
        player_id = self.validated_data["onesignal_player_id"]
        # FIX: last_seen_at moved from view into here — single responsibility
        device, _ = Device.objects.update_or_create(
            onesignal_player_id=player_id,
            defaults={
                "user": user,
                "platform": self.validated_data["platform"],
                "is_active": True,
                "app_version": self.validated_data.get("app_version", ""),
                "device_model": self.validated_data.get("device_model", ""),
                "os_version": self.validated_data.get("os_version", ""),
                "last_seen_at": timezone.now(),
            },
        )
        return device


class NotificationSerializer(serializers.ModelSerializer):
    """
    Flattens Notification + NotificationDelivery into one clean response
    for the Flutter inbox. Flutter only needs one object, not nested.
    """
    type = serializers.CharField(source="notification.type")
    title = serializers.CharField(source="notification.title")
    body = serializers.CharField(source="notification.body")
    data = serializers.JSONField(source="notification.data")
    actor_id = serializers.UUIDField(source="notification.actor_id", allow_null=True)
    entity_id = serializers.UUIDField(source="notification.entity_id", allow_null=True)
    created_at = serializers.DateTimeField(source="notification.created_at")

    class Meta:
        model = NotificationDelivery
        fields = [
            "id",           # delivery UUID — used for mark-read endpoint
            "type",
            "title",
            "body",
            "data",
            "actor_id",
            "entity_id",
            "is_read",
            "read_at",
            "status",
            "created_at",
        ]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        exclude = ["id", "user"]