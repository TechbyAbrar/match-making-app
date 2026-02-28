
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from .serializers import DeviceUpsertSerializer
from .models import Device
class DeviceUpsertView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = DeviceUpsertSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        device = ser.save()
        device.last_seen_at = timezone.now()
        device.save(update_fields=["last_seen_at"])
        return Response({"ok": True})
    
    
class DeviceDeactivateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        player_id = request.data.get("onesignal_player_id")
        if player_id:
            Device.objects.filter(user=request.user, onesignal_player_id=player_id).update(is_active=False)
        return Response({"ok": True})