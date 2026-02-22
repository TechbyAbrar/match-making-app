import logging
import random
import uuid
import base64

# import face_recognition
from PIL import Image

from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile

from rest_framework import status, permissions
from rest_framework.permissions import (
    IsAuthenticated,
    AllowAny,
    IsAdminUser,
)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from core.utils import ResponseHandler

from .models import Story, UserFace

from .serializers import (
    StorySerializer,
    CreateStorySerializer,
    ShareRequestSerializer,
    ProfileShareSerializer,
    UserBlockSerializer,
    CreateReportSerializer,
    UserFaceSerializer,
)

from .services import (
    add_story_view,
    get_story_viewers,
    create_share,
    UserBlockService,
    ReportService,
    ReportServiceError,
)

from .models import Notification
from .serializers import NotificationSerializer

logger = logging.getLogger(__name__)
User = get_user_model()



class SmallPagination(PageNumberPagination):
    page_size = 10
    max_page_size = 50


# ------------------ POST STORY ------------------
class StoryCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @transaction.atomic
    def post(self, request):
        try:
            serializer = CreateStorySerializer(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            story = serializer.save()
            logger.info(f"User {request.user.user_id} posted a story {story.id}")
            return ResponseHandler.created(
                message="Story created successfully.",
                data=StorySerializer(story).data
            )
        except Exception as e:
            logger.exception(f"Error creating story for user {request.user.user_id}")
            return ResponseHandler.generic_error(exception=e)


# ------------------ GET MY STORIES ------------------
class MyStoriesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            stories = Story.objects.filter(
                user=request.user,
                expires_at__gt=timezone.now(),
                is_deleted=False
            ).only('id', 'text', 'media', 'view_count', 'created_at', 'expires_at')
            
            return ResponseHandler.success(
                message="Fetched user stories successfully.",
                data=StorySerializer(stories, many=True).data,
                extra={"count": stories.count()}
            )
        except Exception as e:
            logger.exception(f"Error fetching stories for user {request.user.user_id}")
            return ResponseHandler.generic_error(exception=e)


# ------------------ DELETE STORY ------------------
class StoryDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, story_id):
        try:
            story = get_object_or_404(Story, id=story_id, user=request.user, is_deleted=False)
            story.is_deleted = True
            story.save(update_fields=['is_deleted'])
            logger.info(f"User {request.user.user_id} deleted story {story_id}")
            return ResponseHandler.deleted(message="Story deleted successfully.")
        except Exception as e:
            logger.exception(f"Error deleting story {story_id} for user {request.user.user_id}")
            return ResponseHandler.generic_error(exception=e)

class StoryViewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, story_id):
        """
        Record a story view and return other active stories by the same user.
        """
        try:
            # Fetch the story by UUID
            story = get_object_or_404(
                Story,
                id=story_id,
                expires_at__gt=timezone.now(),
                is_deleted=False
            )

            # Prevent users from viewing their own story
            if story.user.user_id == request.user.user_id:
                return ResponseHandler.bad_request(message="You cannot view your own story.")

            # Record the view
            add_story_view(story_id, request.user.user_id)

            # Fetch other active stories by the same user (exclude current one)
            other_stories = Story.objects.filter(
                user__user_id=story.user.user_id,
                expires_at__gt=timezone.now(),
                is_deleted=False
            ).exclude(id=story_id).order_by('created_at')

            # Serialize other stories
            serialized_stories = StorySerializer(
                other_stories,
                many=True,
                context={'request': request}
            ).data

            return ResponseHandler.success(
                message="View recorded.",
                data={
                    "story_id": str(story.id),  # UUID string
                    "user_id": story.user.user_id,  # use user_id
                    "other_stories": serialized_stories
                }
            )

        except Exception as e:
            logger.exception(f"Error recording view for story {story_id} by user {request.user.user_id}")
            return ResponseHandler.generic_error(exception=e)

# ------------------ VIEWERS LIST ------------------
class StoryViewersAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, story_id):
        try:
            story = get_object_or_404(Story, id=story_id, user=request.user, is_deleted=False)
            page = int(request.query_params.get('page', 1))
            limit = int(request.query_params.get('page_size', 20))
            offset = (page - 1) * limit

            viewer_ids, total = get_story_viewers(story_id, offset, limit)
            viewers = User.objects.filter(user_id__in=viewer_ids).only('user_id', 'full_name', 'profile_pic')

            data = [{"id": u.user_id,"full_name": u.full_name,"profile_pic": u.profile_pic.url if u.profile_pic else None} for u in viewers]
            return ResponseHandler.success(
                message="Fetched story viewers successfully.",
                data=data,
                extra={"count": total, "page": page, "page_size": limit}
            )
        except Exception as e:
            logger.exception(f"Error fetching viewers for story {story_id} by user {request.user.user_id}")
            return ResponseHandler.generic_error(exception=e)


# ------------------ GLOBAL RANDOM STORIES ------------------
class GlobalStoriesAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            stories = Story.objects.filter(
                expires_at__gt=timezone.now(),
                is_deleted=False
            ).select_related('user').only(
                'id', 'text', 'media', 'view_count', 'created_at', 'expires_at', 'user__username', 'user__full_name',
            )

            # Exclude current user's stories if authenticated
            if request.user.is_authenticated:
                stories = stories.exclude(user=request.user)

            stories = list(stories)
            random.shuffle(stories)
            paginated = stories[:20]  # limit to 20 random stories

            return ResponseHandler.success(
                message="Fetched global stories successfully.",
                data=StorySerializer(paginated, many=True).data,
                extra={"count": len(paginated)}
            )
        except Exception as e:
            logger.exception("Error fetching global stories")
            return ResponseHandler.generic_error(exception=e)



# share profile views
from django.core.exceptions import ObjectDoesNotExist

class ShareProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ShareRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return ResponseHandler.bad_request(
                message="Invalid request data.",
                errors=serializer.errors
            )

        target = serializer.validated_data.get("target")

        try:
            share_obj, created = create_share(request.user, target)
            response_data = ProfileShareSerializer(share_obj).data
            response_data["created"] = created
            return ResponseHandler.success(
                message="Profile shared successfully.",
                data=response_data,
                status_code=201 if created else 200
            )

        except ValueError as e:
            logger.warning(f"ShareProfileAPIView validation error: {str(e)}")
            return ResponseHandler.bad_request(
                message=str(e)
            )
        except ObjectDoesNotExist as e:
            logger.warning(f"ShareProfileAPIView target not found: {str(e)}")
            return ResponseHandler.not_found(
                message=str(e)
            )
        except Exception as e:
            logger.exception(f"Unhandled error in ShareProfileAPIView for user_id={request.user.user_id}")
            return ResponseHandler.server_error(
                message="Internal Server Error. Check logs for details.",
                errors=str(e)
            )


class PublicProfileLinkAPIView(APIView):

    permission_classes = []

    def get(self, request, username: str):
        try:
            user = User.objects.only("username").get(username=username)
            return ResponseHandler.success(
                message="User found.",
                data={"username": user.username, "profile_link": user.profile_link}
            )
        except ObjectDoesNotExist:
            logger.warning(f"PublicProfileLinkAPIView: User '{username}' not found")
            return ResponseHandler.not_found(message=f"User '{username}' not found.")
        except Exception as e:
            logger.exception(f"Unhandled error in PublicProfileLinkAPIView for username='{username}'")
            return ResponseHandler.server_error(
                message="Internal Server Error. Check logs for details.",
                errors=str(e)
            )
            
            
            
# Block views
class BlockUserView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UserBlockSerializer(
            data=request.data,
            context={'request': request}
        )

        if not serializer.is_valid():
            return ResponseHandler.bad_request(
                message="Validation failed.",
                errors=serializer.errors
            )

        try:
            blocked_user_id = serializer.validated_data["blocked_user_id"]

            obj, created = UserBlockService.block_user(
                blocker=request.user,
                blocked_user_id=blocked_user_id
            )

            return ResponseHandler.success(
                message="User blocked successfully.",
                data={"created": created}
            )

        except Exception as e:
            logger.exception("Error blocking user")
            return ResponseHandler.generic_error(
                message="Failed to block user.",
                exception=e
            )


class UnblockUserView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UserBlockSerializer(
            data=request.data,
            context={'request': request}
        )

        if not serializer.is_valid():
            return ResponseHandler.bad_request(
                message="Validation failed.",
                errors=serializer.errors
            )

        try:
            blocked_user_id = serializer.validated_data["blocked_user_id"]

            deleted = UserBlockService.unblock_user(
                blocker=request.user,
                blocked_user_id=blocked_user_id
            )

            if deleted == 0:
                return ResponseHandler.not_found(
                    message="User was not blocked."
                )

            return ResponseHandler.success(
                message="User unblocked successfully."
            )

        except Exception as e:
            logger.exception("Error unblocking user")
            return ResponseHandler.generic_error(
                message="Failed to unblock user.",
                exception=e
            )


class BlockedUserListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            blocked_users = UserBlockService.get_blocked_users(request.user)

            return ResponseHandler.success(
                message="Blocked users fetched successfully.",
                data={"blocked_users": blocked_users}
            )

        except Exception as e:
            logger.exception("Error fetching blocked users")
            return ResponseHandler.generic_error(
                message="Could not fetch blocked users.",
                exception=e
            )
            
# report profile views

class CreateReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateReportSerializer(
            data=request.data,
            context={"request": request}
        )

        if not serializer.is_valid():
            logger.debug("Invalid report data: %s", serializer.errors)
            return ResponseHandler.error(
                message="Invalid data provided.",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data

        try:
            report = ReportService.create_report(
                reporter=request.user,
                reported_user=data["reported_user"],
                reason=data["reason"],
                comment=data.get("comment"),
                metadata={"ip": request.META.get("REMOTE_ADDR")},
            )

        except ReportServiceError as e:
            return ResponseHandler.error(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )

        except Exception:
            logger.exception("Unexpected error when creating report")
            return ResponseHandler.error(
                message="Failed to create report.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return ResponseHandler.success(
            message="Report submitted successfully.",
            data={"id": report.id},
            status_code=status.HTTP_201_CREATED
        )


class AdminAggregatedReportsPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200


class AdminAggregatedReportsAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            raw = ReportService.get_aggregated_reports()
        except Exception:
            logger.exception("Failed to fetch aggregated reports")
            return ResponseHandler.error(
                message="Failed to fetch aggregated reports.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        paginator = AdminAggregatedReportsPagination()
        page = paginator.paginate_queryset(raw, request)

        # Extract PKs of users
        user_ids = [item["reported_user"] for item in page]

        # FIX: use pk__in instead of id__in
        users = User.objects.filter(pk__in=user_ids).in_bulk()

        payload = [
            {
                "reported_user_id": item["reported_user"],
                "report_count": item["report_count"],
                "username": getattr(users.get(item["reported_user"]), "username", None),
                "email": getattr(users.get(item["reported_user"]), "email", None),
            }
            for item in page
        ]

        return ResponseHandler.paginated(
            paginator=paginator,
            data=payload
        )





# story like and unlike
from .services import StoryLikeService

class StoryLikeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, story_id):
        """
        Like a story. Returns liked=True if successful.
        """
        try:
            StoryLikeService.like_story(story_id, request.user)
            return ResponseHandler.success(
                message="Story liked.",
                data={"liked": True}
            )
        except ValueError as e:
            return ResponseHandler.bad_request(message=str(e))
        except Exception as e:
            logger.exception("Error liking story")
            return ResponseHandler.generic_error(exception=e)


class StoryUnlikeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, story_id):
        """
        Unlike a story. Returns liked=False if successful.
        """
        try:
            StoryLikeService.unlike_story(story_id, request.user)
            return ResponseHandler.success(
                message="Story unliked.",
                data={"liked": False}
            )
        except ValueError as e:
            return ResponseHandler.bad_request(message=str(e))
        except Exception as e:
            logger.exception("Error unliking story")
            return ResponseHandler.generic_error(exception=e)
        
# single user stories fetch       
class UserStoriesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, story_id):
        try:
            # Fetch the story
            story = get_object_or_404(
                Story,
                id=story_id,
                expires_at__gt=timezone.now(),
                is_deleted=False
            )

            user = story.user

            # Fetch all active stories of this user
            user_stories = Story.objects.filter(
                user__user_id=user.user_id,
                expires_at__gt=timezone.now(),
                is_deleted=False
            ).order_by('created_at')

            # Serialize stories
            serialized_stories = StorySerializer(
                user_stories,
                many=True,
                context={'request': request}
            ).data

            # Return user info + stories
            return ResponseHandler.success(
                message="User stories fetched successfully.",
                data={
                    "user_id": user.user_id,
                    "username": user.username,
                    "stories": serialized_stories
                }
            )

        except Exception as e:
            logger.exception(f"Error fetching stories for story_id {story_id}")
            return ResponseHandler.generic_error(exception=e)
        
        

# # faceapi/views.py
# class FaceScanView(APIView):
#     def post(self, request, format=None):
#         try:
#             file = None

#             if request.FILES.get("face_image"):
#                 file = request.FILES.get("face_image")


#             elif request.data.get("face_image"):
#                 base64_image = request.data.get("face_image")

#                 if "base64," in base64_image:
#                     format, imgstr = base64_image.split(";base64,")
#                     ext = format.split("/")[-1]
#                 else:
#                     imgstr = base64_image
#                     ext = "jpg"

#                 file = ContentFile(
#                     base64.b64decode(imgstr),
#                     name=f"{uuid.uuid4()}.{ext}",
#                 )

#             if not file:
#                 return Response(
#                     {"error": "No image provided"},
#                     status=status.HTTP_400_BAD_REQUEST,
#                 )


#             image = face_recognition.load_image_file(file)
#             face_locations = face_recognition.face_locations(image)

#             if not face_locations:
#                 return Response(
#                     {"error": "No face detected"},
#                     status=status.HTTP_400_BAD_REQUEST,
#                 )
#             file.seek(0)
#             if UserFace.objects.filter(user=request.user).exists():
#                 return Response(
#                     {"error": "Face already registered"},
#                     status=status.HTTP_409_CONFLICT,
#                 )
#             with transaction.atomic():
#                 serializer = UserFaceSerializer(
#                     data={
#                         "user": request.user.id,
#                         "face_image": file,
#                     }
#                 )
#                 serializer.is_valid(raise_exception=True)
#                 serializer.save()

#             return Response(
#                 {   
#                     "success": True,
#                     "message": "Face registered successfully",
#                     "faces_detected": len(face_locations),
#                 },
#                 status=status.HTTP_201_CREATED,
#             )

#         except Exception as e:
#             return Response(
#                 {
#                     "success": False,
#                     "error": "Face registration failed",
#                     "details": str(e),
#                 },
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             )



# notifications/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404
from .models import Notification
from .serializers import NotificationSerializer

class NotificationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')[:50]
        serializer = NotificationSerializer(notifications, many=True)
        return Response({
            "success": True,
            "message": "Notifications fetched successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)


class NotificationMarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk)
        if notification.recipient != request.user:
            return Response({
                "success": False,
                "message": "You do not have permission to modify this notification",
                "data": None
            }, status=status.HTTP_403_FORBIDDEN)

        notification.is_read = True
        notification.save(update_fields=['is_read'])
        serializer = NotificationSerializer(notification)
        return Response({
            "success": True,
            "message": "Notification marked as read",
            "data": serializer.data
        }, status=status.HTTP_200_OK)


class NotificationUnreadCountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return Response({
            "success": True,
            "message": "Unread notifications count fetched successfully",
            "data": {"unread_count": count}
        }, status=status.HTTP_200_OK)
