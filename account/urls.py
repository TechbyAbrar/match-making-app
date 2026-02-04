from django.urls import path
from .views import (
    RegisterAPIView, VerifyOTPAPIView, ResendVerifyOTPAPIView, LoginView, ForgetPasswordView, VerifyForgetPasswordOTPView, ResetPasswordView)

urlpatterns = [
    path("signup/", RegisterAPIView.as_view(), name="user-register"),
    path("verify-otp/registration/", VerifyOTPAPIView.as_view(), name="verify-otp"),
    path("resend-otp/", ResendVerifyOTPAPIView.as_view(), name="resend-otp"),
    path('login/', LoginView.as_view(), name="login"),
    path("forget-password/", ForgetPasswordView.as_view(), name="forget-password"),
    path("password/verify-otp/", VerifyForgetPasswordOTPView.as_view(), name="verify-otp"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),
]
