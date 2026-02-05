from celery import shared_task
from django.db.models import F
from django.utils import timezone
from .models import Story
from .services import REDIS
import logging

logger = logging.getLogger(__name__)

@shared_task
def cleanup_expired_stories():
    expired = Story.objects.filter(expires_at__lt=timezone.now(), is_deleted=False)
    count = expired.update(is_deleted=True)
    logger.info(f"Cleaned up {count} expired stories.")


@shared_task
def sync_redis_view_counts():
    """
    Periodically sync Redis view counts to DB
    """
    keys = REDIS.keys("story:*:view_count")
    for key in keys:
        try:
            story_id = key.decode().split(":")[1]
            count = int(REDIS.get(key))
            if count > 0:
                Story.objects.filter(id=story_id).update(view_count=F('view_count') + count)
                REDIS.delete(key)
        except Exception as e:
            logger.exception(f"Error syncing story view count: {e}")
