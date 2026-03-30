"""
This is how OTHER apps (chat, account, etc.) trigger notifications cleanly
without importing views or tasks directly. They just fire a Django signal.
"""
from django.dispatch import Signal, receiver
from .services import create_and_send_notification
from .models import Notification

# Define signals here — other apps import and send these
notify_chat_message = Signal()   # provides: sender, recipient, message, chat
notify_call_incoming = Signal()  # provides: sender, recipient, call
notify_call_missed = Signal()    # provides: sender, recipient, call
notify_story_new = Signal()      # provides: sender, recipients, story


@receiver(notify_chat_message)
def handle_chat_message(sender, recipient, message, chat, **kwargs):
    create_and_send_notification(
        ntype=Notification.Type.CHAT_MESSAGE,
        title=f"{sender.get_full_name() or sender.username}",
        body=message.content[:100],
        recipients=[recipient],
        data={
            "screen": "chat_detail",
            "chat_id": str(chat.id),
            "message_id": str(message.id),
        },
        actor_id=sender.id,
        entity_id=chat.id,
    )


@receiver(notify_call_incoming)
def handle_call_incoming(sender, recipient, call, **kwargs):
    create_and_send_notification(
        ntype=Notification.Type.CALL_INCOMING,
        title="Incoming call",
        body=f"{sender.get_full_name() or sender.username} is calling you",
        recipients=[recipient],
        data={"screen": "call", "call_id": str(call.id)},
        actor_id=sender.id,
        entity_id=call.id,
    )