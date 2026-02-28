import requests
from django.conf import settings

from .models import Notification, NotificationDelivery
from .tasks import send_delivery_task

ONESIGNAL_API_URL = "https://onesignal.com/api/v1/notifications"

class OneSignalError(Exception):
    pass

def send_to_player_ids(*, title: str, body: str, player_ids: list[str], data: dict) -> dict:
    if not player_ids:
        return {"skipped": True, "reason": "no_player_ids"}

    headers = {
        "Authorization": f"Basic {settings.ONESIGNAL_REST_API_KEY}",
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
    }

    payload = {
        "app_id": settings.ONESIGNAL_APP_ID,
        "include_player_ids": player_ids,
        "headings": {"en": title},
        "contents": {"en": body},
        "data": data,  # important: used by Flutter for routing
        # Optional:
        # "android_channel_id": settings.ONESIGNAL_ANDROID_CHANNEL_ID,
        # "ios_sound": "default",
        # "priority": 10,
    }

    r = requests.post(ONESIGNAL_API_URL, json=payload, headers=headers, timeout=15)
    try:
        resp = r.json()
    except Exception:
        raise OneSignalError(f"Non-JSON response: {r.status_code} {r.text}")

    if r.status_code >= 400:
        raise OneSignalError(f"OneSignal error {r.status_code}: {resp}")

    return resp



def create_and_send_notification(*, ntype: str, title: str, body: str, recipients, data: dict, actor_id=None, entity_id=None):
    notif = Notification.objects.create(
        type=ntype,
        title=title,
        body=body,
        data=data,
        actor_id=actor_id,
        entity_id=entity_id,
    )

    deliveries = []
    for user in recipients:
        deliveries.append(NotificationDelivery(notification=notif, recipient=user))

    NotificationDelivery.objects.bulk_create(deliveries, ignore_conflicts=True)

    for d in NotificationDelivery.objects.filter(notification=notif):
        send_delivery_task.delay(str(d.id))

    return notif