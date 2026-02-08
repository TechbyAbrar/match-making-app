
# import os

# from django.core.asgi import get_asgi_application

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# application = get_asgi_application()


# core/asgi.py
import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# ✅ Set settings before importing anything Django-related
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

import chat.routing  # safe to import now

# ✅ Only call this once
django_asgi_app = get_asgi_application()

# application = ProtocolTypeRouter({
#     "http": django_asgi_app,
#     "websocket": AuthMiddlewareStack(
#         URLRouter(
#             chat.routing.websocket_urlpatterns
#         )
#     ),
# })


application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter(chat.routing.websocket_urlpatterns),
})