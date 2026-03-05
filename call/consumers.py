from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

from .models import Call
from .presence import set_online, is_in_call, set_in_call, clear_in_call

class CallConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close(code=4401)
            return

        self.user = user
        self.user_group = f"user_{user.id}"

        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.accept()

        # mark online (refresh TTL)
        set_online(user.id)

        await self.send_json({"type": "ws_connected", "user_id": user.id})

    async def disconnect(self, code):
        if hasattr(self, "user_group"):
            await self.channel_layer.group_discard(self.user_group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        set_online(self.user.id)  # keep alive

        msg_type = content.get("type")

        if msg_type == "call_invite":
            await self.on_invite(content)
        elif msg_type == "call_accept":
            await self.on_accept(content)
        elif msg_type == "call_reject":
            await self.on_reject(content)
        elif msg_type == "call_end":
            await self.on_end(content)
        else:
            await self.send_json({"type": "error", "detail": "Unknown message type"})

    async def on_invite(self, data):
        """
        data: { type, call_id, target_user_id }
        """
        call_id = data.get("call_id")
        target_user_id = data.get("target_user_id")

        if not call_id or not target_user_id:
            await self.send_json({"type": "error", "detail": "call_id and target_user_id required"})
            return

        target_user_id = int(target_user_id)

        # fast busy check
        if is_in_call(target_user_id):
            await self.set_status(call_id, Call.Status.BUSY, "receiver_busy")
            await self.send_json({"type": "busy", "call_id": call_id})
            return

        call = await self.get_call(call_id)
        if not call or call.caller_id != self.user.id:
            await self.send_json({"type": "error", "detail": "Invalid call or not caller"})
            return

        # notify receiver
        await self.channel_layer.group_send(
            f"user_{target_user_id}",
            {
                "type": "push_event",
                "payload": {
                    "type": "incoming_call",
                    "call_id": str(call.id),
                    "from_user_id": call.caller_id,
                    "channel": call.channel,
                    "call_type": call.call_type,
                }
            }
        )

        # optional: also confirm to caller
        await self.send_json({"type": "invite_sent", "call_id": str(call.id)})

    async def on_accept(self, data):
        """
        data: { type, call_id }
        """
        call_id = data.get("call_id")
        if not call_id:
            await self.send_json({"type": "error", "detail": "call_id required"})
            return

        call = await self.get_call(call_id)
        if not call or call.receiver_id != self.user.id:
            await self.send_json({"type": "error", "detail": "Invalid call or not receiver"})
            return

        # if receiver already in another call
        if is_in_call(self.user.id):
            await self.set_status(call_id, Call.Status.BUSY, "receiver_busy")
            await self.send_json({"type": "busy", "call_id": call_id})
            return

        ok = await self.accept_call(call_id)
        if not ok:
            await self.send_json({"type": "error", "detail": "Cannot accept (maybe not ringing)"})
            return

        # mark both in-call
        set_in_call(call.caller_id, str(call.id))
        set_in_call(call.receiver_id, str(call.id))

        # notify caller
        await self.channel_layer.group_send(
            f"user_{call.caller_id}",
            {
                "type": "push_event",
                "payload": {
                    "type": "call_accepted",
                    "call_id": str(call.id),
                    "channel": call.channel,
                }
            }
        )

        await self.send_json({"type": "accepted", "call_id": str(call.id), "channel": call.channel})

    async def on_reject(self, data):
        call_id = data.get("call_id")
        if not call_id:
            await self.send_json({"type": "error", "detail": "call_id required"})
            return

        call = await self.get_call(call_id)
        if not call or call.receiver_id != self.user.id:
            await self.send_json({"type": "error", "detail": "Invalid call or not receiver"})
            return

        await self.set_status(call_id, Call.Status.REJECTED, "rejected")

        await self.channel_layer.group_send(
            f"user_{call.caller_id}",
            {"type": "push_event", "payload": {"type": "call_rejected", "call_id": str(call.id)}}
        )

        await self.send_json({"type": "rejected", "call_id": str(call.id)})

    async def on_end(self, data):
        """
        data: { type, call_id, reason }
        """
        call_id = data.get("call_id")
        reason = data.get("reason", "ended")

        if not call_id:
            await self.send_json({"type": "error", "detail": "call_id required"})
            return

        call = await self.get_call(call_id)
        if not call:
            return

        # only caller or receiver can end
        if self.user.id not in (call.caller_id, call.receiver_id):
            await self.send_json({"type": "error", "detail": "Forbidden"})
            return

        # if still ringing and caller ends -> missed
        if call.status == Call.Status.RINGING and reason == "timeout":
            await self.set_status(call_id, Call.Status.MISSED, "timeout")
        else:
            await self.end_call(call_id, reason)

        # clear in-call flags
        clear_in_call(call.caller_id)
        clear_in_call(call.receiver_id)

        other_user_id = call.receiver_id if self.user.id == call.caller_id else call.caller_id
        await self.channel_layer.group_send(
            f"user_{other_user_id}",
            {"type": "push_event", "payload": {"type": "call_ended", "call_id": str(call.id), "reason": reason}}
        )

        await self.send_json({"type": "ended", "call_id": str(call.id), "reason": reason})

    async def push_event(self, event):
        await self.send_json(event["payload"])

    # ---------- DB helpers ----------
    @database_sync_to_async
    def get_call(self, call_id):
        return Call.objects.filter(id=call_id).first()

    @database_sync_to_async
    def accept_call(self, call_id) -> bool:
        call = Call.objects.filter(id=call_id).first()
        if not call or call.status != Call.Status.RINGING:
            return False
        call.status = Call.Status.ACCEPTED
        call.accepted_at = timezone.now()
        call.save(update_fields=["status", "accepted_at"])
        return True

    @database_sync_to_async
    def set_status(self, call_id, status_value, reason=None):
        Call.objects.filter(id=call_id).update(status=status_value, end_reason=reason)

    @database_sync_to_async
    def end_call(self, call_id, reason="ended"):
        Call.objects.filter(id=call_id).update(
            status=Call.Status.ENDED,
            ended_at=timezone.now(),
            end_reason=reason,
        )