import logging
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Device, NotificationDelivery, NotificationPreference
from .serializers import (
    DeviceUpsertSerializer,
    NotificationSerializer,
    NotificationPreferenceSerializer,
)

logger = logging.getLogger(__name__)


class DeviceRegisterView(APIView):
    """
    POST /api/notifications/devices/register/
    Called by Flutter on app start or when OneSignal gives a new player_id.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = DeviceUpsertSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response({"ok": True}, status=status.HTTP_200_OK)


class DeviceDeregisterView(APIView):
    """
    POST /api/notifications/devices/deregister/
    Called by Flutter on logout to stop push to this device.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        player_id = request.data.get("onesignal_player_id", "").strip()
        # FIX: validate input — original returned 200 on empty string silently
        if not player_id:
            return Response(
                {"error": "onesignal_player_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        updated = Device.objects.filter(
            user=request.user, onesignal_player_id=player_id
        ).update(is_active=False)
        return Response({"ok": True, "deactivated": updated})


class NotificationListView(APIView):
    """
    GET /api/notifications/?page_size=30
    In-app inbox — only SENT deliveries, newest first.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page_size = min(int(request.query_params.get("page_size", 30)), 100)
        qs = (
            NotificationDelivery.objects
            .filter(
                recipient=request.user,
                status=NotificationDelivery.Status.SENT,
            )
            .select_related("notification")
            .order_by("-notification__created_at")
        )[:page_size]
        ser = NotificationSerializer(qs, many=True)
        return Response(ser.data)


class NotificationUnreadCountView(APIView):
    """
    GET /api/notifications/unread-count/
    Used by Flutter to show badge on the bell icon.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = NotificationDelivery.objects.filter(
            recipient=request.user,
            is_read=False,
            status=NotificationDelivery.Status.SENT,
        ).count()
        return Response({"unread_count": count})


class NotificationMarkReadView(APIView):
    """
    POST /api/notifications/<delivery_id>/read/
    Mark a single notification as read.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, delivery_id):
        delivery = get_object_or_404(
            NotificationDelivery, id=delivery_id, recipient=request.user
        )
        if not delivery.is_read:
            delivery.is_read = True
            delivery.read_at = timezone.now()
            delivery.save(update_fields=["is_read", "read_at"])
        return Response({"ok": True})


class NotificationMarkAllReadView(APIView):
    """
    POST /api/notifications/read-all/
    Bulk mark all unread as read — used when user opens the inbox.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = NotificationDelivery.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True, read_at=timezone.now())
        return Response({"ok": True, "marked": updated})


class NotificationPreferenceView(APIView):
    """
    GET  /api/notifications/preferences/  — fetch current preferences
    PUT  /api/notifications/preferences/  — update (partial allowed)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pref, _ = NotificationPreference.objects.get_or_create(user=request.user)
        return Response(NotificationPreferenceSerializer(pref).data)

    def put(self, request):
        pref, _ = NotificationPreference.objects.get_or_create(user=request.user)
        ser = NotificationPreferenceSerializer(pref, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)