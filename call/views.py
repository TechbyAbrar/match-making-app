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
from django.contrib.auth import get_user_model
User = get_user_model()

from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Call
from .presence import set_in_call, clear_in_call, is_in_call


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_call(request):
    receiver_id = request.data.get("receiver_id")
    call_type = request.data.get("call_type", "video")

    if not receiver_id:
        return Response({"detail": "receiver_id is required"}, status=400)

    receiver_id = int(receiver_id)
    
    if call_type not in ["audio", "video"]:
        return Response({"detail": "call_type must be 'audio' or 'video'"}, status=400)

    # ✅ avoid self-call
    if receiver_id == request.user.pk:
        return Response({"detail": "You cannot call yourself"}, status=400)
    
    if not User.objects.filter(pk=receiver_id).exists():
        return Response({"detail": "Receiver not found or exist"}, status=404)

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
    uid = request.user.pk

    if not channel:
        return Response({"detail": "channel is required"}, status=400)

    call = Call.objects.filter(channel=channel).first()
    if not call:
        return Response({"detail": "Invalid channel"}, status=404)

    if request.user.pk not in (call.caller_id, call.receiver_id):
        return Response({"detail": "Forbidden"}, status=403)

    if call.status not in (Call.Status.RINGING, Call.Status.ACCEPTED):
        return Response({"detail": f"Call not active ({call.status})"}, status=400)

    token = generate_rtc_token(channel, uid)

    return Response({
        "token": token,
        "uid": uid,
    })
    
    


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def accept_call(request, call_id):
    with transaction.atomic():
        call = Call.objects.select_for_update().filter(id=call_id).first()

        if not call:
            return Response({"detail": "Call not found"}, status=404)

        if call.receiver_id != request.user.pk:
            return Response({"detail": "Only receiver can accept this call"}, status=403)

        if call.status != Call.Status.RINGING:
            return Response(
                {"detail": f"Cannot accept call in {call.status} state"},
                status=400,
            )

        if is_in_call(request.user.pk):
            call.status = Call.Status.BUSY
            call.ended_at = timezone.now()
            call.end_reason = "receiver_busy"
            call.save(update_fields=["status", "ended_at", "end_reason"])
            return Response({"detail": "Receiver already in another call"}, status=409)

        call.status = Call.Status.ACCEPTED
        call.accepted_at = timezone.now()
        call.save(update_fields=["status", "accepted_at"])

        set_in_call(call.caller_id, str(call.id))
        set_in_call(call.receiver_id, str(call.id))

    return Response({
        "call_id": str(call.id),
        "status": call.status,
        "channel": call.channel,
        "call_type": call.call_type,
        "accepted_at": call.accepted_at,
    }, status=200)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reject_call(request, call_id):
    with transaction.atomic():
        call = Call.objects.select_for_update().filter(id=call_id).first()

        if not call:
            return Response({"detail": "Call not found"}, status=404)

        if call.receiver_id != request.user.pk:
            return Response({"detail": "Only receiver can reject this call"}, status=403)

        if call.status != Call.Status.RINGING:
            return Response(
                {"detail": f"Cannot reject call in {call.status} state"},
                status=400,
            )

        call.status = Call.Status.REJECTED
        call.ended_at = timezone.now()
        call.end_reason = "rejected"
        call.save(update_fields=["status", "ended_at", "end_reason"])

        clear_in_call(call.caller_id)
        clear_in_call(call.receiver_id)

    return Response({
        "call_id": str(call.id),
        "status": call.status,
        "end_reason": call.end_reason,
        "ended_at": call.ended_at,
    }, status=200)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def end_call(request, call_id):
    reason = request.data.get("reason", "ended")

    with transaction.atomic():
        call = Call.objects.select_for_update().filter(id=call_id).first()

        if not call:
            return Response({"detail": "Call not found"}, status=404)

        if request.user.pk not in (call.caller_id, call.receiver_id):
            return Response({"detail": "Forbidden"}, status=403)

        if call.status in [
            Call.Status.ENDED,
            Call.Status.REJECTED,
            Call.Status.MISSED,
            Call.Status.FAILED,
        ]:
            return Response(
                {"detail": f"Call already finished with status {call.status}"},
                status=400,
            )

        if call.status == Call.Status.RINGING and reason == "timeout":
            call.status = Call.Status.MISSED
            call.end_reason = "timeout"
        else:
            call.status = Call.Status.ENDED
            call.end_reason = reason

        call.ended_at = timezone.now()
        call.save(update_fields=["status", "end_reason", "ended_at"])

        clear_in_call(call.caller_id)
        clear_in_call(call.receiver_id)

    return Response({
        "call_id": str(call.id),
        "status": call.status,
        "end_reason": call.end_reason,
        "ended_at": call.ended_at,
    }, status=200)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def call_status(request, call_id):
    call = Call.objects.filter(id=call_id).first()

    if not call:
        return Response({"detail": "Call not found"}, status=404)

    if request.user.pk not in (call.caller_id, call.receiver_id):
        return Response({"detail": "Forbidden"}, status=403)

    return Response({
        "call_id": str(call.id),
        "channel": call.channel,
        "call_type": call.call_type,
        "status": call.status,
        "caller_id": call.caller_id,
        "receiver_id": call.receiver_id,
        "created_at": call.created_at,
        "accepted_at": call.accepted_at,
        "ended_at": call.ended_at,
        "end_reason": call.end_reason,
    }, status=200)