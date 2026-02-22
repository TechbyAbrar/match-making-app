from rest_framework import serializers
from .models import Story
from .services import get_story_view_count, StoryLikeService
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import ProfileShare, UserBlock, Report, ReportReason, StoryLike, UserFace, Notification


User = get_user_model()

# STORY SERIALIZERS
class StorySerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)
    view_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()

    class Meta:
        model = Story
        fields = ['id', 'user','user_full_name', 'text', 'media', 'view_count', 'likes_count', 'is_liked', 'created_at', 'expires_at']

    def get_view_count(self, obj):
        return obj.view_count + get_story_view_count(obj.id)
    
    def get_is_liked(self, obj):
        """
        Returns True if the current user has liked this story.
        Safe handling if request context is missing.
        """
        request = self.context.get('request', None)
        if request is None or request.user.is_anonymous:
            return False
        return StoryLikeService.is_liked(obj, request.user)

    def get_likes_count(self, obj):
        """
        Returns the total number of likes for the story.
        """
        return obj.likes_count  # use cached field for efficiency


class CreateStorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Story
        fields = ['text', 'media']

    def validate(self, attrs):
        if not attrs.get('text') and not attrs.get('media'):
            raise serializers.ValidationError("You must include text or media.")
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        return Story.objects.create(user=user, **validated_data)




# PROFILE SHARING SERIALIZERS

class ShareRequestSerializer(serializers.Serializer):
    target = serializers.CharField(required=True)


class ProfileShareSerializer(serializers.ModelSerializer):
    sharer_username = serializers.CharField(source="sharer.username", read_only=True)
    shared_username = serializers.CharField(source="shared_user.username", read_only=True)
    profile_link = serializers.CharField(source="shared_user.profile_link", read_only=True)

    class Meta:
        model = ProfileShare
        fields = ["id", "sharer_username", "shared_username", "profile_link", "created_at"]


#Block
# users/serializers.py

class UserBlockSerializer(serializers.ModelSerializer):
    blocked_user_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = UserBlock
        fields = ['blocked_user_id']

    def validate_blocked_user_id(self, value):
        if value == self.context['request'].user.user_id:
            raise serializers.ValidationError("You cannot block yourself.")
        if not User.objects.filter(user_id=value).exists():
            raise serializers.ValidationError("User does not exist.")
        return value

# report profile serializer

class CreateReportSerializer(serializers.ModelSerializer):
    reason = serializers.ChoiceField(choices=ReportReason.choices)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    class Meta:
        model = Report
        fields = ("reported_user", "reason", "comment")

    def validate_reported_user(self, value):
        # Prevent reporting self
        user = self.context["request"].user
        if value == user:
            raise serializers.ValidationError("You cannot report your own profile.")
        return value



# face recognition serializer
class UserFaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserFace
        fields = ['user', 'face_image']


# notifications/serializers.py

from rest_framework import serializers
from .models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'recipient', 'sender', 'sender_username', 
            'type', 'message', 'metadata', 'is_read', 'created_at'
        ]
        read_only_fields = ['id', 'recipient', 'sender', 'sender_username', 'created_at']

