from django.urls import path
from .views import RevenueCatWebhookView, AdminDashboardAPIView

urlpatterns = [
    path("webhooks/revenuecat/", RevenueCatWebhookView.as_view(), name="revenuecat-webhook"),
    path("admin-dashboard/", AdminDashboardAPIView.as_view(), name="admin-dashboard"),
]
