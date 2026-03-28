from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class UserSubscription(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
    )

    source = models.CharField(max_length=50, db_index=True)
    platform = models.CharField(max_length=20, db_index=True)

    app_user_id = models.CharField(max_length=255, blank=True, default="")
    original_app_user_id = models.CharField(max_length=255, blank=True, default="")

    entitlement_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    is_blink_pro_active = models.BooleanField(default=False, db_index=True)

    active_subscriptions = models.JSONField(default=list, blank=True)
    all_purchased_product_identifiers = models.JSONField(default=list, blank=True)
    all_purchase_dates = models.JSONField(default=dict, blank=True)
    all_expiration_dates = models.JSONField(default=dict, blank=True)

    latest_expiration_date = models.DateTimeField(null=True, blank=True, db_index=True)
    request_date = models.DateTimeField(null=True, blank=True)
    management_url = models.URLField(blank=True, default="", max_length=1000)

    entitlements = models.JSONField(default=dict, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)

    synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_subscriptions"

    def __str__(self) -> str:
        return f"user={self.user_id} active={self.is_blink_pro_active}"

    def clean(self) -> None:
        self.source = (self.source or "").strip().lower()
        self.platform = (self.platform or "").strip().lower()
        self.app_user_id = (self.app_user_id or "").strip()
        self.original_app_user_id = (self.original_app_user_id or "").strip()
        self.entitlement_id = (self.entitlement_id or "").strip()

        if self.latest_expiration_date and self.request_date:
            if self.latest_expiration_date.year < 2000:
                raise ValidationError(
                    {"latest_expiration_date": "Invalid latest_expiration_date."}
                )