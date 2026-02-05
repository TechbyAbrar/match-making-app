from django.urls import path
from .views import (
    RegisterAPIView, VerifyOTPAPIView, ResendVerifyOTPAPIView, LoginView, ForgetPasswordView, 
    VerifyForgetPasswordOTPView, ResetPasswordView, UserProfileUpdateAPIView, 
    UserProfileAPIView, UserProfileHardDeleteAPIView, PopImageListCreateAPIView, PopImageRetrieveUpdateDeleteAPIView)

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
    # delte profile
    path("profile/delete/", UserProfileHardDeleteAPIView.as_view(), name="profile-delete"),
    
    # pop image urls
    path("pop-images/", PopImageListCreateAPIView.as_view(), name="pop-image-list-create"),
    path("pop-images/<int:pk>/", PopImageRetrieveUpdateDeleteAPIView.as_view(), name="pop-image-detail"),
]
