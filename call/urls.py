from django.urls import path
from .views import (
    start_call, 
    agora_token,
    accept_call,
    reject_call,
    end_call,
    call_status,
)
        

urlpatterns = [
    path("start/", start_call),
    path("agora-token/", agora_token),
    path("<uuid:call_id>/accept/", accept_call),
    path("<uuid:call_id>/reject/", reject_call),
    path("<uuid:call_id>/end/", end_call),
    path("<uuid:call_id>/status/", call_status),
]

