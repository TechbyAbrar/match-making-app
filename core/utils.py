from typing import Any, Optional, Union
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
import traceback


class ResponseHandler:
    @staticmethod
    def _build_response(
        success: bool,
        message: str,
        data: Optional[Union[dict, list]] = None,
        errors: Optional[Union[dict, list, str]] = None,
        status_code: int = status.HTTP_200_OK,
        extra: Optional[dict] = None,
    ) -> Response:
        """Unified API response builder with environment-aware debug handling."""
        normalized_data = data if isinstance(data, (dict, list)) else {}
        normalized_errors = (
            errors if isinstance(errors, (dict, list)) else {"detail": str(errors)}
            if errors else None
        )

        payload: dict[str, Any] = {
            "success": success,
            "message": message,
            "status_code": status_code,
            "data": normalized_data,
            "errors": normalized_errors,
        }

        # Optional metadata like pagination or trace_id
        if extra and isinstance(extra, dict):
            payload["extra"] = extra

        # Include debug info only in development mode for failed responses
        if getattr(settings, "DEBUG", False) and not success:
            payload["debug"] = traceback.format_stack()

        response = Response(payload, status=status_code)
        response.data["status_code"] = response.status_code
        return response
    
    @staticmethod
    def paginated(paginator, data):
        return paginator.get_paginated_response(data)

    # ------------------ ✅ Success Responses ------------------ #

    @classmethod
    def success(
        cls,
        message: str = "Request successful.",
        data: Optional[Union[dict, list]] = None,
        status_code: int = status.HTTP_200_OK,
        extra: Optional[dict] = None,
    ) -> Response:
        return cls._build_response(True, message, data, None, status_code, extra)

    @classmethod
    def created(
        cls,
        message: str = "Resource created successfully.",
        data: Optional[dict] = None,
        extra: Optional[dict] = None,
    ) -> Response:
        return cls._build_response(True, message, data, None, status.HTTP_201_CREATED, extra)

    @classmethod
    def updated(
        cls,
        message: str = "Resource updated successfully.",
        data: Optional[dict] = None,
        extra: Optional[dict] = None,
    ) -> Response:
        return cls._build_response(True, message, data, None, status.HTTP_200_OK, extra)

    @classmethod
    def deleted(
        cls,
        message: str = "Resource deleted successfully.",
        extra: Optional[dict] = None,
    ) -> Response:
        return cls._build_response(True, message, {}, None, status.HTTP_204_NO_CONTENT, extra)

    # ------------------ ❌ Error Responses ------------------ #

    @classmethod
    def error(
        cls,
        message: str = "An error occurred.",
        errors: Optional[Union[dict, list, str]] = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        extra: Optional[dict] = None,
    ) -> Response:
        return cls._build_response(False, message, None, errors, status_code, extra)

    @classmethod
    def bad_request(
        cls,
        message: str = "Invalid request.",
        errors: Optional[Union[dict, list, str]] = None,
        extra: Optional[dict] = None,
    ) -> Response:
        return cls._build_response(False, message, None, errors, status.HTTP_400_BAD_REQUEST, extra)

    @classmethod
    def unauthorized(
        cls,
        message: str = "Authentication required.",
        errors: Optional[Union[dict, list, str]] = None,
        extra: Optional[dict] = None,
    ) -> Response:
        return cls._build_response(False, message, None, errors, status.HTTP_401_UNAUTHORIZED, extra)

    @classmethod
    def forbidden(
        cls,
        message: str = "Access forbidden.",
        errors: Optional[Union[dict, list, str]] = None,
        extra: Optional[dict] = None,
    ) -> Response:
        return cls._build_response(False, message, None, errors, status.HTTP_403_FORBIDDEN, extra)

    @classmethod
    def not_found(
        cls,
        message: str = "Resource not found.",
        errors: Optional[Union[dict, list, str]] = None,
        extra: Optional[dict] = None,
    ) -> Response:
        return cls._build_response(False, message, None, errors, status.HTTP_404_NOT_FOUND, extra)

    @classmethod
    def conflict(
        cls,
        message: str = "Conflict detected.",
        errors: Optional[Union[dict, list, str]] = None,
        extra: Optional[dict] = None,
    ) -> Response:
        return cls._build_response(False, message, None, errors, status.HTTP_409_CONFLICT, extra)

    @classmethod
    def server_error(
        cls,
        message: str = "Internal server error.",
        errors: Optional[Union[dict, list, str]] = None,
        extra: Optional[dict] = None,
    ) -> Response:
        return cls._build_response(False, message, None, errors, status.HTTP_500_INTERNAL_SERVER_ERROR, extra)

    @classmethod
    def generic_error(
        cls,
        message: str = "Something went wrong.",
        exception: Optional[Exception] = None,
        extra: Optional[dict] = None,
    ) -> Response:
        """Generic fallback for unexpected exceptions."""
        error_detail = str(exception) if exception else message
        return cls.server_error(message, errors=error_detail, extra=extra)
    
    


# ------------------ Custom Exception Handler ------------------ #

from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.exceptions import APIException, ValidationError, PermissionDenied, NotAuthenticated


def custom_exception_handler(exc, context):
    """Enhanced DRF exception handler integrated with ResponseHandler."""
    response = drf_exception_handler(exc, context)

    if response is not None:
        detail = response.data
        status_code = response.status_code

        if isinstance(exc, ValidationError):
            return ResponseHandler.bad_request(message="Validation failed.", errors=detail)
        elif isinstance(exc, NotAuthenticated):
            return ResponseHandler.unauthorized(message="Authentication required.", errors=detail)
        elif isinstance(exc, PermissionDenied):
            return ResponseHandler.forbidden(message="Access denied.", errors=detail)
        elif isinstance(exc, APIException):
            return ResponseHandler.error(message=str(detail), errors=detail, status_code=status_code)
        else:
            return ResponseHandler.generic_error(message="Unexpected error occurred.", exception=exc)

    # Fallback for unhandled exceptions
    return ResponseHandler.server_error(message="Internal server error.", errors=str(exc))



