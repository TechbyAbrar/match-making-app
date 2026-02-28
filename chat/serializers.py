# Standard library
from collections import defaultdict

# Django
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.db.models import F, Window
from django.db.models.functions import Random, RowNumber

# DRF
from rest_framework import serializers

# Local apps
from .models import (
    ChatThread,
    Message,
    MessageReaction,
    Society,
    SocietyMember,
    SocietyMessage,
)

User = get_user_model()
class SimpleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["user_id", "email", "username", "full_name", "profile_pic", 'is_online']  # updated id → user_id



class MessageSerializer(serializers.ModelSerializer):
    message_id = serializers.IntegerField(source="id", read_only=True)
    sender = SimpleUserSerializer(read_only=True)
    reactions = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "message_id", "thread", "sender", "content", "message_type", "attachment",
            "is_read", "is_like", "created_at", "reactions"
        ]
        read_only_fields = ["message_id", "sender", "created_at", "is_read", "reactions"]

    def get_reactions(self, obj):
        reactions = getattr(obj, "_prefetched_reactions", obj.reactions.all())
        # r.user_id is correct because MessageReaction.user_id refers to FK column
        return [{"user_id": r.user_id, "reaction": r.reaction} for r in reactions]

    def validate(self, attrs):
        mt = attrs.get("message_type", Message.MESSAGE_TEXT)
        if mt == Message.MESSAGE_TEXT and not attrs.get("content"):
            raise serializers.ValidationError({"content": "Text message requires 'content'."})
        if mt == Message.MESSAGE_IMAGE and not attrs.get("attachment"):
            raise serializers.ValidationError({"attachment": "Image message requires an 'attachment'."})
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["sender"] = user
        message = super().create(validated_data)
        ChatThread.objects.filter(pk=message.thread_id).update(updated_at=message.created_at)
        return message



class ThreadListSerializer(serializers.ModelSerializer):
    thread_id = serializers.IntegerField(source="id", read_only=True)
    other_user = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = ChatThread
        fields = ["thread_id", "other_user", "updated_at", "last_message", "unread_count"]

    def get_other_user(self, obj):
        request_user = self.context.get("request").user

        # request_user.pk instead of request_user.id (id does NOT exist)
        other = obj.user_b if obj.user_a_id == request_user.pk else obj.user_a
        return SimpleUserSerializer(other).data

    def get_last_message(self, obj):
        last = obj.messages.order_by("-created_at").first()
        return MessageSerializer(last).data if last else None
    
    def get_unread_count(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return 0

        key = f"chat:unread:{request.user.pk}:{obj.pk}"
        return int(cache.get(key) or 0)



class SocietySerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True)
    random_member_images = serializers.SerializerMethodField()

    class Meta:
        model = Society
        fields = ["id", "name", "image", "created_by", "created_at", "member_count", "random_member_images"]
        read_only_fields = ["id", "created_by", "created_at", "member_count", "random_member_images"]

    def _random_images_map(self):
        """
        Build {society_id: [pic1..pic5]} once for the whole list serialization.
        """
        if hasattr(self, "_cached_random_images_map"):
            return self._cached_random_images_map

        instance = self.instance
        if not instance:
            self._cached_random_images_map = {}
            return self._cached_random_images_map

        # instance can be queryset/list or single object
        if hasattr(instance, "__iter__"):
            society_ids = [s.id for s in instance]
        else:
            society_ids = [instance.id]

        qs = (
            SocietyMember.objects
            .filter(society_id__in=society_ids)
            .select_related("user")
            .annotate(
                rn=Window(
                    expression=RowNumber(),
                    partition_by=[F("society_id")],
                    order_by=Random(),
                )
            )
            .filter(rn__lte=5)
            .values("society_id", "user__profile_pic")
        )

        mp = defaultdict(list)
        request = self.context.get("request")

        for row in qs:
            pic = row["user__profile_pic"]
            if not pic:
                continue

            pic_str = str(pic).strip()

            # 1) If already absolute (CDN etc.), keep it
            if pic_str.startswith("http://") or pic_str.startswith("https://"):
                final_url = pic_str

            else:
                # 2) If starts with "/", it's already a URL-path like "/media/.."
                if pic_str.startswith("/"):
                    url_path = pic_str
                else:
                    # 3) If stored like "profile/x.png", convert to "/media/profile/x.png" (or storage URL)
                    url_path = default_storage.url(pic_str)

                # 4) Make absolute for Flutter
                final_url = request.build_absolute_uri(url_path) if request else url_path

            mp[row["society_id"]].append(final_url)

        self._cached_random_images_map = dict(mp)
        return self._cached_random_images_map

    def get_random_member_images(self, obj):
        return self._random_images_map().get(obj.id, [])

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["created_by"] = user
        society = super().create(validated_data)
        SocietyMember.objects.create(society=society, user=user, is_admin=True)
        return society


class SocietyMemberSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer(read_only=True)

    class Meta:
        model = SocietyMember
        fields = ["id", "user", "is_admin", "joined_at"]


class SocietyMessageSerializer(serializers.ModelSerializer):
    sender = SimpleUserSerializer(read_only=True)

    class Meta:
        model = SocietyMessage
        fields = ["id", "society", "sender", "content", "message_type", "attachment", "created_at"]
        read_only_fields = ["id", "sender", "created_at"]

