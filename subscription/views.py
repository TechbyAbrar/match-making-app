from django.utils import timezone
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth import get_user_model

from .models import Subscription

User = get_user_model()


class RevenueCatWebhookView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        data = request.data or {}
        event = data.get("event") or {}

        event_type = event.get("type")
        customer_id = event.get("app_user_id")
        entitlement = event.get("entitlement_id")
        expiration_at_ms = event.get("expiration_at_ms")

        if not event_type:
            return Response({"error": "Missing event.type"}, status=400)

        if not customer_id:
            return Response({"error": "Missing event.app_user_id"}, status=400)

        # app_user_id should match your User.user_id (AutoField)
        try:
            user_id = int(customer_id)
        except (TypeError, ValueError):
            return Response({"error": "event.app_user_id must be an integer user_id"}, status=400)

        try:
            user = User.objects.get(user_id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        # PURCHASE / RENEWAL
        if event_type in ("INITIAL_PURCHASE", "RENEWAL"):
            if not entitlement:
                return Response({"error": "Missing event.entitlement_id"}, status=400)

            if expiration_at_ms is None:
                return Response({"error": "Missing event.expiration_at_ms"}, status=400)

            try:
                expires_at = timezone.datetime.fromtimestamp(
                    int(expiration_at_ms) / 1000,
                    tz=timezone.utc
                )
            except (TypeError, ValueError, OSError):
                return Response({"error": "Invalid event.expiration_at_ms"}, status=400)

            # Keep started_at if subscription exists already
            sub, created = Subscription.objects.update_or_create(
                user=user,
                revenuecat_entitlement_id=entitlement,
                defaults={
                    "plan": entitlement,  # NOTE: entitlement must match your PLAN_CHOICES keys
                    "revenuecat_customer_id": str(customer_id),
                    "is_active": True,
                    "expires_at": expires_at,
                },
            )

            if created or not sub.started_at:
                sub.started_at = timezone.now()
                sub.save(update_fields=["started_at"])

            # Update User fields
            user.is_subscribed = True
            user.subscription_expiry = expires_at
            user.save(update_fields=["is_subscribed", "subscription_expiry"])

            return Response({"status": "success", "event": event_type})

        # CANCELLATION / EXPIRATION
        if event_type in ("CANCELLATION", "EXPIRATION"):
            # entitlement can be missing sometimes depending on event; handle both cases
            qs = Subscription.objects.filter(user=user)
            if entitlement:
                qs = qs.filter(revenuecat_entitlement_id=entitlement)

            qs.update(is_active=False)

            # If user still has any active subscription, keep is_subscribed True
            has_active = Subscription.objects.filter(user=user, is_active=True).exists()
            user.is_subscribed = has_active
            user.subscription_expiry = (
                Subscription.objects.filter(user=user, is_active=True)
                .order_by("-expires_at")
                .values_list("expires_at", flat=True)
                .first()
            )
            user.save(update_fields=["is_subscribed", "subscription_expiry"])

            return Response({"status": "success", "event": event_type})

        # Other events ignored safely
        return Response({"status": "ignored", "event": event_type})
