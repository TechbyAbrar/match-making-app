# chat/urls.py
from django.urls import path
from .views import ThreadListCreateAPIView, MessageListCreateAPIView, SocietyListCreateAPIView, SocietyAddMemberAPIView, SocietyMessageListAPIView

urlpatterns = [
    path("threads/", ThreadListCreateAPIView.as_view(), name="thread-list-create"),
    path("messages/", MessageListCreateAPIView.as_view(), name="message-list-create"),
    
    #society
    path("societies/", SocietyListCreateAPIView.as_view()),
    path("societies/<int:society_id>/members/", SocietyAddMemberAPIView.as_view()),
    path("societies/<int:society_id>/messages/", SocietyMessageListAPIView.as_view()),
]
