import uuid
from django.utils import timezone
from django.db import transaction
from django.db import models

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Call
from .token_service import generate_rtc_token
from .presence import is_in_call


from datetime import timedelta
import uuid

from django.db import transaction, models
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Call


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_call(request):
    receiver_id = request.data.get("receiver_id")
    call_type = request.data.get("call_type", "video")

    if not receiver_id:
        return Response({"detail": "receiver_id is required"}, status=400)

    receiver_id = int(receiver_id)

    # ✅ avoid self-call
    if receiver_id == request.user.pk:
        return Response({"detail": "You cannot call yourself"}, status=400)

    with transaction.atomic():
        # ✅ auto-expire old ringing calls so users don't stay "busy" forever
        timeout_at = timezone.now() - timedelta(seconds=25)  # tune as needed
        Call.objects.select_for_update().filter(
            status=Call.Status.RINGING,
            created_at__lt=timeout_at,
        ).update(
            status=Call.Status.MISSED,
            ended_at=timezone.now(),
            end_reason="timeout",
        )

        # ✅ block if receiver is still in an active call
        active_call = Call.objects.select_for_update().filter(
            status__in=[Call.Status.RINGING, Call.Status.ACCEPTED],
        ).filter(
            models.Q(caller_id=receiver_id) |
            models.Q(receiver_id=receiver_id)
        ).first()

        if active_call:
            return Response({"detail": "Receiver already in a call"}, status=409)

        channel = f"call_{uuid.uuid4().hex}"

        call = Call.objects.create(
            channel=channel,
            caller=request.user,
            receiver_id=receiver_id,
            call_type=call_type,
            status=Call.Status.RINGING,
        )

    return Response({
        "call_id": str(call.id),
        "channel": call.channel,
        "call_type": call.call_type,
        "status": call.status,
    }, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def agora_token(request):
    
    channel = request.GET.get("channel")
    uid = request.GET.get("uid")

    if not channel or not uid:
        return Response({"detail": "channel and uid are required"}, status=400)

    uid = int(uid)

    call = Call.objects.filter(channel=channel).first()
    if not call:
        return Response({"detail": "Invalid channel"}, status=404)

    # Only caller/receiver can get token
    if request.user.id not in (call.caller_id, call.receiver_id):
        return Response({"detail": "Forbidden"}, status=403)

    if call.status not in (Call.Status.RINGING, Call.Status.ACCEPTED):
        return Response({"detail": f"Call not active ({call.status})"}, status=400)

    token = generate_rtc_token(channel, uid)
    return Response({"token": token})