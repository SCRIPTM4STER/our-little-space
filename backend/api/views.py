from collections.abc import Mapping
from uuid import UUID

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ParseError, PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Conversation, DirectMessage, FriendRequest, Friendship, Notification, Profile, Room, RoomInvitation, RoomMembership, RoomMessage, RoomWatchSession
from .realtime import broadcast_chat_message
from .serializers import (
    ConversationSerializer,
    DirectMessageSerializer,
    FriendRequestSerializer,
    LoginSerializer,
    NotificationSerializer,
    ProfileSerializer,
    PublicProfileSerializer,
    RegisterSerializer,
	RoomInvitationSerializer,
	RoomMessageSerializer,
	RoomSerializer,
    UserSerializer,
)

MESSAGE_PAGE_SIZE = 100
API_PAGE_SIZE = 100


def auth_response(user, token):
	return {
		'token': token.key,
		'user': UserSerializer(user).data,
	}


def message_cursor(request, parameter):
	value = request.query_params.get(parameter)
	if value is None:
		return None
	try:
		cursor = int(value)
	except (TypeError, ValueError):
		raise ParseError(f'{parameter} must be a non-negative message ID.')
	if cursor < 0:
		raise ParseError(f'{parameter} must be a non-negative message ID.')
	return cursor


def message_page(queryset, request):
	after = message_cursor(request, 'after')
	before = message_cursor(request, 'before')
	if after is not None and before is not None:
		raise ParseError('Use either before or after, not both.')
	if after is not None:
		return list(queryset.filter(pk__gt=after).order_by('pk')[:MESSAGE_PAGE_SIZE])
	if before is not None:
		return list(queryset.filter(pk__lt=before).order_by('-pk')[:MESSAGE_PAGE_SIZE])[::-1]
	return list(queryset.order_by('-pk')[:MESSAGE_PAGE_SIZE])[::-1]


def page_offset(request):
	value = request.query_params.get('offset', '0')
	try:
		offset = int(value)
	except (TypeError, ValueError):
		raise ParseError('offset must be a non-negative integer.')
	if offset < 0 or offset > 1_000_000:
		raise ParseError('offset must be between 0 and 1000000.')
	return offset


def paginate_queryset(queryset, request):
	offset = page_offset(request)
	items = list(queryset[offset:offset + API_PAGE_SIZE])
	has_more = queryset[offset + len(items):offset + len(items) + 1].exists()
	return items, offset + len(items), has_more


def paginate_sequence(sequence, request):
	offset = page_offset(request)
	items = sequence[offset:offset + API_PAGE_SIZE]
	return items, offset + len(items), offset + len(items) < len(sequence)


def paginated_response(data, next_offset, has_more):
	return Response(
		{'data': data},
		headers={
			'X-Next-Offset': str(next_offset),
			'X-Has-More': 'true' if has_more else 'false',
		},
	)


def request_payload(request):
	if not isinstance(request.data, Mapping):
		raise ParseError('Expected a JSON object.')
	return request.data


def profile_by_public_id(public_id):
	try:
		parsed_public_id = UUID(str(public_id))
	except (TypeError, ValueError, AttributeError):
		raise ParseError('A valid public user ID is required.')
	return get_object_or_404(Profile, public_id=parsed_public_id)


def message_content(request):
	content = request_payload(request).get('content')
	if not isinstance(content, str):
		raise ParseError('Message content must be text.')
	content = content.strip()
	if not content:
		raise ParseError('Message content cannot be empty.')
	if len(content) > 5000:
		raise ParseError('Message content must be 5000 characters or fewer.')
	return content


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
	return Response({'data': {'status': 'ok', 'service': 'backend'}})


class RegisterView(APIView):
	permission_classes = [AllowAny]
	throttle_scope = 'auth_register'

	def post(self, request):
		serializer = RegisterSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		user = serializer.save()
		token, _ = Token.objects.get_or_create(user=user)
		return Response({'data': auth_response(user, token)}, status=status.HTTP_201_CREATED)


class LoginView(ObtainAuthToken):
	permission_classes = [AllowAny]
	throttle_scope = 'auth_login'

	def post(self, request, *args, **kwargs):
		serializer = LoginSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		user = serializer.validated_data['user']
		token, _ = Token.objects.get_or_create(user=user)
		return Response({'data': auth_response(user, token)})


class CurrentUserView(APIView):
	permission_classes = [IsAuthenticated]

	def get(self, request):
		return Response({'data': UserSerializer(request.user).data})


class LogoutView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'auth_logout'

	def post(self, request):
		Token.objects.filter(user=request.user).delete()
		return Response({'data': {'logged_out': True}})


class UserLookupView(APIView):
	permission_classes = [IsAuthenticated]

	def get(self, request, public_id):
		profile = get_object_or_404(Profile, public_id=public_id)
		return Response({'data': PublicProfileSerializer(profile, context={'request': request}).data})


class UserSearchView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'username_search'

	def get(self, request):
		username = (request.query_params.get('username') or '').strip()
		if username.startswith('@'):
			username = username[1:]
		if not username:
			return Response({'detail': 'Enter a username to search.'}, status=status.HTTP_400_BAD_REQUEST)
		if len(username) > 150:
			return Response({'detail': 'Username searches must be 150 characters or fewer.'}, status=status.HTTP_400_BAD_REQUEST)
		profile = Profile.objects.select_related('user').filter(user__username__iexact=username).first()
		if profile is None:
			return Response({'detail': 'No user found with that username.'}, status=status.HTTP_404_NOT_FOUND)
		return Response({'data': PublicProfileSerializer(profile, context={'request': request}).data})


class UserRecommendationsView(APIView):
	permission_classes = [IsAuthenticated]

	def get(self, request):
		user = request.user
		friendships = Friendship.objects.filter(Q(user_a=user) | Q(user_b=user)).values_list('user_a_id', 'user_b_id')
		friend_ids = {
			user_b_id if user_a_id == user.pk else user_a_id
			for user_a_id, user_b_id in friendships
		}

		mutual_counts = {}
		if friend_ids:
			friendships_of_friends = Friendship.objects.filter(
				Q(user_a_id__in=friend_ids) | Q(user_b_id__in=friend_ids)
			).values_list('user_a_id', 'user_b_id')
			for user_a_id, user_b_id in friendships_of_friends:
				if user_a_id in friend_ids and user_b_id != user.pk:
					mutual_counts[user_b_id] = mutual_counts.get(user_b_id, 0) + 1
				if user_b_id in friend_ids and user_a_id != user.pk:
					mutual_counts[user_a_id] = mutual_counts.get(user_a_id, 0) + 1

		room_ids = RoomMembership.objects.filter(user=user).values_list('room_id', flat=True)
		shared_room_counts = dict(
			RoomMembership.objects.filter(room_id__in=room_ids)
			.exclude(user=user)
			.values('user_id')
			.annotate(count=Count('room_id', distinct=True))
			.values_list('user_id', 'count')
		)

		excluded_ids = friend_ids | {user.pk}
		friend_requests = FriendRequest.objects.filter(
			Q(sender=user) | Q(recipient=user)
		).values_list('sender_id', 'recipient_id')
		for sender_id, recipient_id in friend_requests:
			excluded_ids.add(recipient_id if sender_id == user.pk else sender_id)

		candidate_ids = (mutual_counts.keys() | shared_room_counts.keys()) - excluded_ids
		profiles = Profile.objects.select_related('user').filter(user_id__in=candidate_ids)
		profiles = sorted(
			profiles,
			key=lambda profile: (
				-(mutual_counts.get(profile.user_id, 0) * 3 + shared_room_counts.get(profile.user_id, 0) * 2),
				-mutual_counts.get(profile.user_id, 0),
				-shared_room_counts.get(profile.user_id, 0),
				profile.user.username.casefold(),
			),
		)

		recommendations = []
		for profile in profiles:
			mutual_count = mutual_counts.get(profile.user_id, 0)
			shared_room_count = shared_room_counts.get(profile.user_id, 0)
			recommendations.append({
				**PublicProfileSerializer(profile).data,
				'mutual_friends_count': mutual_count,
				'shared_rooms_count': shared_room_count,
				'recommendation_score': mutual_count * 3 + shared_room_count * 2,
			})

		page, next_offset, has_more = paginate_sequence(recommendations, request)
		return paginated_response(page, next_offset, has_more)


class FriendRequestView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'friend_requests'

	def get(self, request):
		requests = FriendRequest.objects.filter(
			Q(sender=request.user) | Q(recipient=request.user),
		).select_related('sender__profile', 'recipient__profile').order_by('-created_at', '-pk')
		page, next_offset, has_more = paginate_queryset(requests, request)
		return paginated_response(FriendRequestSerializer(page, many=True).data, next_offset, has_more)

	def post(self, request):
		payload = request_payload(request)
		recipient_public_id = payload.get('recipient_public_id')
		if not recipient_public_id:
			return Response({'detail': 'recipient_public_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
		recipient_profile = profile_by_public_id(recipient_public_id)
		recipient = recipient_profile.user
		if recipient == request.user:
			return Response({'detail': 'You cannot send a friend request to yourself.'}, status=status.HTTP_400_BAD_REQUEST)
		if Friendship.objects.are_friends(request.user, recipient):
			return Response({'detail': 'You are already friends with this user.'}, status=status.HTTP_400_BAD_REQUEST)
		existing_request = FriendRequest.objects.filter(
			Q(sender=request.user, recipient=recipient) | Q(sender=recipient, recipient=request.user)
		).first()
		if existing_request:
			return Response({'detail': 'A friend request already exists for this user pair.'}, status=status.HTTP_400_BAD_REQUEST)
		try:
			with transaction.atomic():
				friend_request = FriendRequest.objects.create(sender=request.user, recipient=recipient)
				content_type = ContentType.objects.get_for_model(FriendRequest)
				Notification.objects.create(
					recipient=recipient,
					notification_type='friend_request',
					content_type=content_type,
					object_id=str(friend_request.pk),
				)
		except ValueError as exc:
			return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
		return Response({'data': FriendRequestSerializer(friend_request).data}, status=status.HTTP_201_CREATED)


class FriendRequestReceivedView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'friend_requests'

	def get(self, request):
		requests = FriendRequest.objects.filter(
			recipient=request.user,
			status=FriendRequest.STATUS_PENDING,
		).select_related('sender__profile', 'recipient__profile').order_by('-created_at', '-pk')
		page, next_offset, has_more = paginate_queryset(requests, request)
		return paginated_response(FriendRequestSerializer(page, many=True).data, next_offset, has_more)


class FriendRequestSentView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'friend_requests'

	def get(self, request):
		requests = FriendRequest.objects.filter(
			sender=request.user,
			status=FriendRequest.STATUS_PENDING,
		).select_related('sender__profile', 'recipient__profile').order_by('-created_at', '-pk')
		page, next_offset, has_more = paginate_queryset(requests, request)
		return paginated_response(FriendRequestSerializer(page, many=True).data, next_offset, has_more)


class FriendRequestActionView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'friend_requests'

	def post(self, request, request_id, action):
		with transaction.atomic():
			friend_request = get_object_or_404(FriendRequest.objects.select_for_update(), pk=request_id)
			if friend_request.recipient != request.user:
				raise PermissionDenied('Only the recipient can act on this request.')
			if action == 'accept':
				friend_request.accept()
				response_status = status.HTTP_200_OK
			elif action == 'reject':
				friend_request.reject()
				response_status = status.HTTP_200_OK
			else:
				raise PermissionDenied('Unsupported action.')
			Notification.objects.filter(
				recipient=request.user,
				notification_type='friend_request',
				object_id=str(friend_request.pk),
				read_at__isnull=True,
			).update(read_at=timezone.now())
		return Response({'data': FriendRequestSerializer(friend_request).data}, status=response_status)


class FriendListView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'friends'

	def get(self, request):
		friendships, next_offset, has_more = paginate_queryset(Friendship.objects.for_user(request.user), request)
		friends = []
		for friendship in friendships:
			friend = friendship.other_user(request.user)
			profile = friend.profile
			friends.append({
				'id': friendship.pk,
				'public_id': str(profile.public_id),
				'username': friend.username,
				'display_name': profile.display_name,
				'bio': profile.bio,
				'avatar': profile.avatar.url if profile.avatar else None,
			})
		return paginated_response(friends, next_offset, has_more)


class RemoveFriendView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'friends'

	def delete(self, request, public_id):
		profile = get_object_or_404(Profile, public_id=public_id)
		friend = profile.user
		friendship = Friendship.objects.filter(
			Q(user_a=request.user, user_b=friend) | Q(user_a=friend, user_b=request.user)
		).first()
		if friendship is None:
			raise PermissionDenied('This user is not in your friends list.')
		friendship.delete()
		return Response({'data': {'removed': True}})


class NotificationView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'notifications'

	def get(self, request):
		notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at', '-pk')
		page, next_offset, has_more = paginate_queryset(notifications, request)
		return paginated_response({
			'notifications': NotificationSerializer(page, many=True).data,
			'unread_count': notifications.filter(read_at__isnull=True).count(),
		}, next_offset, has_more)


class ActivitySummaryView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'activity_summary'

	def get(self, request):
		user = request.user
		unread_messages = DirectMessage.objects.filter(
			Q(conversation__user_a=user) | Q(conversation__user_b=user),
			read_at__isnull=True,
		).exclude(sender=user).count()
		return Response({'data': {
			'notifications': Notification.objects.filter(
				recipient=user,
				read_at__isnull=True,
			).exclude(notification_type__in=['direct_message', 'friend_request']).count(),
			'messages': unread_messages,
			'friend_requests': FriendRequest.objects.filter(
				recipient=user,
				status=FriendRequest.STATUS_PENDING,
			).count(),
		}})


class NotificationReadView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'notifications'

	def post(self, request, notification_id):
		notification = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
		notification.mark_read()
		return Response({'data': NotificationSerializer(notification).data})


class ConversationView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'conversations'

	def get(self, request):
		conversations = Conversation.objects.for_user(request.user).order_by('-updated_at', '-pk').prefetch_related(
			Prefetch(
				'messages',
				queryset=DirectMessage.objects.select_related('sender__profile').order_by('-created_at')[:1],
				to_attr='latest_messages',
			),
		)
		page, next_offset, has_more = paginate_queryset(conversations, request)
		return paginated_response(
			ConversationSerializer(page, many=True, context={'request': request}).data,
			next_offset,
			has_more,
		)

	def post(self, request):
		participant_public_id = request_payload(request).get('participant_public_id')
		if not participant_public_id:
			return Response({'detail': 'participant_public_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
		participant_profile = profile_by_public_id(participant_public_id)
		participant = participant_profile.user
		if not Friendship.objects.are_friends(request.user, participant):
			return Response({'detail': 'Only friends can start a private conversation.'}, status=status.HTTP_400_BAD_REQUEST)
		try:
			conversation = Conversation.objects.create_for_participants(request.user, participant)
		except ValueError as exc:
			return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
		return Response({'data': ConversationSerializer(conversation, context={'request': request}).data}, status=status.HTTP_201_CREATED)


class ConversationMessageView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'messages'

	def get(self, request, conversation_id):
		conversation = get_object_or_404(Conversation, pk=conversation_id)
		if not conversation.is_participant(request.user):
			raise Http404('You do not have access to this conversation.')
		unread_ids = list(conversation.messages.filter(
			read_at__isnull=True,
		).exclude(sender=request.user).values_list('pk', flat=True))
		if unread_ids:
			read_at = timezone.now()
			DirectMessage.objects.filter(pk__in=unread_ids).update(read_at=read_at)
			Notification.objects.filter(
				recipient=request.user,
				content_type=ContentType.objects.get_for_model(DirectMessage),
				object_id__in=[str(message_id) for message_id in unread_ids],
				read_at__isnull=True,
			).update(read_at=read_at)
		messages = conversation.messages.filter(deleted_at__isnull=True).select_related('sender__profile')
		return Response({'data': DirectMessageSerializer(message_page(messages, request), many=True).data})

	def post(self, request, conversation_id):
		conversation = get_object_or_404(Conversation, pk=conversation_id)
		if not conversation.is_participant(request.user):
			raise Http404('You do not have access to this conversation.')
		content = message_content(request)
		with transaction.atomic():
			message = DirectMessage.objects.create(conversation=conversation, sender=request.user, content=content)
			recipient = conversation.other_participant(request.user)
			Notification.objects.create(
				recipient=recipient,
				notification_type='direct_message',
				content_type=ContentType.objects.get_for_model(DirectMessage),
				object_id=str(message.pk),
			)
			conversation.updated_at = timezone.now()
			conversation.save(update_fields=['updated_at'])
		payload = DirectMessageSerializer(message).data
		broadcast_chat_message(f'conversation_{conversation.pk}', payload)
		return Response({'data': payload}, status=status.HTTP_201_CREATED)

	def delete(self, request, conversation_id, message_id):
		conversation = get_object_or_404(Conversation, pk=conversation_id)
		if not conversation.is_participant(request.user):
			raise Http404('You do not have access to this conversation.')
		message = get_object_or_404(DirectMessage, pk=message_id, conversation=conversation)
		if message.sender != request.user:
			raise PermissionDenied('You can only delete your own messages.')
		message.deleted_at = timezone.now()
		message.save(update_fields=['deleted_at'])
		return Response({'data': {'deleted': True}})


class RoomView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'rooms'

	def get_throttles(self):
		self.throttle_scope = 'room_create' if self.request.method == 'POST' else 'rooms'
		return super().get_throttles()

	def get(self, request):
		rooms = Room.objects.filter(
			memberships__user=request.user,
		).distinct().order_by('-updated_at', '-pk').annotate(
			request_user_is_member=Exists(RoomMembership.objects.filter(room_id=OuterRef('pk'), user=request.user)),
		).select_related('owner__profile').prefetch_related(
			Prefetch('memberships', queryset=RoomMembership.objects.select_related('user'), to_attr='room_memberships'),
			Prefetch(
				'messages',
				queryset=RoomMessage.objects.select_related('sender__profile').order_by('-created_at')[:1],
				to_attr='latest_messages',
			),
		)
		page, next_offset, has_more = paginate_queryset(rooms, request)
		return paginated_response(
			RoomSerializer(page, many=True, context={'request': request}).data,
			next_offset,
			has_more,
		)

	def post(self, request):
		name = request_payload(request).get('name')
		if not isinstance(name, str):
			return Response({'detail': 'Room name must be text.'}, status=status.HTTP_400_BAD_REQUEST)
		name = name.strip()
		if not name:
			return Response({'detail': 'Room name cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)
		if len(name) > 80:
			return Response({'detail': 'Room name must be 80 characters or fewer.'}, status=status.HTTP_400_BAD_REQUEST)
		with transaction.atomic():
			room = Room.objects.create(name=name, owner=request.user)
			RoomMembership.objects.create(room=room, user=request.user)
		return Response({'data': RoomSerializer(room, context={'request': request}).data}, status=status.HTTP_201_CREATED)


class RoomMembershipView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'room_membership'

	def post(self, request, room_id, action):
		room = get_object_or_404(Room, pk=room_id, memberships__user=request.user)
		if action == 'join':
			return Response({'data': RoomSerializer(room, context={'request': request}).data})
		elif action == 'leave':
			if room.owner_id == request.user.pk:
				return Response({'detail': 'Room owners cannot leave. Delete the room to close it.'}, status=status.HTTP_400_BAD_REQUEST)
			RoomMembership.objects.filter(room=room, user=request.user).delete()
		else:
			raise Http404('Unsupported room action.')
		return Response({'data': RoomSerializer(room, context={'request': request}).data})


class RoomDeleteView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'room_delete'

	def delete(self, request, room_id):
		with transaction.atomic():
			room = get_object_or_404(Room, pk=room_id)
			if room.owner_id != request.user.pk:
				raise PermissionDenied('Only the room owner can delete this room.')
			invitation_ids = RoomInvitation.objects.filter(room=room).values_list('pk', flat=True)
			invitation_type = ContentType.objects.get_for_model(RoomInvitation)
			Notification.objects.filter(
				content_type=invitation_type,
				object_id__in=invitation_ids,
			).delete()
			room.delete()
		return Response({'data': {'deleted': True}})


class RoomInvitationListCreateView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'room_invitations'

	def get_room_for_member(self, room_id, user):
		return get_object_or_404(Room, pk=room_id, memberships__user=user)

	def get(self, request, room_id):
		room = self.get_room_for_member(room_id, request.user)
		invitations = RoomInvitation.objects.filter(
			room=room,
			status=RoomInvitation.STATUS_PENDING,
		).select_related('room', 'inviter__profile', 'invitee__profile').order_by('-created_at', '-pk')
		invitations, next_offset, has_more = paginate_queryset(invitations, request)
		member_public_ids = room.members.values_list('profile__public_id', flat=True)
		return paginated_response({
			'invitations': RoomInvitationSerializer(invitations, many=True).data,
			'member_public_ids': [str(public_id) for public_id in member_public_ids],
		}, next_offset, has_more)

	def post(self, request, room_id):
		room = self.get_room_for_member(room_id, request.user)
		invitee_public_id = request_payload(request).get('invitee_public_id')
		if not invitee_public_id:
			return Response({'detail': 'invitee_public_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
		invitee_profile = profile_by_public_id(invitee_public_id)
		invitee = invitee_profile.user
		if room.memberships.filter(user=invitee).exists():
			return Response({'detail': 'This user is already a room member.'}, status=status.HTTP_400_BAD_REQUEST)
		if not Friendship.objects.are_friends(request.user, invitee):
			return Response({'detail': 'You can only invite friends to a room.'}, status=status.HTTP_400_BAD_REQUEST)

		with transaction.atomic():
			invitation, created = RoomInvitation.objects.get_or_create(
				room=room,
				invitee=invitee,
				status=RoomInvitation.STATUS_PENDING,
				defaults={'inviter': request.user},
			)
			if not created:
				return Response({'detail': 'A pending invitation already exists for this user.'}, status=status.HTTP_400_BAD_REQUEST)
			Notification.objects.create(
				recipient=invitee,
				notification_type='room_invitation',
				content_type=ContentType.objects.get_for_model(RoomInvitation),
				object_id=str(invitation.pk),
			)
		return Response({'data': RoomInvitationSerializer(invitation).data}, status=status.HTTP_201_CREATED)


class PendingRoomInvitationView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'room_invitations'

	def get(self, request):
		invitations = RoomInvitation.objects.filter(
			invitee=request.user,
			status=RoomInvitation.STATUS_PENDING,
		).select_related('room', 'inviter__profile', 'invitee__profile').order_by('-created_at', '-pk')
		page, next_offset, has_more = paginate_queryset(invitations, request)
		return paginated_response(RoomInvitationSerializer(page, many=True).data, next_offset, has_more)


class RoomInvitationActionView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'room_invitation_actions'

	def post(self, request, invitation_id, action):
		if action not in ('accept', 'decline'):
			raise Http404('Unsupported invitation action.')
		with transaction.atomic():
			invitation = get_object_or_404(
				RoomInvitation.objects.select_for_update().select_related('room', 'inviter__profile', 'invitee__profile'),
				pk=invitation_id,
				invitee=request.user,
				status=RoomInvitation.STATUS_PENDING,
			)
			if action == 'accept':
				RoomMembership.objects.get_or_create(room=invitation.room, user=request.user)
				invitation.status = RoomInvitation.STATUS_ACCEPTED
			else:
				invitation.status = RoomInvitation.STATUS_DECLINED
			invitation.save(update_fields=['status', 'updated_at'])
			Notification.objects.filter(
				recipient=request.user,
				notification_type='room_invitation',
				content_type=ContentType.objects.get_for_model(RoomInvitation),
				object_id=str(invitation.pk),
				read_at__isnull=True,
			).update(read_at=timezone.now())
		return Response({'data': RoomInvitationSerializer(invitation).data})


class RoomMessageView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'messages'

	def get_room_for_member(self, room_id, user):
		return get_object_or_404(Room, pk=room_id, memberships__user=user)

	def get(self, request, room_id):
		room = self.get_room_for_member(room_id, request.user)
		messages = room.messages.select_related('sender__profile')
		return Response({'data': RoomMessageSerializer(message_page(messages, request), many=True).data})

	def post(self, request, room_id):
		room = self.get_room_for_member(room_id, request.user)
		content = message_content(request)
		with transaction.atomic():
			message = RoomMessage.objects.create(room=room, sender=request.user, content=content)
			room.updated_at = timezone.now()
			room.save(update_fields=['updated_at'])
		payload = RoomMessageSerializer(message).data
		broadcast_chat_message(f'room_{room.pk}', payload)
		return Response({'data': payload}, status=status.HTTP_201_CREATED)
	def delete(self, request, room_id, msg_id):
		room = self.get_room_for_member(room_id, request.user)
		message = get_object_or_404(RoomMessage, id=msg_id, room=room)
		if message.sender != request.user:
			raise PermissionDenied('You can only delete your own messages.')
		message.delete()
		return Response({'data': {'deleted': True}})





class RoomWatchView(APIView):
	permission_classes = [IsAuthenticated]
	throttle_scope = 'watch_session'

	def get_room_for_member(self, room_id, user):
		return get_object_or_404(Room, pk=room_id, memberships__user=user)

	@staticmethod
	def normalize_video_url(value):
		if not isinstance(value, str):
			raise ValueError('A supported video URL is required.')
		url = value.strip()
		if not url:
			raise ValueError('A supported video URL is required.')
		if not url.startswith(('http://', 'https://')):
			raise ValueError('Only HTTP/HTTPS video URLs are allowed.')
		if 'youtube.com' not in url and 'youtu.be' not in url and 'youtube-nocookie.com' not in url:
			raise ValueError('Only YouTube video URLs are currently supported.')
		return url

	def get(self, request, room_id):
		room = self.get_room_for_member(room_id, request.user)
		session, _ = RoomWatchSession.objects.get_or_create(room=room, defaults={'owner': room.owner, 'controller': room.owner})
		return Response({'data': {
			'room_id': room.id,
			'video_url': session.video_url,
			'is_playing': session.is_playing,
			'position': float(session.position or 0),
			'playback_rate': float(session.playback_rate or 1),
			'controller': PublicProfileSerializer(session.controller.profile).data if session.controller else None,
		}})

	def post(self, request, room_id):
		room = self.get_room_for_member(room_id, request.user)
		payload = request_payload(request)
		action = payload.get('action') or ('set_video' if 'video_url' in payload else None)
		session, _ = RoomWatchSession.objects.get_or_create(room=room, defaults={'owner': room.owner, 'controller': room.owner})
		if request.user.pk not in {room.owner_id, session.controller_id} and request.user.pk != room.owner_id:
			return Response({'detail': 'Only the room owner or the active controller can change the watch session.'}, status=status.HTTP_403_FORBIDDEN)
		try:
			if action == 'set_video':
				session.video_url = self.normalize_video_url(payload.get('video_url', ''))
				session.is_playing = False
				session.position = 0
				session.controller = request.user
			elif action == 'play':
				session.is_playing = True
				session.controller = request.user
			elif action == 'pause':
				session.is_playing = False
				session.controller = request.user
			elif action == 'seek':
				session.position = float(payload.get('position', 0) or 0)
				session.controller = request.user
			elif action == 'sync':
				if 'video_url' in payload:
					session.video_url = self.normalize_video_url(payload.get('video_url'))
				if 'is_playing' in payload:
					session.is_playing = bool(payload.get('is_playing'))
				if 'position' in payload:
					session.position = float(payload.get('position', 0) or 0)
				if 'playback_rate' in payload:
					session.playback_rate = float(payload.get('playback_rate', 1) or 1)
				session.controller = request.user
			else:
				raise ValueError('Unsupported watch action.')
		except (TypeError, ValueError):
			return Response({'detail': 'Invalid watch state payload.'}, status=status.HTTP_400_BAD_REQUEST)
		session.save(update_fields=['video_url', 'is_playing', 'position', 'playback_rate', 'controller', 'updated_at'])
		return Response({'data': {
			'room_id': room.id,
			'video_url': session.video_url,
			'is_playing': session.is_playing,
			'position': float(session.position or 0),
			'playback_rate': float(session.playback_rate or 1),
			'controller': PublicProfileSerializer(session.controller.profile).data if session.controller else None,
		}})


class ProfileView(APIView):
	permission_classes = [IsAuthenticated]
	parser_classes = [MultiPartParser, FormParser]
	throttle_scope = 'profile_reads'

	def get_throttles(self):
		self.throttle_scope = 'profile_updates' if self.request.method == 'PATCH' else 'profile_reads'
		return super().get_throttles()

	def get(self, request):
		profile, _ = Profile.objects.get_or_create(user=request.user)
		return Response({'data': ProfileSerializer(profile, context={'request': request}).data})

	def patch(self, request):
		profile, _ = Profile.objects.get_or_create(user=request.user)
		serializer = ProfileSerializer(
			profile,
			data=request.data,
			partial=True,
			context={'request': request},
		)
		serializer.is_valid(raise_exception=True)
		serializer.save()
		return Response({'data': serializer.data})


def frontend_index(request):
    """Serve the React SPA index.html for all non-API, non-admin routes.

    WhiteNoise handles /static/ and /media/ before this view is reached.
    This catch-all enables React Router client-side navigation on refresh.
    """
    from django.conf import settings
    from django.http import FileResponse, Http404
    import os

    index_path = os.path.join(settings.STATICFILES_DIRS[0], 'index.html')
    if os.path.exists(index_path):
        return FileResponse(open(index_path, 'rb'))
    raise Http404('Frontend not built. Run `npm run build` in the frontend directory.')
