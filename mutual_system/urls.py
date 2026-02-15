from django.urls import path
from .views import (
    StoryCreateAPIView, MyStoriesAPIView, StoryDeleteAPIView,
    StoryViewAPIView, StoryViewersAPIView, GlobalStoriesAPIView, 
    ShareProfileAPIView, PublicProfileLinkAPIView,
    BlockedUserListView, BlockUserView, UnblockUserView, 
    CreateReportAPIView, AdminAggregatedReportsAPIView, StoryLikeAPIView, StoryUnlikeAPIView, UserStoriesAPIView, NotificationListView, NotificationMarkReadView, NotificationUnreadCountView
)

# FaceScanView

urlpatterns = [
    path('create/story/', StoryCreateAPIView.as_view(), name='post-story'),
    path('my/story/', MyStoriesAPIView.as_view(), name='my-stories'),
    path('story/<uuid:story_id>/delete/', StoryDeleteAPIView.as_view(), name='delete-story'),
    path('story/<uuid:story_id>/view/', StoryViewAPIView.as_view(), name='view-story'),
    path('story/<uuid:story_id>/viewers/', StoryViewersAPIView.as_view(), name='story-viewers'),
    path('story/global/', GlobalStoriesAPIView.as_view(), name='global-stories'),
    
    # story like and unlike apis
    path('stories/<uuid:story_id>/like/', StoryLikeAPIView.as_view(), name='story-like'),
    path('stories/<uuid:story_id>/unlike/', StoryUnlikeAPIView.as_view(), name='story-unlike'),
    
    # user stories
    path('stories/<uuid:story_id>/user/', UserStoriesAPIView.as_view(), name='user-stories'),
    
    # share profile apis
    path("share/", ShareProfileAPIView.as_view(), name="share-profile"),
    path("profile-link/<str:username>/", PublicProfileLinkAPIView.as_view(), name="public-profile-link"),
    
    # block apis
    path("block/", BlockUserView.as_view(), name="user-block"),
    path("unblock/", UnblockUserView.as_view(), name="user-unblock"),
    path("block-list/", BlockedUserListView.as_view(), name="user-blocked-list"),
    
    # report
    path("reports/", CreateReportAPIView.as_view(), name="create-report"),
    path("admin/reports/aggregated/", AdminAggregatedReportsAPIView.as_view(), name="admin-aggregated-reports"),
    
    # face recognition api
    # path('scan-face/', FaceScanView.as_view(), name='scan-face'),
    
    #notifications
    path('notifications/', NotificationListView.as_view(), name='notifications-list'),
    path('notifications/<int:pk>/mark-read/', NotificationMarkReadView.as_view(), name='notification-mark-read'),
    path('notifications/unread-count/', NotificationUnreadCountView.as_view(), name='notifications-unread-count'),
    
]
