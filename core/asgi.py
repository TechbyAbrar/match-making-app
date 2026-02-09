# core/asgi.py
import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

import chat.routing
from chat.middleware import JWTAuthMiddleware

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddleware(      # ✅ JWT first
        AuthMiddlewareStack(             # ✅ then session auth (optional)
            URLRouter(chat.routing.websocket_urlpatterns)
        )
    ),
})
