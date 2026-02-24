# users/management/commands/mark_offline.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

User = get_user_model()

OFFLINE_CUTOFF_MINUTES = 25  # ✅ must be > cron interval and > touch throttle

class Command(BaseCommand):
    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(minutes=OFFLINE_CUTOFF_MINUTES)

        updated = User.objects.filter(
            is_online=True,
            last_activity__lt=cutoff
        ).update(is_online=False)

        self.stdout.write(f"Marked offline: {updated}")