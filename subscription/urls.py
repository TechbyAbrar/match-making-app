from django.urls import path

from .views import SubscriptionDetailAPIView, SubscriptionSyncAPIView

urlpatterns = [
    path("sync/", SubscriptionSyncAPIView.as_view(), name="subscription-sync"),
    path("me/", SubscriptionDetailAPIView.as_view(), name="subscription-detail"),
]