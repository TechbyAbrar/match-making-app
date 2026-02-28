# views.py

import logging

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q, Subquery
from django.shortcuts import get_object_or_404

from rest_framework import parsers, permissions, serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from account.presence import touch_chat_presence
from core.utils import ResponseHandler

from .models import (
    ChatThread,
    Message,
    Society,
    SocietyMember,
    SocietyMessage,
)
from .pagination import MessagePagination
from .serializers import (
    MessageSerializer,
    SocietyMemberSerializer,
    SocietyAddMembersSerializer,
    SocietyMessageSerializer,
    SocietySerializer,
    ThreadListSerializer,
)

logger = logging.getLogger(__name__)
User = get_user_model()

class ThreadListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        touch_chat_presence(request.user)
        threads = ChatThread.objects.filter(Q(user_a=request.user) | Q(user_b=request.user))
        serializer = ThreadListSerializer(threads, many=True, context={"request": request})
        return ResponseHandler.success(data=serializer.data)

    def post(self, request):
        touch_chat_presence(request.user)
        other_id = request.data.get("other_user_id")
        if not other_id:
            return ResponseHandler.bad_request(errors={"other_user_id": "This field is required."})
        if int(other_id) == request.user.pk:
            return ResponseHandler.bad_request(message="Cannot create thread with self.")
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        other = get_object_or_404(User, pk=other_id)
        thread = ChatThread.get_or_create_thread(request.user, other)
        serializer = ThreadListSerializer(thread, context={"request": request})
        return ResponseHandler.created(data=serializer.data)


class MessageListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = MessagePagination

    def get(self, request):
        touch_chat_presence(request.user)
        thread_id = request.query_params.get("thread")
        if not thread_id:
            return ResponseHandler.bad_request(errors={"thread": "Query parameter is required."})

        thread = get_object_or_404(ChatThread, pk=thread_id)

        if request.user.pk not in [thread.user_a_id, thread.user_b_id]:
            return ResponseHandler.forbidden(message="You are not a participant in this thread.")
        
        # added two lines to reset unread count when messages are fetched
        key = f"chat:unread:{request.user.pk}:{thread.pk}"
        cache.set(key, 0, timeout=7 * 24 * 3600)

        messages = (
            Message.objects.filter(thread=thread)
            .select_related("sender")
            .order_by("created_at")
        )

        serializer = MessageSerializer(messages, many=True, context={"request": request})
        return ResponseHandler.success(data=serializer.data)

    def post(self, request):
        touch_chat_presence(request.user)
        serializer = MessageSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        message = serializer.save()

        # Update unread count atomically
        thread = message.thread
        receiver_id = thread.user_b_id if message.sender_id == thread.user_a_id else thread.user_a_id
        key = f"chat:unread:{receiver_id}:{thread.pk}"
        if cache.get(key) is not None:
            cache.incr(key, 1)
        else:
            cache.set(key, 1, timeout=7*24*3600)

        return ResponseHandler.created(data=serializer.data)



#society
class SocietyListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (
        parsers.MultiPartParser,
        parsers.FormParser,
        parsers.JSONParser,
    )
    
    # def get(self, request):
    #     touch_chat_presence(request.user)

    #     societies = (
    #         Society.objects
    #         .filter(members__user=request.user)
    #         .distinct()
    #         .annotate(member_count=Count("members", distinct=True))
    #     )

    #     return ResponseHandler.success(
    #         data=SocietySerializer(societies, many=True, context={"request": request}).data
    #     )
    
    def get(self, request):
        touch_chat_presence(request.user)

        society_ids = SocietyMember.objects.filter(
            user=request.user
        ).values("society_id")

        societies = (
            Society.objects
            .filter(id__in=Subquery(society_ids))
            .annotate(member_count=Count("members", distinct=True))
            .distinct()
        )

        return ResponseHandler.success(
            data=SocietySerializer(societies, many=True, context={"request": request}).data
        )

    # @transaction.atomic
    # def post(self, request):
    #     touch_chat_presence(request.user)
    #     serializer = SocietySerializer(
    #         data=request.data,
    #         context={"request": request},
    #     )
    #     serializer.is_valid(raise_exception=True)

    #     society = serializer.save()  # name + image

    #     return ResponseHandler.created(
    #         data=SocietySerializer(society).data
    #     )
    
    @transaction.atomic
    def post(self, request):
        touch_chat_presence(request.user)

        serializer = SocietySerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        society = serializer.save()

        # ✅ This is correct because of related_name="members"
        society.member_count = society.members.count()

        return ResponseHandler.created(
            data=SocietySerializer(society, context={"request": request}).data
        )

class SocietyAddMembersAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, society_id):
        touch_chat_presence(request.user)

        serializer = SocietyAddMembersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_ids = serializer.validated_data["normalized_user_ids"]

        society = get_object_or_404(Society, pk=society_id)

        # ✅ Only admin/creator can add members
        is_admin = SocietyMember.objects.filter(
            society=society,
            user=request.user,
            is_admin=True
        ).exists()
        if not is_admin:
            return ResponseHandler.forbidden(message="Only creator/admin can add members.")

        # ✅ Fetch valid users in ONE query (your PK is user_id)
        existing_user_ids = set(
            User.objects.filter(user_id__in=user_ids).values_list("user_id", flat=True)
        )

        invalid_user_ids = [uid for uid in user_ids if uid not in existing_user_ids]
        valid_user_ids = [uid for uid in user_ids if uid in existing_user_ids]

        if not valid_user_ids:
            return ResponseHandler.bad_request(
                errors={"user_ids": "No valid users found in the request."}
            )

        # ✅ Fetch already-members in ONE query
        already_member_ids = set(
            SocietyMember.objects.filter(
                society=society,
                user_id__in=valid_user_ids
            ).values_list("user_id", flat=True)
        )

        to_create_ids = [uid for uid in valid_user_ids if uid not in already_member_ids]

        # ✅ Bulk insert (safe with your unique_together)
        new_rows = [SocietyMember(society=society, user_id=uid) for uid in to_create_ids]
        SocietyMember.objects.bulk_create(new_rows, ignore_conflicts=True)

        already_member_ordered = [uid for uid in valid_user_ids if uid in already_member_ids]

        return ResponseHandler.success(
            message="Member add processed successfully.",
            data={
                "requested": user_ids,
                "added": to_create_ids,
                "already_member": already_member_ordered,
                "invalid_user": invalid_user_ids,
                "count": {
                    "requested": len(user_ids),
                    "added": len(to_create_ids),
                    "already_member": len(already_member_ordered),
                    "invalid_user": len(invalid_user_ids),
                }
            }
        )

class SocietyMessageListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (
        parsers.MultiPartParser,
        parsers.FormParser,
        parsers.JSONParser,
    )

    def get(self, request, society_id):
        touch_chat_presence(request.user)
        society = get_object_or_404(Society, pk=society_id)

        if not SocietyMember.objects.filter(society=society, user=request.user).exists():
            return ResponseHandler.forbidden(message="You are not a member of this society.")

        qs = (
            SocietyMessage.objects
            .filter(society=society)
            .select_related("sender")
            .order_by("created_at")
        )
        return ResponseHandler.success(
            data=SocietyMessageSerializer(qs, many=True).data
        )

    @transaction.atomic
    def post(self, request, society_id):
        touch_chat_presence(request.user)
        society = get_object_or_404(Society, pk=society_id)

        member = SocietyMember.objects.filter(society=society, user=request.user).first()
        if not member:
            return ResponseHandler.forbidden(message="You are not a member of this society.")

        content = (request.data.get("content") or "").strip()
        attachment = request.FILES.get("attachment")

        if not content and not attachment:
            raise ValidationError("Message must contain text or an attachment.")

        message_type = "image" if attachment else "text"

        msg = SocietyMessage.objects.create(
            society=society,
            sender=request.user,
            content=content,
            attachment=attachment,
            message_type=message_type,
        )

        return ResponseHandler.created(
            data=SocietyMessageSerializer(msg).data
        )   
        

