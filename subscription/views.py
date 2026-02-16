from decimal import Decimal
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth import get_user_model

from .models import Subscription

User = get_user_model()


def ms_to_dt(ms):
    if not ms:
        return None
    return timezone.datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)


class RevenueCatWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        payload = request.data or {}
        event = payload.get("event") or {}

        event_type = event.get("type")
        app_user_id = event.get("app_user_id")

        if not event_type:
            return Response({"success": False, "message": "Missing event.type"}, status=400)
        if not app_user_id:
            return Response({"success": False, "message": "Missing event.app_user_id"}, status=400)

        # IMPORTANT: you said your app_user_id is your User ID (int)
        try:
            user_id = int(app_user_id)
        except (TypeError, ValueError):
            return Response({"success": False, "message": "event.app_user_id must be an integer user id"}, status=400)

        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({"success": False, "message": "User not found"}, status=404)

        # clean fields
        event_id = event.get("id")
        product_id = event.get("product_id")
        entitlement_id = event.get("entitlement_id")
        store = event.get("store")

        currency = event.get("currency") or "USD"
        price = Decimal(str(event.get("price") or "0"))

        purchased_at = ms_to_dt(event.get("purchased_at_ms"))
        expires_at = ms_to_dt(event.get("expiration_at_ms"))

        # Plan name: use entitlement_id if present, else product_id
        plan_name = entitlement_id or product_id or "Premium Plan"

        # If event_id exists, store idempotently (prevents duplicates)
        if event_id:
            obj, created = Subscription.objects.get_or_create(
                event_id=event_id,
                defaults={
                    "user": user,
                    "app_user_id": str(app_user_id),
                    "event_type": event_type,
                    "product_id": product_id,
                    "entitlement_id": entitlement_id,
                    "store": store,
                    "plan_name": plan_name,
                    "currency": currency,
                    "plan_price": price,
                    "purchased_at": purchased_at,
                    "expires_at": expires_at,
                },
            )
            return Response(
                {
                    "success": True,
                    "message": "Stored" if created else "Already stored",
                    "data": {"id": obj.id, "event": event_type},
                },
                status=200,
            )

        # If no event_id in payload, just create (may duplicate if webhook repeats)
        obj = Subscription.objects.create(
            user=user,
            app_user_id=str(app_user_id),
            event_type=event_type,
            product_id=product_id,
            entitlement_id=entitlement_id,
            store=store,
            plan_name=plan_name,
            currency=currency,
            plan_price=price,
            purchased_at=purchased_at,
            expires_at=expires_at,
        )

        return Response({"success": True, "message": "Stored", "data": {"id": obj.id, "event": event_type}}, status=200)
