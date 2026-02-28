import requests
from django.conf import settings

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