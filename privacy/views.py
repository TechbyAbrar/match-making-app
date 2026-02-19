from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction

from .models import PrivacyPolicy, AboutUs, TermsConditions, SubmitQuerry, ShareThoughts
from .serializers import (
    PrivacyPolicySerializer,
    AboutUsSerializer,
    TermsConditionsSerializer,
    SubmitQuerrySerializer,
    ShareThoughtsSerializer
)
from account.permissions import IsSuperUserOrReadOnly


class SingleObjectViewMixin:
    def get_object(self):
        return self.queryset.first()


class BaseSingleObjectView(SingleObjectViewMixin, generics.RetrieveUpdateAPIView):
    permission_classes = [IsSuperUserOrReadOnly]

    def get(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance:
            return Response(
                {"success": False, "message": "No content found.", "data": None},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(instance)
        return Response(
            {"success": True, "message": "Content retrieved successfully.", "data": serializer.data},
            status=status.HTTP_200_OK
        )

    @transaction.atomic
    def put(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance:
            serializer = self.get_serializer(instance, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(
                    {"success": True, "message": "Content updated successfully.", "data": serializer.data},
                    status=status.HTTP_200_OK
                )
            return Response(
                {"success": False, "message": "Validation failed.", "data": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        else:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(
                    {"success": True, "message": "Content created successfully.", "data": serializer.data},
                    status=status.HTTP_201_CREATED
                )
            return Response(
                {"success": False, "message": "Validation failed.", "data": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance:
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(
                    {"success": True, "message": "Content partially updated successfully.", "data": serializer.data},
                    status=status.HTTP_200_OK
                )
            return Response(
                {"success": False, "message": "Validation failed.", "data": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        else:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(
                    {"success": True, "message": "Content created successfully.", "data": serializer.data},
                    status=status.HTTP_201_CREATED
                )
            return Response(
                {"success": False, "message": "Validation failed.", "data": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

# privacy

class PrivacyPolicyView(BaseSingleObjectView):
    queryset = PrivacyPolicy.objects.all()
    serializer_class = PrivacyPolicySerializer


class AboutUsView(BaseSingleObjectView):
    queryset = AboutUs.objects.all()
    serializer_class = AboutUsSerializer


class TermsConditionsView(BaseSingleObjectView):
    queryset = TermsConditions.objects.all()
    serializer_class = TermsConditionsSerializer


class SubmitQuerryView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SubmitQuerrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"success": True, "message": "User query submitted successfully!", "data": serializer.data},
            status=status.HTTP_201_CREATED
        )

    def get(self, request):
        queries = SubmitQuerry.objects.all().only('id', 'name', 'email', 'message', 'created_at')
        serializer = SubmitQuerrySerializer(queries, many=True)

        return Response(
            {"success": True, "message": "All queries retrieved successfully.", "data": serializer.data},
            status=status.HTTP_200_OK
        )


class SubmitQuerryDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            query = SubmitQuerry.objects.only('id', 'name', 'email', 'message', 'created_at').get(pk=pk)
        except SubmitQuerry.DoesNotExist:
            return Response(
                {"success": False, "message": "Query not found.", "data": None},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = SubmitQuerrySerializer(query)
        return Response(
            {"success": True, "message": "Query retrieved successfully.", "data": serializer.data},
            status=status.HTTP_200_OK
        )


class ShareThoughtsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        thoughts = ShareThoughts.objects.select_related('user') \
            .only('id', 'thoughts', 'created_at', 'user__username') \
            .order_by('-created_at')

        serializer = ShareThoughtsSerializer(thoughts, many=True)
        return Response(
            {"success": True, "message": "Retrieved successfully!", "data": serializer.data},
            status=status.HTTP_200_OK
        )

    def post(self, request):
        serializer = ShareThoughtsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)

        return Response(
            {"success": True, "message": "Created successfully!", "data": serializer.data},
            status=status.HTTP_201_CREATED
        )
