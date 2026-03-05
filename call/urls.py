from django.urls import path
from .views import start_call, agora_token

urlpatterns = [
    path("start/", start_call),
    path("agora-token/", agora_token),
]

