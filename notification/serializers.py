# serializers.py
from rest_framework import serializers
from .models import Device

class DeviceUpsertSerializer(serializers.Serializer):
    onesignal_player_id = serializers.CharField(max_length=255)
    platform = serializers.ChoiceField(choices=Device.Platform.choices)
    app_version = serializers.CharField(max_length=50, required=False, allow_blank=True)
    device_model = serializers.CharField(max_length=80, required=False, allow_blank=True)
    os_version = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def create(self, validated):
        user = self.context["request"].user
        player_id = validated["onesignal_player_id"]

        device, _ = Device.objects.update_or_create(
            onesignal_player_id=player_id,
            defaults={
                "user": user,
                "platform": validated["platform"],
                "is_active": True,
                "app_version": validated.get("app_version", ""),
                "device_model": validated.get("device_model", ""),
                "os_version": validated.get("os_version", ""),
            },
        )
        return device