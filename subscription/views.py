import json
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth import get_user_model
from .models import Subscription

User = get_user_model()


class RevenueCatWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data

        event_type = data.get("event", {}).get("type")
        customer_id = data.get("event", {}).get("app_user_id")
        entitlement = data.get("event", {}).get("entitlement_id")
        expiration_at = data.get("event", {}).get("expiration_at_ms")

        if not customer_id:
            return Response({"error": "No customer id"}, status=400)

        try:
            user = User.objects.get(id=customer_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        # Handle activation
        if event_type in ["INITIAL_PURCHASE", "RENEWAL"]:

            expires_at = timezone.datetime.fromtimestamp(
                int(expiration_at) / 1000,
                tz=timezone.utc
            )

            Subscription.objects.update_or_create(
                user=user,
                revenuecat_entitlement_id=entitlement,
                defaults={
                    "plan": entitlement,
                    "revenuecat_customer_id": customer_id,
                    "is_active": True,
                    "started_at": timezone.now(),
                    "expires_at": expires_at,
                },
            )

            user.is_subscribed = True
            user.save(update_fields=["is_subscribed"])

        # Handle cancellation / expiration
        if event_type in ["CANCELLATION", "EXPIRATION"]:
            Subscription.objects.filter(
                user=user,
                revenuecat_entitlement_id=entitlement
            ).update(is_active=False)

            user.is_subscribed = False
            user.save(update_fields=["is_subscribed"])

        return Response({"status": "success"})
