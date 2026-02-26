from django.urls import path
from .views import (
    RegisterAPIView, VerifyOTPAPIView, ResendVerifyOTPAPIView, LoginView, ForgetPasswordView, 
    VerifyForgetPasswordOTPView, ResetPasswordView, UserProfileUpdateAPIView, 
    UserProfileAPIView, UserProfileHardDeleteAPIView, PopImageListCreateAPIView, PopImageRetrieveUpdateDeleteAPIView,
    GlobalFeedAPIView, UserDetailsProfileAPIView, LikeUserAPIView, UnlikeUserAPIView, WhoLikedUserAPIView, UserSearchAPIView, UserFilterAPIView, GoogleLoginAPIView)

urlpatterns = [
    path("signup/", RegisterAPIView.as_view(), name="user-register"),
    path("verify-otp/registration/", VerifyOTPAPIView.as_view(), name="verify-otp"),
    path("resend-otp/", ResendVerifyOTPAPIView.as_view(), name="resend-otp"),
    path('login/', LoginView.as_view(), name="login"),
    path("forget-password/", ForgetPasswordView.as_view(), name="forget-password"),
    path("password/verify-otp/", VerifyForgetPasswordOTPView.as_view(), name="verify-otp"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),
    
    #update profile
    path("profile/update/", UserProfileUpdateAPIView.as_view(), name="profile-update"),
    # get profile
    path("profile/details/", UserProfileAPIView.as_view(), name="profile-get"),
    # delete profile
    path("profile/delete/", UserProfileHardDeleteAPIView.as_view(), name="profile-delete"),
    
    # pop image urls
    path("pop-images/", PopImageListCreateAPIView.as_view(), name="pop-image-list-create"),
    path("pop-images/<int:pk>/", PopImageRetrieveUpdateDeleteAPIView.as_view(), name="pop-image-detail"),
    
    # global feed
    path("feed/global/", GlobalFeedAPIView.as_view(), name="global-feed"),
    
    # user details profile
    path("user/<str:identifier>/", UserDetailsProfileAPIView.as_view(), name="user-profile"),
    
    #liked and unliked
    path('user/<int:user_id>/like/', LikeUserAPIView.as_view(), name='like-user'),
    path('user/<int:user_id>/unlike/', UnlikeUserAPIView.as_view(), name='unlike-user'),
    path("who-liked-me/", WhoLikedUserAPIView.as_view(), name="who-liked-me"),
    
    # search and filter
    path("users/search/", UserSearchAPIView.as_view(), name="user-search"),
    path("users/filter/", UserFilterAPIView.as_view(), name="user-filter"),
    
    #google auth
    path('googleLogin/', GoogleLoginAPIView.as_view(), name='google-login'),
]
