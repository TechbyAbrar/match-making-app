from decimal import Decimal
from django.db import models
from django.conf import settings


class Subscription(models.Model):
    class Meta:
        verbose_name_plural = "Subscriptions"
        db_table = "subscription"
        ordering = ["-created_at"]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )

    # RevenueCat identifiers
    app_user_id = models.CharField(max_length=255)                  # event.app_user_id
    event_id = models.CharField(max_length=100, null=True, blank=True, unique=True)  # event.id (if present)

    # Event info
    event_type = models.CharField(max_length=50)                    # INITIAL_PURCHASE / RENEWAL / etc.
    product_id = models.CharField(max_length=255, null=True, blank=True)
    entitlement_id = models.CharField(max_length=255, null=True, blank=True)
    store = models.CharField(max_length=50, null=True, blank=True)

    # What you need for earnings
    plan_name = models.CharField(max_length=100, default="Premium Plan")
    currency = models.CharField(max_length=10, default="USD")
    plan_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    # Dates from RevenueCat
    purchased_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.plan_name} - {self.plan_price} {self.currency}"
