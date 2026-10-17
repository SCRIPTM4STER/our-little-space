from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.routing import ProtocolTypeRouter, URLRouter
from django.contrib.auth.models import AnonymousUser
from django.urls import re_path
from rest_framework.authtoken.models import Token

from api.consumers import DirectMessageConsumer, RoomChatConsumer, RoomWatchConsumer


class TokenAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'')
        params = parse_qs(query_string.decode())
        token_key = (params.get('token') or [None])[0]
        if token_key:
            try:
                token = await database_sync_to_async(
                    Token.objects.select_related('user').get
                )(key=token_key)
            except Token.DoesNotExist:
                scope['user'] = AnonymousUser()
            else:
                scope['user'] = token.user
        else:
            scope['user'] = AnonymousUser()
        return await self.app(scope, receive, send)


websocket_application = TokenAuthMiddleware(
    URLRouter([
        re_path(r'^ws/chat/direct/(?P<conversation_id>\d+)/$', DirectMessageConsumer.as_asgi()),
        re_path(r'^ws/chat/room/(?P<room_id>\d+)/$', RoomChatConsumer.as_asgi()),
        re_path(r'^ws/watch/(?P<room_id>\d+)/$', RoomWatchConsumer.as_asgi()),
    ])
)

application = ProtocolTypeRouter({
    'websocket': websocket_application,
})
