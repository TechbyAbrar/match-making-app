import time
from django.conf import settings
from agora_token_builder import RtcTokenBuilder

ROLE_PUBLISHER = 1

def generate_rtc_token(channel: str, uid: int, expire_seconds: int = 3600) -> str:
    now = int(time.time())
    expiry = now + expire_seconds

    return RtcTokenBuilder.buildTokenWithUid(
        settings.AGORA_APP_ID,
        settings.AGORA_APP_CERTIFICATE,
        channel,
        uid,
        ROLE_PUBLISHER,
        expiry,
    )
    
    
