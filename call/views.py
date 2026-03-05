import uuid
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Call
from .token_service import generate_rtc_token
from .presence import is_in_call

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_call(request):
    """
    body: { "receiver_id": 123, "call_type": "video" }
    """
    receiver_id = request.data.get("receiver_id")
    call_type = request.data.get("call_type", "video")

    if not receiver_id:
        return Response({"detail": "receiver_id is required"}, status=400)

    receiver_id = int(receiver_id)

    # Busy check (fast)
    if is_in_call(receiver_id):
        return Response({"detail": "Receiver is busy"}, status=409)

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