import json
import base64
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.files.base import ContentFile
from django.contrib.auth import get_user_model
from .models import ChatThread, Message, MessageReaction

logger = logging.getLogger(__name__)
User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.thread_id = self.scope["url_route"]["kwargs"]["thread_id"]
        self.room_group_name = f"chat_{self.thread_id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        logger.info(f"WebSocket connected: thread {self.thread_id}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        logger.info(f"WebSocket disconnected: thread {self.thread_id} code={close_code}")

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(json.dumps({"error": "Invalid JSON"}))
            return

        msg_type = data.get("type", "message")
        if msg_type == "message":
            await self.handle_message(data)
        elif msg_type == "reaction":
            await self.handle_reaction(data)

    async def handle_message(self, data):
        message_text = data.get("message", "")
        attachment_b64 = data.get("attachment")
        # use .pk (works regardless of primary key field name)
        sender_id = getattr(self.scope.get("user", None), "pk", None) or data.get("sender_id")

        # Auto-detect message type
        if attachment_b64:
            message_type = Message.MESSAGE_IMAGE
            try:
                format, imgstr = attachment_b64.split(";base64,")
                ext = format.split("/")[-1]
                attachment_file = ContentFile(base64.b64decode(imgstr), name=f"msg_{sender_id}.{ext}")
            except Exception:
                await self.send(json.dumps({"error": "Invalid base64 image"}))
                return
        else:
            message_type = Message.MESSAGE_TEXT
            attachment_file = None

        if message_type == Message.MESSAGE_TEXT and not message_text:
            await self.send(json.dumps({"error": "Text message cannot be empty"}))
            return

        try:
            msg = await self.save_message(sender_id, message_text, message_type, attachment_file)
            serialized = await self.serialize_message(msg)
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "chat_message", "message": serialized},
            )
        except Exception as e:
            logger.exception("Failed to save message")
            await self.send(json.dumps({"error": str(e)}))

    async def handle_reaction(self, data):
        reaction_data = data.get("reaction")
        if not reaction_data:
            await self.send(json.dumps({"error": "Reaction data required"}))
            return

        sender_id = getattr(self.scope.get("user", None), "pk", None) or data.get("sender_id")
        message_id = reaction_data.get("message_id")
        reaction_type = reaction_data.get("reaction")

        try:
            reaction = await self.save_reaction(sender_id, message_id, reaction_type)
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "chat_reaction", "reaction": reaction},
            )
        except Exception as e:
            logger.exception("Failed to save reaction")
            await self.send(json.dumps({"error": str(e)}))

    async def chat_message(self, event):
        await self.send(json.dumps(event["message"]))

    async def chat_reaction(self, event):
        await self.send(json.dumps({"reaction": event["reaction"]}))

    @database_sync_to_async
    def save_message(self, sender_id, content, message_type, attachment):
        # use pk lookups so custom user PK name doesn't matter
        sender = User.objects.get(pk=sender_id)
        thread = ChatThread.objects.get(pk=self.thread_id)
        # thread.user_a_id and thread.user_b_id are the integer FK columns; compare with sender.pk
        if sender.pk not in (thread.user_a_id, thread.user_b_id):
            raise PermissionError("Sender is not in the thread")

        msg = Message.objects.create(
            thread=thread,
            sender=sender,
            content=content or "",
            message_type=message_type,
            attachment=attachment
        )
        msg = Message.objects.select_related("sender", "thread").prefetch_related("reactions").get(pk=msg.pk)
        msg._prefetched_reactions = list(msg.reactions.all())
        return msg

    @database_sync_to_async
    def save_reaction(self, user_id, message_id, reaction_type):
        user = User.objects.get(pk=user_id)
        message = Message.objects.get(pk=message_id)
        reaction, _ = MessageReaction.objects.update_or_create(
            message=message,
            user=user,
            defaults={"reaction": reaction_type}
        )
        return {"message_id": message_id, "user_id": user_id, "reaction": reaction_type}

    @database_sync_to_async
    def serialize_message(self, msg):
        from .serializers import MessageSerializer
        return MessageSerializer(msg).data
