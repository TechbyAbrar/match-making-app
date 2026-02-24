# users/presence_config.py
PRESENCE_TOUCH_THROTTLE_SECONDS = 300  # touch at most once per 5 minutes
OFFLINE_CUTOFF_MINUTES = 12            # must be > 5 to avoid flicker


# account/presence.py
from django.utils import timezone
from django.core.cache import cache

def touch_chat_presence(user) -> None:
    if not user or not user.is_authenticated:
        return

    key = f"presence:chat_touch:{user.pk}"
    if cache.get(key):
        return

    now = timezone.now()

    # lightweight update (no model save)
    type(user).objects.filter(pk=user.pk).update(
        is_online=True,
        last_activity=now,
    )

    cache.set(key, 1, PRESENCE_TOUCH_THROTTLE_SECONDS)