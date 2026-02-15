# chat/routing.py (or your existing routing file)
from django.urls import re_path
from .consumers import ChatConsumer, SocietyConsumer

websocket_urlpatterns = [
    re_path(r"ws/chat/(?P<thread_id>\d+)/$", ChatConsumer.as_asgi()),      # existing (private)
    re_path(r"ws/society/(?P<society_id>\d+)/$", SocietyConsumer.as_asgi()),    # new (society)
]
