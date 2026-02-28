# Standard library imports
import logging
from typing import Optional, Dict

# Django imports
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Count, F
from django.shortcuts import get_object_or_404
from django.utils import timezone

# Third-party imports
from django_redis import get_redis_connection

# Local app imports
from .models import (
    ProfileShare,
    UserBlock,
    Report,
    Story,
    StoryLike,
    Notification,
)

# Logger setup
logger = logging.getLogger(__name__)

# Redis connection
REDIS = get_redis_connection("default")

# Get User model
User = get_user_model()


def add_story_view(story_id: str, viewer_id: int) -> bool:
    """
    Record a story view in Redis. Returns True if it's a new view.
    """
    try:
        viewer_set = f"story:{story_id}:viewers"
        count_key = f"story:{story_id}:view_count"
        is_new = REDIS.sadd(viewer_set, viewer_id)
        REDIS.expire(viewer_set, 86400)
        if is_new:
            REDIS.incr(count_key)
            REDIS.expire(count_key, 86400)
        return bool(is_new)
    except Exception as e:
        logger.exception(f"Error adding story view: {e}")
        return False

def get_story_view_count(story_id: str) -> int:
    try:
        count = REDIS.get(f"story:{story_id}:view_count")
        return int(count) if count else 0
    except Exception as e:
        logger.exception(f"Error fetching story view count: {e}")
        return 0

def get_story_viewers(story_id: str, offset=0, limit=20):
    try:
        key = f"story:{story_id}:viewers"
        viewers = list(REDIS.smembers(key))
        total = len(viewers)
        slice_ = [int(v) for v in viewers[offset:offset+limit]]
        return slice_, total
    except Exception as e:
        logger.exception(f"Error fetching story viewers: {e}")
        return [], 0



# PROFILE SHARING SERVICES


def resolve_target_user(target: str) -> "User":
    """
    Resolve target user by ID or username.
    Raises ObjectDoesNotExist if user not found.
    """
    # Try as integer ID
    try:
        return User.objects.only("user_id", "username").get(user_id=int(target))
    except (ValueError, TypeError, ObjectDoesNotExist):
        pass

    # Try as username
    try:
        return User.objects.only("user_id", "username").get(username=target)
    except ObjectDoesNotExist:
        raise ObjectDoesNotExist(f"Target user '{target}' not found.")


def create_share(sharer: "User", target: str) -> tuple["ProfileShare", bool]:
    """
    Creates a ProfileShare object between sharer and target user.
    Returns a tuple (share_obj, created: bool)
    """
    target_user = resolve_target_user(target)

    if target_user.user_id == sharer.user_id:
        raise ValueError("You cannot share your own profile.")

    if not target_user.username:
        raise ValueError("Target user does not have a valid username to share.")

    try:
        with transaction.atomic():
            obj, created = ProfileShare.objects.get_or_create(
                sharer=sharer,
                shared_user=target_user
            )
            return obj, created
    except Exception as e:
        logger.exception(
            f"Error creating ProfileShare from user_id={sharer.user_id} "
            f"to target_id={target_user.user_id}"
        )
        raise e
    
    
# Block

# users/services/user_block_service.py

CACHE_TIMEOUT = 60*1

class UserBlockService:
    @staticmethod
    @transaction.atomic
    def block_user(blocker, blocked_user_id):
        blocked = User.objects.get(user_id=blocked_user_id)
        obj, created = UserBlock.objects.get_or_create(
            blocker=blocker, blocked=blocked
        )
        cache.delete(f"user_block_list_{blocker.user_id}")
        return obj, created

    @staticmethod
    @transaction.atomic
    def unblock_user(blocker, blocked_user_id):
        deleted_count, _ = UserBlock.objects.filter(
            blocker=blocker, blocked__user_id=blocked_user_id
        ).delete()
        cache.delete(f"user_block_list_{blocker.user_id}")
        return deleted_count

    @staticmethod
    def get_blocked_users(user):
        cache_key = f"user_block_list_{user.user_id}"
        blocked_users = cache.get(cache_key)
        if blocked_users is None:
            blocked_users = list(
                UserBlock.objects.filter(blocker=user)
                .select_related('blocked')
                .values('blocked__user_id', 'blocked__username')
            )
            cache.set(cache_key, blocked_users, CACHE_TIMEOUT)
        return blocked_users



# report

AGGREGATED_REPORTS_CACHE_KEY = "reports:aggregated_profiles_v1"
AGGREGATED_REPORTS_CACHE_TTL = 60  # seconds (adjust for your traffic/consistency needs)


class ReportServiceError(Exception):
    pass

# reports/services.py
from django.db.models import Count, OuterRef, Subquery
class ReportService:
    @staticmethod
    @transaction.atomic
    def create_report(*, reporter, reported_user, reason, comment=None, metadata=None):
        try:
            # Optional: prevent exact duplicate within 1 hour
            cutoff = timezone.now() - timezone.timedelta(hours=1)
            existing = Report.objects.filter(
                reporter=reporter,
                reported_user=reported_user,
                reason=reason,
                created_at__gte=cutoff,
            ).exists()
            if existing:
                raise ReportServiceError("You have recently submitted the same report.")

            report = Report.objects.create(
                reporter=reporter,
                reported_user=reported_user,
                reason=reason,
                comment=comment or "",
                metadata=metadata or {},
            )

            # Invalidate aggregated cache
            try:
                cache.delete(AGGREGATED_REPORTS_CACHE_KEY)
            except Exception:
                logger.exception("Failed to delete aggregated reports cache after new report.")

            logger.info("Report created: reporter=%s reported_user=%s reason=%s", reporter.user_id, reported_user.user_id, reason)
            return report

        except ReportServiceError:
            raise
        except Exception as exc:
            logger.exception("Failed to create report: %s", exc)
            raise ReportServiceError("Failed to create report") from exc


    # @staticmethod
    # def get_aggregated_reports(order_by="-report_count"):
    #     # Try cache
    #     cached = cache.get(AGGREGATED_REPORTS_CACHE_KEY)
    #     if cached is not None:
    #         return cached

    #     qs = (
    #         Report.objects
    #         .filter(resolved=False)
    #         .values("reported_user")
    #         .annotate(report_count=Count("id"))
    #         .order_by(order_by)
    #     )

    #     # Materialize to list of dicts (so cacheable easily)
    #     result = list(qs)
    #     try:
    #         cache.set(AGGREGATED_REPORTS_CACHE_KEY, result, AGGREGATED_REPORTS_CACHE_TTL)
    #     except Exception:
    #         logger.exception("Failed to set aggregated reports cache.")

    #     return result
    
    @staticmethod
    def get_aggregated_reports(order_by="-report_count"):
        cached = cache.get(AGGREGATED_REPORTS_CACHE_KEY)
        if cached is not None:
            return cached

        latest = (
            Report.objects
            .filter(resolved=False, reported_user=OuterRef("reported_user"))
            .order_by("-created_at")
        )

        qs = (
            Report.objects
            .filter(resolved=False)
            .values("reported_user")
            .annotate(
                report_count=Count("id"),

                # ✅ latest report snapshot
                last_report_id=Subquery(latest.values("id")[:1]),
                last_reason=Subquery(latest.values("reason")[:1]),
                last_comment=Subquery(latest.values("comment")[:1]),
                last_reporter_id=Subquery(latest.values("reporter_id")[:1]),
                last_reported_at=Subquery(latest.values("created_at")[:1]),
            )
            .order_by(order_by)
        )

        result = list(qs)
        try:
            cache.set(AGGREGATED_REPORTS_CACHE_KEY, result, AGGREGATED_REPORTS_CACHE_TTL)
        except Exception:
            logger.exception("Failed to set aggregated reports cache.")

        return result




# story services

# stories/services/like_service.py



class StoryLikeService:
    @staticmethod
    @transaction.atomic
    def like_story(story_id: str, user):
        story = get_object_or_404(
            Story,
            id=story_id,
            expires_at__gt=timezone.now(),
            is_deleted=False
        )

        if story.user == user:
            raise ValueError("You cannot like your own story.")

        obj, created = StoryLike.objects.get_or_create(story=story, user=user)
        if not created:
            raise ValueError("You have already liked this story.")

        Story.objects.filter(id=story_id).update(likes_count=F("likes_count") + 1)
        return True

    @staticmethod
    @transaction.atomic
    def unlike_story(story_id: str, user):
        deleted, _ = StoryLike.objects.filter(story_id=story_id, user=user).delete()
        if not deleted:
            raise ValueError("You have not liked this story yet.")

        Story.objects.filter(id=story_id, likes_count__gt=0).update(likes_count=F("likes_count") - 1)
        return True

    @staticmethod
    def is_liked(story, user) -> bool:
        """
        Returns True if the given user has liked the story, False otherwise.
        """
        return StoryLike.objects.filter(story=story, user=user).exists()
    
    
    
# notifications/services.py


def create_notification(
    recipient: User,
    type: str,
    message: str,
    sender: Optional[User] = None,
    metadata: Optional[Dict] = None
) -> Notification:
    """
    Creates a notification efficiently.
    """
    metadata = metadata or {}
    with transaction.atomic():
        notification = Notification.objects.create(
            recipient=recipient,
            sender=sender,
            type=type,
            message=message,
            metadata=metadata,
            created_at=timezone.now()
        )
    return notification
