from urllib.parse import urlparse

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from .models import Conversation, DirectMessage, Notification, Room, RoomMessage, RoomWatchSession
from .serializers import DirectMessageSerializer, PublicProfileSerializer, RoomMessageSerializer


def _session_state(session):
    controller = None if not session.controller else PublicProfileSerializer(session.controller.profile).data
    return {
        'room_id': session.room_id,
        'video_url': session.video_url,
        'is_playing': session.is_playing,
        'position': float(session.position or 0),
        'playback_rate': float(session.playback_rate or 1),
        'controller': controller,
        'updated_at': session.updated_at.isoformat() if session.updated_at else None,
    }


class DirectMessageConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return
        conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        conversation = await database_sync_to_async(self._get_conversation)(conversation_id)
        if not conversation or not conversation.is_participant(user):
            await self.close(code=4002)
            return
        self.conversation = conversation
        self.group_name = f'conversation_{conversation_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    @staticmethod
    def _get_conversation(conversation_id):
        try:
            return Conversation.objects.select_related('user_a__profile', 'user_b__profile').get(pk=conversation_id)
        except Conversation.DoesNotExist:
            return None

    @staticmethod
    def _serialize_direct_message(message):
        payload = DirectMessageSerializer(message).data
        payload['type'] = 'message'
        return payload

    async def receive_json(self, payload, **kwargs):
        if payload.get('type') != 'message':
            return
        content = (payload.get('content') or '').strip()
        if not content:
            await self.send_json({'type': 'error', 'message': 'Message content cannot be empty.'})
            return

        user = self.scope['user']
        message = await database_sync_to_async(self._create_direct_message)(user, self.conversation.pk, content)
        event_payload = await database_sync_to_async(self._serialize_direct_message)(message)
        await self.channel_layer.group_send(
            self.group_name,
            {'type': 'chat_message', 'message': event_payload},
        )

    @staticmethod
    def _create_direct_message(user, conversation_id, content):
        conversation = Conversation.objects.get(pk=conversation_id)
        if not conversation.is_participant(user):
            raise PermissionError('Not allowed')
        message = DirectMessage.objects.create(conversation=conversation, sender=user, content=content)
        recipient = conversation.other_participant(user)
        Notification.objects.create(
            recipient=recipient,
            notification_type='direct_message',
            content_type=ContentType.objects.get_for_model(DirectMessage),
            object_id=str(message.pk),
        )
        conversation.updated_at = message.created_at
        conversation.save(update_fields=['updated_at'])
        return message

    async def chat_message(self, event):
        payload = dict(event['message'])
        payload['type'] = 'message'
        await self.send_json(payload)


class RoomChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return
        room_id = self.scope['url_route']['kwargs']['room_id']
        room = await database_sync_to_async(self._get_room)(room_id)
        if not room or not await database_sync_to_async(room.memberships.filter(user=user).exists)():
            await self.close(code=4002)
            return
        self.room = room
        self.group_name = f'room_{room_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    @staticmethod
    def _get_room(room_id):
        try:
            return Room.objects.select_related('owner__profile').get(pk=room_id)
        except Room.DoesNotExist:
            return None

    @staticmethod
    def _serialize_room_message(message):
        payload = RoomMessageSerializer(message).data
        payload['type'] = 'message'
        return payload

    async def receive_json(self, payload, **kwargs):
        if payload.get('type') != 'message':
            return
        content = (payload.get('content') or '').strip()
        if not content:
            await self.send_json({'type': 'error', 'message': 'Message content cannot be empty.'})
            return

        user = self.scope['user']
        if not await database_sync_to_async(self.room.memberships.filter(user=user).exists)():
            await self.close(code=4003)
            return
        message = await database_sync_to_async(self._create_room_message)(self.room.pk, user, content)
        event_payload = await database_sync_to_async(self._serialize_room_message)(message)
        await self.channel_layer.group_send(
            self.group_name,
            {'type': 'chat_message', 'message': event_payload},
        )

    @staticmethod
    def _create_room_message(room_id, user, content):
        room = Room.objects.select_related('owner').get(pk=room_id)
        if not room.memberships.filter(user=user).exists():
            raise PermissionError('Not allowed')
        message = RoomMessage.objects.create(room=room, sender=user, content=content)
        room.updated_at = message.created_at
        room.save(update_fields=['updated_at'])
        return message

    async def chat_message(self, event):
        payload = dict(event['message'])
        payload['type'] = 'message'
        await self.send_json(payload)


class RoomWatchConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return
        room_id = self.scope['url_route']['kwargs']['room_id']
        room = await database_sync_to_async(self._get_room)(room_id)
        if not room or not await database_sync_to_async(room.memberships.filter(user=user).exists)():
            await self.close(code=4002)
            return
        self.room = room
        self.group_name = f'room_watch_{room_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        session = await database_sync_to_async(self._get_or_create_session)(room)
        await self.send_json({'type': 'state', 'state': await database_sync_to_async(_session_state)(session)})

    @staticmethod
    def _get_room(room_id):
        try:
            return Room.objects.select_related('owner__profile').get(pk=room_id)
        except Room.DoesNotExist:
            return None

    @staticmethod
    def _get_or_create_session(room):
        session, _ = RoomWatchSession.objects.get_or_create(
            room=room,
            defaults={'owner': room.owner, 'controller': room.owner},
        )
        return session

    @staticmethod
    def _save_session(session):
        session.save(update_fields=['video_url', 'is_playing', 'position', 'playback_rate', 'controller', 'updated_at'])

    @staticmethod
    def _normalize_video_url(value):
        if not isinstance(value, str):
            raise ValidationError('A supported video URL is required.')
        url = value.strip()
        if not url:
            raise ValidationError('A supported video URL is required.')
        parsed = urlparse(url)
        if parsed.scheme not in {'http', 'https'}:
            raise ValidationError('Only HTTP/HTTPS video URLs are allowed.')
        host = parsed.netloc.lower().replace('www.', '')
        allowed_hosts = {'youtube.com', 'youtu.be', 'youtube-nocookie.com', 'm.youtube.com'}
        if host not in allowed_hosts and not any(host.endswith(f'.{allowed}') for allowed in allowed_hosts):
            raise ValidationError('Only YouTube video URLs are currently supported.')
        return url

    async def receive_json(self, payload, **kwargs):
        action = payload.get('action')
        if action not in {'set_video', 'play', 'pause', 'seek', 'sync'}:
            await self.send_json({'type': 'error', 'message': 'Unsupported watch action.'})
            return

        session = await database_sync_to_async(self._get_or_create_session)(self.room)
        if self.scope['user'].pk not in {session.owner_id, session.controller_id}:
            await self.send_json({'type': 'error', 'message': 'Only the owner or active controller can update the watch session.'})
            return

        if action == 'set_video':
            try:
                session.video_url = self._normalize_video_url(payload.get('video_url'))
            except ValidationError as exc:
                await self.send_json({'type': 'error', 'message': str(exc)})
                return
            session.is_playing = False
            session.position = 0
            session.controller = self.scope['user']
        elif action == 'play':
            session.is_playing = True
            session.controller = self.scope['user']
        elif action == 'pause':
            session.is_playing = False
            session.controller = self.scope['user']
        elif action == 'seek':
            try:
                session.position = float(payload.get('position', 0) or 0)
            except (TypeError, ValueError):
                await self.send_json({'type': 'error', 'message': 'Playback position must be a number.'})
                return
            session.controller = self.scope['user']
        elif action == 'sync':
            if 'video_url' in payload:
                try:
                    session.video_url = self._normalize_video_url(payload.get('video_url'))
                except ValidationError as exc:
                    await self.send_json({'type': 'error', 'message': str(exc)})
                    return
            if 'is_playing' in payload:
                session.is_playing = bool(payload.get('is_playing'))
            if 'position' in payload:
                try:
                    session.position = float(payload.get('position', 0) or 0)
                except (TypeError, ValueError):
                    await self.send_json({'type': 'error', 'message': 'Playback position must be a number.'})
                    return
            if 'playback_rate' in payload:
                try:
                    session.playback_rate = float(payload.get('playback_rate', 1) or 1)
                except (TypeError, ValueError):
                    await self.send_json({'type': 'error', 'message': 'Playback rate must be a number.'})
                    return
            session.controller = self.scope['user']

        await database_sync_to_async(self._save_session)(session)
        await self.channel_layer.group_send(
            self.group_name,
            {'type': 'watch_state', 'state': await database_sync_to_async(_session_state)(session)},
        )

    async def watch_state(self, event):
        await self.send_json({'type': 'watch_state', 'state': event['state']})
