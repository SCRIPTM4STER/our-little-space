import os
import uuid
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User

from config.asgi import application
from api.models import Friendship, Conversation

suffix = uuid.uuid4().hex[:8]
user_a = User.objects.create_user(username=f'ws-check-a-{suffix}', password='strong-password-123')
user_b = User.objects.create_user(username=f'ws-check-b-{suffix}', password='strong-password-123')
Friendship.create_for_users(user_a, user_b)
conversation = Conversation.objects.create_for_participants(user_a, user_b)

token, _ = Token.objects.get_or_create(user=user_a)
for path in [
    f'/ws/chat/direct/{conversation.pk}/?token={token.key}',
    f'ws/chat/direct/{conversation.pk}/?token={token.key}',
    f'/ws/chat/direct/{conversation.pk}/',
    f'ws/chat/direct/{conversation.pk}/',
]:
    communicator = WebsocketCommunicator(application, path)
    try:
        connected, subprotocol = async_to_sync(communicator.connect)()
        print(path, '=>', connected, subprotocol)
    except Exception as exc:
        import traceback
        print(path, 'EXC')
        traceback.print_exc()
