from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

from .models import Call
from .presence import set_online


class CallConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or user.is_anonymous:
            await self.close(code=4401)
            return

        self.user = user
        self.user_id = user.pk
        self.user_group = f"user_{self.user_id}"

        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.accept()

        await sync_to_async(set_online)(self.user_id)

        await self.send_json({
            "type": "ws_connected",
            "success": True,
            "message": "WebSocket connected successfully",
            "data": {
                "user_id": self.user_id,
            },
        })

    async def disconnect(self, code):
        if hasattr(self, "user_group"):
            await self.channel_layer.group_discard(self.user_group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        await sync_to_async(set_online)(self.user_id)

        msg_type = content.get("type")

        if msg_type == "call_invite":
            await self.on_invite(content)
        elif msg_type == "call_accept":
            await self.on_accept(content)
        elif msg_type == "call_reject":
            await self.on_reject(content)
        elif msg_type == "call_end":
            await self.on_end(content)
        elif msg_type == "ping":
            await self.send_json({
                "type": "pong",
                "success": True,
                "message": "pong",
                "data": None,
            })
        else:
            await self.send_error("Unknown message type")

    async def on_invite(self, data):
        call_id = data.get("call_id")
        target_user_id = data.get("target_user_id")

        if not call_id or not target_user_id:
            await self.send_error("call_id and target_user_id required")
            return

        try:
            target_user_id = int(target_user_id)
        except (TypeError, ValueError):
            await self.send_error("target_user_id must be a valid integer")
            return

        call = await self.get_call(call_id)
        if not call:
            await self.send_error("Call not found")
            return

        if call.caller_id != self.user_id:
            await self.send_error("Only caller can send invite for this call")
            return

        if call.receiver_id != target_user_id:
            await self.send_error("target_user_id does not match call receiver")
            return

        if call.status != Call.Status.RINGING:
            await self.send_error(f"Cannot invite in {call.status} state")
            return

        await self.push_call_event(
            target_user_id=target_user_id,
            event_type="incoming_call",
            message="Incoming call",
            call=call,
        )

        await self.send_json({
            "type": "call_invite_sent",
            "success": True,
            "message": "Call invite sent",
            "data": self.call_payload(call),
        })

    async def on_accept(self, data):
        call_id = data.get("call_id")
        if not call_id:
            await self.send_error("call_id required")
            return

        call = await self.get_call(call_id)
        if not call:
            await self.send_error("Call not found")
            return

        if call.receiver_id != self.user_id:
            await self.send_error("Only receiver can send accept signal")
            return

        if call.status != Call.Status.ACCEPTED:
            await self.send_error(f"Call is not accepted yet, current state: {call.status}")
            return

        await self.push_call_event(
            target_user_id=call.caller_id,
            event_type="call_accepted",
            message="Call accepted",
            call=call,
        )

        await self.send_json({
            "type": "call_accepted",
            "success": True,
            "message": "Call accepted signal sent",
            "data": self.call_payload(call),
        })

    async def on_reject(self, data):
        call_id = data.get("call_id")
        if not call_id:
            await self.send_error("call_id required")
            return

        call = await self.get_call(call_id)
        if not call:
            await self.send_error("Call not found")
            return

        if call.receiver_id != self.user_id:
            await self.send_error("Only receiver can send reject signal")
            return

        if call.status != Call.Status.REJECTED:
            await self.send_error(f"Call is not rejected yet, current state: {call.status}")
            return

        await self.push_call_event(
            target_user_id=call.caller_id,
            event_type="call_rejected",
            message="Call rejected",
            call=call,
        )

        await self.send_json({
            "type": "call_rejected",
            "success": True,
            "message": "Call rejected signal sent",
            "data": self.call_payload(call),
        })

    async def on_end(self, data):
        call_id = data.get("call_id")
        if not call_id:
            await self.send_error("call_id required")
            return

        call = await self.get_call(call_id)
        if not call:
            await self.send_error("Call not found")
            return

        if self.user_id not in (call.caller_id, call.receiver_id):
            await self.send_error("Forbidden")
            return

        if call.status not in [Call.Status.ENDED, Call.Status.MISSED]:
            await self.send_error(f"Call is not ended yet, current state: {call.status}")
            return

        other_user_id = call.receiver_id if self.user_id == call.caller_id else call.caller_id

        await self.push_call_event(
            target_user_id=other_user_id,
            event_type="call_ended",
            message="Call ended",
            call=call,
        )

        await self.send_json({
            "type": "call_ended",
            "success": True,
            "message": "Call ended signal sent",
            "data": self.call_payload(call),
        })

    async def push_event(self, event):
        await self.send_json(event["payload"])

    async def send_error(self, message, event_type="error", data=None):
        await self.send_json({
            "type": event_type,
            "success": False,
            "message": message,
            "data": data,
        })

    async def push_call_event(self, target_user_id, event_type, message, call):
        await self.channel_layer.group_send(
            f"user_{target_user_id}",
            {
                "type": "push_event",
                "payload": {
                    "type": event_type,
                    "success": True,
                    "message": message,
                    "data": self.call_payload(call),
                },
            },
        )

    def call_payload(self, call):
        if not call:
            return None

        return {
            "call_id": str(call.id),
            "channel": call.channel,
            "call_type": call.call_type,
            "status": call.status,
            "caller_id": call.caller_id,
            "receiver_id": call.receiver_id,
            "created_at": call.created_at.isoformat() if call.created_at else None,
            "accepted_at": call.accepted_at.isoformat() if call.accepted_at else None,
            "ended_at": call.ended_at.isoformat() if call.ended_at else None,
            "end_reason": call.end_reason,
        }

    @database_sync_to_async
    def get_call(self, call_id):
        return Call.objects.filter(id=call_id).first()