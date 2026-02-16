from django.db import models
from django.conf import settings
class Subscription(models.Model):
    PLAN_CHOICES = (
        ('society', 'Society'),
        ('premium', 'Premium'),
        ('elite', 'Elite'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions"
    )

    plan = models.CharField(max_length=20, choices=PLAN_CHOICES)

    revenuecat_customer_id = models.CharField(max_length=255)
    revenuecat_entitlement_id = models.CharField(max_length=255)

    is_active = models.BooleanField(default=True)

    started_at = models.DateTimeField()
    expires_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} - {self.plan}"
