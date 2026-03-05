from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import redis
from django.conf import settings

# If you already have a Redis client in chat, reuse it.
# Minimal standalone approach:
_redis = redis.Redis(host="127.0.0.1", port=6379, db=0, decode_responses=True)

def set_online(user_id: int, ttl_seconds: int = 60):
    _redis.setex(f"online:{user_id}", ttl_seconds, "1")

def is_online(user_id: int) -> bool:
    return _redis.exists(f"online:{user_id}") == 1

def set_in_call(user_id: int, call_id: str, ttl_seconds: int = 3600):
    _redis.setex(f"incall:{user_id}", ttl_seconds, call_id)

def clear_in_call(user_id: int):
    _redis.delete(f"incall:{user_id}")

def is_in_call(user_id: int) -> bool:
    return _redis.exists(f"incall:{user_id}") == 1