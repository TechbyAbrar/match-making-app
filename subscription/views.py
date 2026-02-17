from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import OuterRef, Subquery, Sum
from django.utils import timezone

from rest_framework.permissions import IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Subscription
from .pagination import DashboardUserPagination

User = get_user_model()


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



# dashboard api
class AdminDashboardAPIView(APIView):
    permission_classes = [IsAdminUser]
    pagination_class = DashboardUserPagination

    def get(self, request, *args: Any, **kwargs: Any) -> Response:
        now = timezone.now()

        # ---- Stats ----
        total_users = User.objects.count()
        total_subscribers = User.objects.filter(is_subscribed=True).count()

        total_earning = (
            Subscription.objects
            .aggregate(total=Sum("plan_price"))
            .get("total")
        ) or Decimal("0.00")

        stats = {
            "total_users": total_users,
            "total_subscribers": total_subscribers,
            "total_earning": total_earning,
        }

        # ---- Subqueries: latest subscription per user ----
        latest_sub = (
            Subscription.objects
            .filter(user_id=OuterRef("pk"))
            .order_by("-created_at")  # or "-purchased_at" if you prefer
        )

        # ---- Users list (paginated) ----
        qs = (
            User.objects
            .order_by("-created_at")
            .annotate(
                plan_name=Subquery(latest_sub.values("plan_name")[:1]),
                plan_price=Subquery(latest_sub.values("plan_price")[:1]),
                currency=Subquery(latest_sub.values("currency")[:1]),
                sub_expires_at=Subquery(latest_sub.values("expires_at")[:1]),
            )
            .values(
                "user_id",
                "full_name",
                "username",
                "email",
                "created_at",
                "plan_name",
                "plan_price",
                "currency",
                "sub_expires_at",
            )
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)

        users_data = [
            {
                "user_id": row["user_id"],
                "full_name": row["full_name"],
                "username": row["username"],
                "email": row["email"],
                "join_date": row["created_at"],
                "plan_name": row["plan_name"],          # may be None
                "plan_price": row["plan_price"],        # may be None
                "currency": row["currency"],            # may be None
                "expires_at": row["sub_expires_at"],    # may be None
            }
            for row in page
        ]

        paginated = paginator.get_paginated_response(users_data).data

        return Response(
            {
                "success": True,
                "message": "Dashboard data fetched.",
                "stats": stats,
                "users": paginated,
            },
            status=200,
        )