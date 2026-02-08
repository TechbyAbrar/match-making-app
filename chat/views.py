import logging
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework import permissions
from django.db.models import Q
from .models import ChatThread, Message
from .serializers import ThreadListSerializer, MessageSerializer
from .pagination import MessagePagination
from core.utils import ResponseHandler  

logger = logging.getLogger(__name__)


class ThreadListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        threads = ChatThread.objects.filter(Q(user_a=request.user) | Q(user_b=request.user))
        serializer = ThreadListSerializer(threads, many=True, context={"request": request})
        return ResponseHandler.success(data=serializer.data)

    def post(self, request):
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
        thread_id = request.query_params.get("thread")
        if not thread_id:
            return ResponseHandler.bad_request(errors={"thread": "Query parameter is required."})

        thread = get_object_or_404(ChatThread, pk=thread_id)

        if request.user.pk not in [thread.user_a_id, thread.user_b_id]:
            return ResponseHandler.forbidden(message="You are not a participant in this thread.")

        messages = (
            Message.objects.filter(thread=thread)
            .select_related("sender")
            .order_by("created_at")
        )

        serializer = MessageSerializer(messages, many=True, context={"request": request})
        return ResponseHandler.success(data=serializer.data)

    def post(self, request):
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
