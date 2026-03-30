import logging
import requests
from django.conf import settings
from django.utils import timezone

from .models import Notification, NotificationDelivery, Device, NotificationPreference

logger = logging.getLogger(__name__)

ONESIGNAL_API_URL = "https://onesignal.com/api/v1/notifications"


class OneSignalError(Exception):
    pass


def send_to_player_ids(
    *, title: str, body: str, player_ids: list[str], data: dict
) -> dict:
    if not player_ids:
        return {"skipped": True, "reason": "no_player_ids"}

    headers = {
        "Authorization": f"Basic {settings.ONESIGNAL_REST_API_KEY}",
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
    }

    payload = {
        "app_id": settings.ONESIGNAL_APP_ID,
        # FIX: include_player_ids is deprecated — use include_subscription_ids
        "include_subscription_ids": player_ids,
        "headings": {"en": title},
        "contents": {"en": body},
        "data": data,
        "priority": 10,
    }

    # Only include android_channel_id if configured
    android_channel = getattr(settings, "ONESIGNAL_ANDROID_CHANNEL_ID", None)
    if android_channel:
        payload["android_channel_id"] = android_channel

    try:
        r = requests.post(
            ONESIGNAL_API_URL, json=payload, headers=headers, timeout=15
        )
        resp = r.json()
    except requests.Timeout:
        raise OneSignalError("OneSignal request timed out after 15s")
    except requests.RequestException as e:
        raise OneSignalError(f"OneSignal network error: {e}")
    except ValueError:
        raise OneSignalError(f"OneSignal non-JSON response: {r.status_code} {r.text[:200]}")

    if r.status_code >= 400:
        raise OneSignalError(f"OneSignal HTTP {r.status_code}: {resp}")

    logger.info(f"OneSignal sent. id={resp.get('id')} recipients={resp.get('recipients')}")
    return resp


def _get_preference(user) -> NotificationPreference:
    pref, _ = NotificationPreference.objects.get_or_create(user=user)
    return pref


def create_and_send_notification(
    *,
    ntype: str,
    title: str,
    body: str,
    recipients,          # list[User] or QuerySet[User]
    data: dict,
    actor_id=None,
    entity_id=None,
) -> Notification:
    # Import here to avoid circular import (tasks imports services)
    from .tasks import send_delivery_task

    notif = Notification.objects.create(
        type=ntype,
        title=title,
        body=body,
        data=data,
        actor_id=actor_id,
        entity_id=entity_id,
    )

    # FIX: filter by user preference before creating deliveries
    allowed = [u for u in recipients if _get_preference(u).is_allowed(ntype)]

    if not allowed:
        logger.info(f"Notification {notif.id} ({ntype}): all recipients opted out.")
        return notif

    delivery_objs = [
        NotificationDelivery(notification=notif, recipient=u) for u in allowed
    ]
    # FIX: use the returned objects directly — no extra DB query
    created = NotificationDelivery.objects.bulk_create(
        delivery_objs, ignore_conflicts=True
    )

    for d in created:
        send_delivery_task.delay(str(d.id))

    return notif