import logging
from typing import Dict

# Django
from django.shortcuts import render, get_object_or_404
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Prefetch
from django.contrib.auth import get_user_model
from django.db.models import Q
from datetime import date


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
    UserSerializer, UserProfileUpdateSerializer, WhoLikedUserSerializer,
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
        




# Global Feed View
from core.utils import ResponseHandler
class GlobalFeedPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50

class GlobalFeedAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            current_user = request.user

            users_qs = User.objects.filter(is_active=True).exclude(pk=current_user.pk).only(
                "user_id", "username", "full_name", "is_online", "hobbies"
            )

            paginator = GlobalFeedPagination()
            page = paginator.paginate_queryset(users_qs, request)

            feed_data = []
            for user in page:
                # Only last updated pop image
                last_image = user.pop_images.order_by("-updated_at").first()
                pop_images_serialized = MakeYourProfilePopSerializer(
                    [last_image], many=True, context={"request": request}
                ).data if last_image else []

                feed_data.append({
                    "user_id": user.user_id,
                    "username": user.username or "",
                    "full_name": user.full_name or "",
                    "is_online": user.is_online,
                    "hobbies": user.hobbies or [],
                    "pop_images": pop_images_serialized,
                })

            return ResponseHandler.success(
                message="Global feed fetched successfully.",
                data=paginator.get_paginated_response(feed_data).data
            )

        except Exception as exc:
            return ResponseHandler.server_error(
                message="Failed to fetch global feed.",
                errors=str(exc)
            )


# get a user profile by username
class UserDetailsProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, identifier):
        try:
            # Determine if identifier is numeric (user_id) or string (username)
            if identifier.isdigit():
                user = get_object_or_404(User, user_id=int(identifier), is_active=True)
            else:
                user = get_object_or_404(User, username=identifier, is_active=True)

            serializer = UserSerializer(user, context={"request": request})
            return ResponseHandler.success(
                message="User profile fetched successfully.",
                data=serializer.data
            )

        except Exception as exc:
            return ResponseHandler.server_error(
                message="Failed to fetch user profile.",
                errors=str(exc)
            )
            

#liked and unliked user views
from .services import UserLikeService
class LikeUserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        try:
            UserLikeService.like_user(request.user, user_id)
            return ResponseHandler.success(message="User liked.", data={"liked": True})
        except ValueError as e:
            return ResponseHandler.bad_request(message=str(e))
        except Exception as e:
            logger.exception("Error liking user")
            return ResponseHandler.generic_error(exception=e)

class UnlikeUserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        try:
            UserLikeService.unlike_user(request.user, user_id)
            return ResponseHandler.success(message="User unliked.", data={"liked": False})
        except ValueError as e:
            return ResponseHandler.bad_request(message=str(e))
        except Exception as e:
            logger.exception("Error unliking user")
            return ResponseHandler.generic_error(exception=e)


class WhoLikedUserAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination

    def get_cache_key(self, user_id: int, page: int, page_size: int) -> str:
        return f"who_liked:{user_id}:page:{page}:size:{page_size}"

    def get(self, request):
        user = request.user
        user_id = getattr(user, "user_id", None) or getattr(user, "id")

        paginator = self.pagination_class()

        # Resolve page params
        page_number = request.query_params.get(paginator.page_query_param, "1")
        page_size = paginator.get_page_size(request) or paginator.page_size or 20

        cache_key = self.get_cache_key(user_id, page_number, page_size)

        # Try cache
        try:
            cached_payload = cache.get(cache_key)
        except Exception as exc:
            logger.warning(
                "Cache GET failed for who-liked",
                extra={"user_id": user_id, "exc": str(exc)},
            )
            cached_payload = None

        if cached_payload:
            logger.info("who-liked cache hit", extra={"user_id": user_id})
            return ResponseHandler.success(
                message=f"{cached_payload['pagination']['count']} users liked your profile.",
                data=cached_payload["results"],
                extra={"pagination": cached_payload["pagination"]},
            )

        # Query set
        try:
            qs = UserLikeService.who_liked_user(user_id)
        except Exception as exc:
            return ResponseHandler.generic_error(exception=exc)

        # Pagination
        page = paginator.paginate_queryset(qs, request, view=self)

        serialized = WhoLikedUserSerializer(
            page, many=True, context={"request": request}
        ).data

        # Count safely
        try:
            total_count = qs.count()
        except Exception:
            total_count = len(list(qs))

        pagination = {
            "count": total_count,
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
            "page": int(page_number),
            "page_size": page_size,
        }

        payload = {"results": serialized, "pagination": pagination}

        # Try caching response
        try:
            CACHE_TTL = 15 # seconds
            cache.set(cache_key, payload, CACHE_TTL)
        except Exception as exc:
            logger.warning("Cache SET failed", extra={"exc": str(exc)})

        return ResponseHandler.success(
            message=f"{total_count} users liked your profile.",
            data=serialized,
            extra={"pagination": pagination},
        )
        

CACHE_TTL = 30  # seconds
class UserSearchAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            
            query = request.query_params.get("q", "").strip()
            if not query:
                return ResponseHandler.bad_request(message="Query param 'q' is required.")

            cache_key = f"user_search:{query}"
            users = cache.get(cache_key)

            if not users:
                users = User.objects.filter(
                    Q(username__icontains=query) |
                    Q(full_name__icontains=query) |
                    Q(email__icontains=query)
                ).order_by("-created_at")[:50]
                cache.set(cache_key, users, CACHE_TTL)

            serializer = WhoLikedUserSerializer(users, many=True, context={"request": request})
            return ResponseHandler.success(data=serializer.data)

        except Exception as e:
            return ResponseHandler.generic_error(exception=e)
        


class UserFilterAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            gender = request.query_params.get("gender")
            min_age = request.query_params.get("min_age")
            max_age = request.query_params.get("max_age")
            max_distance = request.query_params.get("max_distance")

            filters = Q()

            if gender:
                filters &= Q(gender__iexact=gender)  # case insensitive

            today = date.today()

            if min_age:
                min_age = int(min_age)
                max_dob = date(today.year - min_age, today.month, today.day)
                filters &= Q(dob__lte=max_dob)

            if max_age:
                max_age = int(max_age)
                min_dob = date(today.year - max_age, today.month, today.day)
                filters &= Q(dob__gte=min_dob)

            if max_distance:
                filters &= Q(distance__lte=int(max_distance))

            cache_key = f"user_filter:{gender}:{min_age}:{max_age}:{max_distance}"
            users = cache.get(cache_key)

            if not users:
                users = (
                    User.objects
                    .filter(filters)
                    .order_by("-created_at")[:50]
                )
                cache.set(cache_key, users, CACHE_TTL)

            serializer = WhoLikedUserSerializer(users, many=True, context={"request": request})
            return ResponseHandler.success(data=serializer.data)

        except ValueError:
            return ResponseHandler.error(message="Invalid filter values", status=400)

        except Exception as e:
            return ResponseHandler.generic_error(exception=e)
