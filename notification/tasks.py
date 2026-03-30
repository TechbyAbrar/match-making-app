from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

from .models import NotificationDelivery, Device
from .services import send_to_player_ids, OneSignalError

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=5)
def send_delivery_task(self, delivery_id: str):
    # FIX: guard against missing delivery — never retry on DoesNotExist
    try:
        delivery = (
            NotificationDelivery.objects
            .select_related("notification", "recipient")
            .get(id=delivery_id)
        )
    except NotificationDelivery.DoesNotExist:
        logger.error(f"send_delivery_task: delivery {delivery_id} not found. Skipping.")
        return

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
        logger.warning(f"OneSignal failed for delivery {delivery_id}: {e}. Retrying.")
        # FIX: exponential backoff — 60s, 120s, 240s, 480s, 960s
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))