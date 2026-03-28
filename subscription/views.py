from __future__ import annotations

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import UserSubscription
from .serializers import SubscriptionSyncSerializer


class SubscriptionSyncAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        serializer = SubscriptionSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payload = serializer.validated_data

        subscription, _ = (
            UserSubscription.objects
            .select_for_update()
            .get_or_create(user=request.user)
        )

        subscription.source = payload["source"]
        subscription.platform = payload["platform"]
        subscription.app_user_id = payload["app_user_id"]
        subscription.original_app_user_id = payload.get("original_app_user_id", "")
        subscription.entitlement_id = payload.get("entitlement_id", "")
        subscription.is_blink_pro_active = payload.get("is_blink_pro_active", False)
        subscription.active_subscriptions = payload.get("active_subscriptions", [])
        subscription.all_purchased_product_identifiers = payload.get(
            "all_purchased_product_identifiers", []
        )
        subscription.all_purchase_dates = payload.get("all_purchase_dates", {})
        subscription.all_expiration_dates = payload.get("all_expiration_dates", {})
        subscription.latest_expiration_date = payload.get("latest_expiration_date")
        subscription.management_url = payload.get("management_url", "")
        subscription.request_date = payload.get("request_date")
        subscription.entitlements = payload.get("entitlements", {})
        subscription.raw_payload = payload

        subscription.full_clean()
        subscription.save()

        return Response(
            {
                "detail": "Subscription synced successfully.",
                "data": {
                    "user_id": request.user.pk,
                    "source": subscription.source,
                    "platform": subscription.platform,
                    "entitlement_id": subscription.entitlement_id,
                    "is_blink_pro_active": subscription.is_blink_pro_active,
                    "latest_expiration_date": subscription.latest_expiration_date,
                    "synced_at": subscription.synced_at,
                },
            },
            status=status.HTTP_200_OK,
        )


class SubscriptionDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        subscription = getattr(request.user, "subscription", None)

        if not subscription:
            return Response(
                {"detail": "Subscription info not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "data": {
                    "user_id": request.user.pk,
                    "source": subscription.source,
                    "platform": subscription.platform,
                    "app_user_id": subscription.app_user_id,
                    "original_app_user_id": subscription.original_app_user_id,
                    "entitlement_id": subscription.entitlement_id,
                    "is_blink_pro_active": subscription.is_blink_pro_active,
                    "active_subscriptions": subscription.active_subscriptions,
                    "all_purchased_product_identifiers": subscription.all_purchased_product_identifiers,
                    "all_purchase_dates": subscription.all_purchase_dates,
                    "all_expiration_dates": subscription.all_expiration_dates,
                    "latest_expiration_date": subscription.latest_expiration_date,
                    "management_url": subscription.management_url,
                    "request_date": subscription.request_date,
                    "entitlements": subscription.entitlements,
                    "synced_at": subscription.synced_at,
                    "created_at": subscription.created_at,
                }
            },
            status=status.HTTP_200_OK,
        )