from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from .models import UserAuth as User, UserLike
import logging
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.contrib.gis.geos import Point
from django.db.models import Subquery
logger = logging.getLogger(__name__)

class UserLikeService:
    @staticmethod
    @transaction.atomic
    def like_user(user_from: User, user_to_id: int):
        if user_from.user_id == user_to_id:   # <-- change here
            raise ValueError("You cannot like yourself.")

        try:
            user_to = User.objects.get(user_id=user_to_id)
        except User.DoesNotExist:
            raise ValueError("User not found.")

        obj, created = UserLike.objects.get_or_create(user_from=user_from, user_to=user_to)
        if not created:
            raise ValueError("You have already liked this user.")

        return obj

    @staticmethod
    @transaction.atomic
    def unlike_user(user_from: User, user_to_id: int):
        try:
            like = UserLike.objects.get(user_from=user_from, user_to__user_id=user_to_id)  # <-- change here
            like.delete()
        except UserLike.DoesNotExist:
            raise ValueError("You haven't liked this user.")

    # @staticmethod
    # def who_liked_user(user_id: int):
    #     qs = (
    #         User.objects
    #         .filter(likes_given__user_to__user_id=user_id)
    #         # .values("user_id", "username", "full_name", "is_online", "hobbies", "profile_pic")
    #         .distinct()
    #     )
    #     return qs
    
    @staticmethod
    def who_liked_user(user, radius_km=None):
        liker_ids = UserLike.objects.filter(user_to=user).values("user_from_id")
        qs = User.objects.filter(user_id__in=Subquery(liker_ids)).distinct()

        # If current user has no location: can't compute distances, return list
        if user.latitude is None or user.longitude is None:
            return qs.order_by("-created_at")

        user_point = Point(float(user.longitude), float(user.latitude), srid=4326)

        # annotate distance (will be NULL for likers without geo_location)
        qs = qs.annotate(distance_m=Distance("geo_location", user_point))

        if radius_km is None:
            radius_km = user.distance  # slider

        # Only apply radius filter if you REALLY want to hide users without location
        if radius_km:
            qs = qs.filter(geo_location__distance_lte=(user_point, D(km=radius_km)))

        return qs.order_by("distance_m")  # nulls first/last depends; acceptable