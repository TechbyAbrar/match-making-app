# chat/urls.py
from django.urls import path
from .views import ThreadListCreateAPIView, MessageListCreateAPIView

urlpatterns = [
    path("threads/", ThreadListCreateAPIView.as_view(), name="thread-list-create"),
    path("messages/", MessageListCreateAPIView.as_view(), name="message-list-create"),
]
