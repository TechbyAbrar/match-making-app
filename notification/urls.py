# FIX: was completely empty
from django.urls import path
from . import views

app_name = "notifications"

urlpatterns = [
    # --- Device management ---
    path("devices/register/",   views.DeviceRegisterView.as_view(),   name="device-register"),
    path("devices/deregister/", views.DeviceDeregisterView.as_view(), name="device-deregister"),

    # --- In-app inbox ---
    path("",              views.NotificationListView.as_view(),      name="notification-list"),
    path("unread-count/", views.NotificationUnreadCountView.as_view(), name="unread-count"),
    path("read-all/",     views.NotificationMarkAllReadView.as_view(), name="read-all"),
    path("<uuid:delivery_id>/read/", views.NotificationMarkReadView.as_view(), name="mark-read"),

    # --- Preferences ---
    path("preferences/", views.NotificationPreferenceView.as_view(), name="preferences"),
]