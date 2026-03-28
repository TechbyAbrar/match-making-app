from rest_framework import serializers


class SubscriptionSyncSerializer(serializers.Serializer):
    source = serializers.CharField(max_length=50)
    platform = serializers.CharField(max_length=20)

    app_user_id = serializers.CharField(max_length=255)
    user_id = serializers.IntegerField(required=False, allow_null=True)

    entitlement_id = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default="",
    )
    is_blink_pro_active = serializers.BooleanField(required=False, default=False)

    active_subscriptions = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
    )
    all_purchased_product_identifiers = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
    )
    all_purchase_dates = serializers.DictField(required=False, default=dict)
    all_expiration_dates = serializers.DictField(required=False, default=dict)

    latest_expiration_date = serializers.DateTimeField(required=False, allow_null=True)
    management_url = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )
    request_date = serializers.DateTimeField(required=False, allow_null=True)

    original_app_user_id = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default="",
    )
    entitlements = serializers.DictField(required=False, default=dict)

    def validate(self, attrs):
        attrs["source"] = attrs["source"].strip().lower()
        attrs["platform"] = attrs["platform"].strip().lower()
        return attrs