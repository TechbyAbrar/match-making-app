# tasks.py
from celery import shared_task
from django.utils import timezone
from .models import NotificationDelivery, Device
from .services import send_to_player_ids, OneSignalError

@shared_task(bind=True, max_retries=5, default_retry_delay=10)
def send_delivery_task(self, delivery_id: str):
    delivery = NotificationDelivery.objects.select_related("notification", "recipient").get(id=delivery_id)
    notif = delivery.notification

    player_ids = list(
        Device.objects.filter(user=delivery.recipient, is_active=True)
        .values_list("onesignal_player_id", flat=True)
    )

    if not player_ids:
        delivery.status = NotificationDelivery.Status.SKIPPED
        delivery.error = "No active devices"
        delivery.sent_at = timezone.now()
        delivery.save(update_fields=["status", "error", "sent_at"])
        return

    try:
        resp = send_to_player_ids(
            title=notif.title,
            body=notif.body,
            player_ids=player_ids,
            data=notif.data,
        )
        delivery.status = NotificationDelivery.Status.SENT
        delivery.onesignal_notification_id = resp.get("id", "")
        delivery.sent_at = timezone.now()
        delivery.save(update_fields=["status", "onesignal_notification_id", "sent_at"])
    except OneSignalError as e:
        delivery.status = NotificationDelivery.Status.FAILED
        delivery.error = str(e)
        delivery.save(update_fields=["status", "error"])
        raise self.retry(exc=e)