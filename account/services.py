from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from .models import UserAuth as User, UserLike
import logging

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

    @staticmethod
    def who_liked_user(user_id: int):
        qs = (
            User.objects
            .filter(likes_given__user_to__user_id=user_id)
            # .values("user_id", "username", "full_name", "is_online", "hobbies", "profile_pic")
            .distinct()
        )
        return qs