import logging
from typing import Dict

# Django
from django.shortcuts import render, get_object_or_404
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Prefetch
from django.contrib.auth import get_user_model

# DRF
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

# Local
from .serializers import (
    SignupSerialzier,
    VerifyOTPSerializer,
    ResendVerifyOTPSerializer,
    LoginSerializer,
    ForgetPasswordSerializer,
    VerifyForgetPasswordOTPSerializer,
    ResetPasswordSerializer,
    UserSerializer, UserProfileUpdateSerializer
)
from account.utils import generate_tokens_for_user


logger = logging.getLogger(__name__)

User = get_user_model()



class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerialzier(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        tokens = generate_tokens_for_user(user)

        return Response(
            {
                "success": True,
                "message": "Registration successful. OTP sent via SMS.",
                "data": {
                    "user_id": user.user_id,
                    "email": user.email,
                    "phone": user.phone,
                    "username": user.username,
                    "is_verified": user.is_verified,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyOTPAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        tokens = generate_tokens_for_user(user)

        return Response(
            {
                "success": True,
                "message": "OTP verified successfully.",
                "data": {
                    "tokens": {
                        "access": tokens["access"],
                    },
                    "user": {
                        "id": user.user_id,
                        "email": user.email,
                        "full_name": user.get_full_name() if hasattr(user, "get_full_name") else None,
                        "is_verified": user.is_verified,
                    },
                },
            },
            status=status.HTTP_200_OK,
        )


class ResendVerifyOTPAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResendVerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "success": True,
                "message": "A new OTP has been sent to your email.",
                "data": {},
            },
            status=status.HTTP_200_OK,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        tokens = generate_tokens_for_user(user)
        user_data = UserSerializer(user, context={"request": request}).data

        return Response(
            {
                "success": True,
                "message": "Login successful",
                "data": {
                    "user": user_data,
                    "tokens": {
                        "access": tokens["access"],
                        "refresh": tokens["refresh"],
                    },
                },
            },
            status=status.HTTP_200_OK,
        )


class ForgetPasswordView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = ForgetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "success": True,
                "message": "OTP sent to user email successfully.",
                "data": {},
            },
            status=status.HTTP_200_OK,
        )


class VerifyForgetPasswordOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyForgetPasswordOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        response_data = serializer.to_representation(serializer.validated_data)

        return Response(
            {
                "success": True,
                "message": "OTP verified successfully.",
                "data": response_data,
            },
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ResetPasswordSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "success": True,
                "message": "Password reset successfully.",
                "data": {},
            },
            status=status.HTTP_200_OK,
        )


# profile update

class UserProfileUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def patch(self, request):
        user = request.user

        serializer = UserProfileUpdateSerializer(
            user,
            data=request.data,
            partial=True,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            serializer.save()

        return Response(
            {   
                "success": True,
                "message": "Profile updated successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
        
# get user profile
class UserProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user, context={"request": request})
        return Response({
            'success': True,
            'message': 'User profile fetched successfully',
            "data": serializer.data}, status=status.HTTP_200_OK)
        
#delete profile
class UserProfileHardDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        request.user.delete()
        return Response({"success": True, "message": "Account permanently deleted."}, status=200)
    
    


# pop image view
from .serializers import MakeYourProfilePopSerializer
from account.models import MakeYourProfilePop
class PopImageListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        images = MakeYourProfilePop.objects.filter(user=request.user)
        serializer = MakeYourProfilePopSerializer(images, many=True)
        return Response(
            {   "success": True,
                "message": "Pop images fetched successfully",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

    def post(self, request):
        images = request.FILES.getlist("image")  # multiple files
        saved_images = []

        if not images:
            return Response(
                {"success": False, "message": "No images provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if request.user.pop_images.count() + len(images) > 7:
            return Response(
                {"success": False, "message": "You can upload a maximum of 7 pop-up images."},
                status=status.HTTP_400_BAD_REQUEST
            )

        for img in images:
            serializer = MakeYourProfilePopSerializer(
                data={"image": img},
                context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(user=request.user)
            saved_images.append(serializer.data)

        return Response(
            {   "success": True,
                "message": f"{len(saved_images)} pop images uploaded successfully",
                "data": saved_images
            },
            status=status.HTTP_201_CREATED
        )




class PopImageRetrieveUpdateDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        return get_object_or_404(MakeYourProfilePop, pk=pk, user=user)

    def get(self, request, pk):
        image = self.get_object(pk, request.user)
        serializer = MakeYourProfilePopSerializer(image)
        return Response(
            {   "success": True,
                "message": "Pop image fetched successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK
        )

    def put(self, request, pk):
        image = self.get_object(pk, request.user)
        serializer = MakeYourProfilePopSerializer(
            image,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "success": True,
                "message": "Pop image updated successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK
        )

    def delete(self, request, pk):
        image = self.get_object(pk, request.user)
        image.delete()
        return Response(
            {   "success": True,
                "message": "Pop image deleted successfully"
            },
            status=status.HTTP_204_NO_CONTENT
        )