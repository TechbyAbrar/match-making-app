from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import StoryLike, ProfileShare, Report
from .services import create_notification
from account.models import UserLike  # UserLike is in account app
from django.contrib.auth import get_user_model

User = get_user_model()


@receiver(post_save, sender=StoryLike)
def notify_story_like(sender, instance: StoryLike, created: bool, **kwargs):
    if created and instance.user != instance.story.user:
        create_notification(
            recipient=instance.story.user,
            sender=instance.user,
            type='STORY_LIKE',
            message=f"{instance.user.username} liked your story.",
            metadata={'story_id': str(instance.story.id)}
        )


@receiver(post_save, sender=UserLike)
def notify_user_like(sender, instance: UserLike, created: bool, **kwargs):
    if created and instance.user_from != instance.user_to:
        create_notification(
            recipient=instance.user_to,
            sender=instance.user_from,
            type='USER_LIKE',
            message=f"{instance.user_from.username} liked your profile.",
            metadata={'user_from_id': instance.user_from.user_id}
        )


@receiver(post_save, sender=ProfileShare)
def notify_profile_share(sender, instance: ProfileShare, created: bool, **kwargs):
    if created and instance.sharer != instance.shared_user:
        create_notification(
            recipient=instance.shared_user,
            sender=instance.sharer,
            type='PROFILE_SHARE',
            message=f"{instance.sharer.username} shared your profile.",
            metadata={'sharer_id': instance.sharer.id}
        )


@receiver(post_save, sender=Report)
def notify_report(sender, instance: Report, created: bool, **kwargs):
    if created:
        staff_users = User.objects.filter(is_staff=True, is_active=True)
        for staff in staff_users:
            create_notification(
                recipient=staff,
                sender=instance.reporter,
                type='REPORT',
                message=f"{instance.reporter.username} reported {instance.reported_user.username}: {instance.reason}",
                metadata={'report_id': instance.id}
            )
