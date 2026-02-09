import json
import base64
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.files.base import ContentFile
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from .models import ChatThread, Message, MessageReaction

logger = logging.getLogger(__name__)
User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.thread_id = self.scope["url_route"]["kwargs"]["thread_id"]
        self.user = self.scope.get("user")

        # 🔐 Must be authenticated
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # 🔐 Must be a participant of the thread
        is_allowed = await self.is_thread_member(self.user.pk, self.thread_id)
        if not is_allowed:
            await self.close(code=4003)
            return

        self.room_group_name = f"chat_{self.thread_id}"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        logger.info(f"WebSocket connected: user={self.user.pk} thread={self.thread_id}")

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        logger.info(f"WebSocket disconnected: thread={self.thread_id} code={close_code}")

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_json({"error": "Invalid JSON"})
            return

        msg_type = data.get("type")

        if msg_type == "message":
            await self.handle_message(data)
        elif msg_type == "reaction":
            await self.handle_reaction(data)
        else:
            await self.send_json({"error": "Unknown message type"})

    async def handle_message(self, data):
        thread_id = data.get("thread")
        message_type = data.get("message_type")
        content = data.get("content", "")
        attachment_b64 = data.get("attachment")
        is_like = data.get("is_like", False)

        if int(thread_id) != int(self.thread_id):
            await self.send_json({"error": "Thread mismatch"})
            return

        attachment_file = None

        if message_type == Message.MESSAGE_IMAGE:
            if not attachment_b64:
                await self.send_json({"error": "Image attachment required"})
                return
            try:
                format, imgstr = attachment_b64.split(";base64,")
                ext = format.split("/")[-1]
                attachment_file = ContentFile(
                    base64.b64decode(imgstr),
                    name=f"msg_{self.user.pk}.{ext}",
                )
            except Exception:
                await self.send_json({"error": "Invalid base64 image"})
                return

        elif message_type == Message.MESSAGE_TEXT:
            if not content:
                await self.send_json({"error": "Text message cannot be empty"})
                return

        try:
            msg = await self.save_message(
                sender_id=self.user.pk,
                content=content,
                message_type=message_type,
                attachment=attachment_file,
                is_like=is_like,
            )

            serialized = await self.serialize_message(msg)

            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "chat_message", "message": serialized},
            )

        except Exception as e:
            logger.exception("Failed to save message")
            await self.send_json({"error": str(e)})


        async def handle_reaction(self, data):
            reaction_data = data.get("reaction")

            if not reaction_data:
                await self.send_json({"error": "Reaction data required"})
                return

            message_id = reaction_data.get("message_id")
            reaction_type = reaction_data.get("reaction")

            if not message_id or not reaction_type:
                await self.send_json({"error": "message_id and reaction are required"})
                return

            try:
                reaction = await self.save_reaction(
                    user_id=self.user.pk,
                    message_id=message_id,
                    reaction_type=reaction_type,
                )

                await self.channel_layer.group_send(
                    self.room_group_name,
                    {"type": "chat_reaction", "reaction": reaction},
                )

            except Exception as e:
                logger.exception("Failed to save reaction")
                await self.send_json({"error": str(e)})

    async def chat_message(self, event):
        await self.send_json(event["message"])

    async def chat_reaction(self, event):
        await self.send_json({"reaction": event["reaction"]})

    async def send_json(self, data):
        await self.send(text_data=json.dumps(data))

    # ========================= DB =========================

    @database_sync_to_async
    def is_thread_member(self, user_id, thread_id):
        return ChatThread.objects.filter(
            pk=thread_id,
            user_a_id__in=[user_id],
        ).exists() or ChatThread.objects.filter(
            pk=thread_id,
            user_b_id__in=[user_id],
        ).exists()

    @database_sync_to_async
    def save_message(self, sender_id, content, message_type, attachment, is_like):
        sender = User.objects.get(pk=sender_id)
        thread = ChatThread.objects.get(pk=self.thread_id)

        if sender.pk not in (thread.user_a_id, thread.user_b_id):
            raise PermissionError("Sender is not in this thread")

        msg = Message.objects.create(
            thread=thread,
            sender=sender,
            content=content or "",
            message_type=message_type,
            attachment=attachment,
            is_like=is_like,
        )

        ChatThread.objects.filter(pk=thread.pk).update(updated_at=timezone.now())

        receiver_id = thread.user_b_id if sender.pk == thread.user_a_id else thread.user_a_id
        key = f"chat:unread:{receiver_id}:{thread.pk}"

        if cache.get(key) is not None:
            cache.incr(key, 1)
        else:
            cache.set(key, 1, timeout=7 * 24 * 3600)

        msg = Message.objects.select_related("sender", "thread").prefetch_related("reactions").get(pk=msg.pk)
        return msg


    @database_sync_to_async
    def save_reaction(self, user_id, message_id, reaction_type):
        user = User.objects.get(pk=user_id)
        message = Message.objects.get(pk=message_id)

        reaction, _ = MessageReaction.objects.update_or_create(
            message=message,
            user=user,
            defaults={"reaction": reaction_type},
        )

        return {"message_id": message_id, "user_id": user_id, "reaction": reaction_type}

    @database_sync_to_async
    def serialize_message(self, msg):
        from .serializers import MessageSerializer
        return MessageSerializer(msg).data
