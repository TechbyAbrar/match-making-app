# chat/middleware.py
from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.authentication import JWTAuthentication
from asgiref.sync import sync_to_async

User = get_user_model()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        scope["user"] = AnonymousUser()

        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token_list = params.get("token")

        if token_list:
            token = token_list[0]
            try:
                jwt_auth = JWTAuthentication()
                validated_token = await sync_to_async(jwt_auth.get_validated_token)(token)
                user = await sync_to_async(jwt_auth.get_user)(validated_token)
                scope["user"] = user
            except Exception:
                scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
