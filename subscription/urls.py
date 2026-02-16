from django.urls import path
from .views import RevenueCatWebhookView

urlpatterns = [
    path("revenuecat/webhook/", RevenueCatWebhookView.as_view(), name="revenuecat-webhook"),
]
