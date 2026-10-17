from io import BytesIO

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.core.cache import cache
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from config.asgi import application

from .models import Conversation, DirectMessage, FriendRequest, Friendship, Notification, Profile, Room, RoomInvitation, RoomMembership, RoomMessage, RoomWatchSession


class AuthenticationTests(APITestCase):
	def test_register_login_me_and_logout(self):
		register_response = self.client.post(
			'/api/auth/register/',
			{
				'username': 'riyad',
				'email': 'riyad@example.com',
				'password': 'strong-password-123',
				'password_confirmation': 'strong-password-123',
			},
			format='json',
		)

		self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)
		token = register_response.data['data']['token']
		self.assertEqual(register_response.data['data']['user']['username'], 'riyad')

		self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
		me_response = self.client.get('/api/auth/me/')
		self.assertEqual(me_response.status_code, status.HTTP_200_OK)
		self.assertEqual(me_response.data['data']['email'], 'riyad@example.com')

		logout_response = self.client.post('/api/auth/logout/', format='json')
		self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

		me_after_logout = self.client.get('/api/auth/me/')
		self.assertEqual(me_after_logout.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_login_rejects_invalid_credentials(self):
		User.objects.create_user(username='riyad', password='strong-password-123')

		response = self.client.post(
			'/api/auth/login/',
			{'username': 'riyad', 'password': 'wrong-password'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_public_id_is_generated_and_unique(self):
		first_user = User.objects.create_user(username='first', password='strong-password-123')
		second_user = User.objects.create_user(username='second', password='strong-password-123')

		first_profile = Profile.objects.get(user=first_user)
		second_profile = Profile.objects.get(user=second_user)

		self.assertTrue(first_profile.public_id)
		self.assertTrue(second_profile.public_id)
		self.assertNotEqual(first_profile.public_id, second_profile.public_id)
		self.assertEqual(Profile.objects.filter(public_id=first_profile.public_id).count(), 1)

	def test_public_id_is_immutable(self):
		user = User.objects.create_user(username='riyad', password='strong-password-123')
		profile = Profile.objects.get(user=user)
		original_public_id = profile.public_id

		with self.assertRaises(ValueError):
			profile.public_id = 'different-public-id'
			profile.save()

		profile.refresh_from_db()
		self.assertEqual(profile.public_id, original_public_id)

	def test_user_lookup_by_public_id_exposes_only_public_fields(self):
		requesting_user = User.objects.create_user(username='requester', password='strong-password-123')
		target_user = User.objects.create_user(username='target', password='strong-password-123')
		target_profile = Profile.objects.get(user=target_user)
		target_profile.display_name = 'Target User'
		target_profile.bio = 'Hello from the public profile.'
		target_profile.save()

		self.client.force_authenticate(user=requesting_user)
		response = self.client.get(f'/api/users/{target_profile.public_id}/')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['data']['public_id'], str(target_profile.public_id))
		self.assertEqual(response.data['data']['username'], 'target')
		self.assertEqual(response.data['data']['display_name'], 'Target User')
		self.assertNotIn('email', response.data['data'])
		self.assertNotIn('password', response.data['data'])
		self.assertNotIn('auth_token', response.data['data'])

	def test_user_search_accepts_at_username_case_insensitively_and_returns_public_fields(self):
		requester = User.objects.create_user(username='search-requester', password='strong-password-123')
		target = User.objects.create_user(username='SearchTarget', email='private@example.com', password='strong-password-123')
		self.client.force_authenticate(user=requester)

		response = self.client.get('/api/users/search/?username=%40searchTarget')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['data']['username'], 'SearchTarget')
		self.assertEqual(response.data['data']['public_id'], str(Profile.objects.get(user=target).public_id))
		self.assertNotIn('email', response.data['data'])
		self.assertEqual(self.client.get('/api/users/search/?username=missing-person').status_code, status.HTTP_404_NOT_FOUND)
		self.assertEqual(self.client.get('/api/users/search/?username=%40').status_code, status.HTTP_400_BAD_REQUEST)

		self.client.force_authenticate(user=None)
		self.assertEqual(self.client.get('/api/users/search/?username=SearchTarget').status_code, status.HTTP_401_UNAUTHORIZED)

	def test_user_recommendations_rank_social_connections_and_exclude_existing_relationships(self):
		requester = User.objects.create_user(username='recommend-requester', password='strong-password-123')
		mutual_friend = User.objects.create_user(username='recommend-mutual-friend', password='strong-password-123')
		both_signals = User.objects.create_user(username='both-signals', password='strong-password-123')
		mutual_only = User.objects.create_user(username='mutual-only', password='strong-password-123')
		room_only = User.objects.create_user(username='room-only', password='strong-password-123')
		already_friend = User.objects.create_user(username='already-friend', password='strong-password-123')
		outgoing_request = User.objects.create_user(username='outgoing-request', password='strong-password-123')
		incoming_request = User.objects.create_user(username='incoming-request', password='strong-password-123')

		Friendship.create_for_users(requester, mutual_friend)
		Friendship.create_for_users(mutual_friend, both_signals)
		Friendship.create_for_users(mutual_friend, mutual_only)
		Friendship.create_for_users(requester, already_friend)
		FriendRequest.objects.create(sender=requester, recipient=outgoing_request)
		FriendRequest.objects.create(sender=incoming_request, recipient=requester)

		room = Room.objects.create(name='Recommendation room', owner=requester)
		RoomMembership.objects.create(room=room, user=requester)
		RoomMembership.objects.create(room=room, user=both_signals)
		RoomMembership.objects.create(room=room, user=room_only)

		self.client.force_authenticate(user=requester)
		response = self.client.get('/api/users/recommendations/')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		recommendations = response.data['data']
		self.assertEqual([item['username'] for item in recommendations], ['both-signals', 'mutual-only', 'room-only'])
		self.assertEqual(recommendations[0]['mutual_friends_count'], 1)
		self.assertEqual(recommendations[0]['shared_rooms_count'], 1)
		recommended_ids = {item['public_id'] for item in recommendations}
		self.assertNotIn(str(Profile.objects.get(user=already_friend).public_id), recommended_ids)
		self.assertNotIn(str(Profile.objects.get(user=outgoing_request).public_id), recommended_ids)
		self.assertNotIn(str(Profile.objects.get(user=incoming_request).public_id), recommended_ids)

	def test_friend_request_cannot_be_sent_to_self(self):
		user = User.objects.create_user(username='riyad', password='strong-password-123')
		self.client.force_authenticate(user=user)

		response = self.client.post('/api/friend-requests/', {'recipient_public_id': Profile.objects.get(user=user).public_id}, format='json')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertFalse(FriendRequest.objects.exists())

	def test_duplicate_and_reverse_pending_requests_are_blocked(self):
		first_user = User.objects.create_user(username='first', password='strong-password-123')
		second_user = User.objects.create_user(username='second', password='strong-password-123')

		FriendRequest.objects.create(sender=first_user, recipient=second_user, status='pending')

		self.client.force_authenticate(user=first_user)
		response = self.client.post('/api/friend-requests/', {'recipient_public_id': Profile.objects.get(user=second_user).public_id}, format='json')
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

		self.client.force_authenticate(user=second_user)
		reverse_response = self.client.post('/api/friend-requests/', {'recipient_public_id': Profile.objects.get(user=first_user).public_id}, format='json')
		self.assertEqual(reverse_response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(FriendRequest.objects.filter(status='pending').count(), 1)

	def test_accepting_request_creates_friendship_and_notification(self):
		sender = User.objects.create_user(username='sender', password='strong-password-123')
		recipient = User.objects.create_user(username='recipient', password='strong-password-123')
		request = FriendRequest.objects.create(sender=sender, recipient=recipient, status='pending')
		self.client.force_authenticate(user=recipient)

		response = self.client.post(f'/api/friend-requests/{request.pk}/accept/', format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertTrue(Friendship.objects.are_friends(sender, recipient))
		self.assertTrue(Notification.objects.filter(recipient=sender, notification_type='friend_request_accepted').exists())
		self.assertFalse(Notification.objects.filter(recipient=recipient, notification_type='friend_request_accepted').exists())

	def test_only_recipient_can_accept_or_reject_request(self):
		first_user = User.objects.create_user(username='first', password='strong-password-123')
		second_user = User.objects.create_user(username='second', password='strong-password-123')
		friend_request = FriendRequest.objects.create(sender=first_user, recipient=second_user, status='pending')

		self.client.force_authenticate(user=first_user)
		accept_response = self.client.post(f'/api/friend-requests/{friend_request.pk}/accept/', format='json')
		self.assertEqual(accept_response.status_code, status.HTTP_403_FORBIDDEN)

	def test_friends_are_visible_to_both_users_and_can_be_removed(self):
		user_a = User.objects.create_user(username='a', password='strong-password-123')
		user_b = User.objects.create_user(username='b', password='strong-password-123')
		friendship = Friendship.objects.create(user_a=user_a, user_b=user_b)

		self.client.force_authenticate(user_a)
		a_friends = self.client.get('/api/friends/')
		self.assertEqual(a_friends.status_code, status.HTTP_200_OK)
		self.assertEqual(len(a_friends.data['data']), 1)

		self.client.force_authenticate(user_b)
		b_friends = self.client.get('/api/friends/')
		self.assertEqual(b_friends.status_code, status.HTTP_200_OK)
		self.assertEqual(len(b_friends.data['data']), 1)

		delete_response = self.client.delete(f'/api/friends/{Profile.objects.get(user=user_a).public_id}/')
		self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
		self.assertFalse(Friendship.objects.are_friends(user_a, user_b))

	def test_only_friends_can_create_private_conversation(self):
		user_a = User.objects.create_user(username='alpha', password='strong-password-123')
		user_b = User.objects.create_user(username='beta', password='strong-password-123')
		user_c = User.objects.create_user(username='gamma', password='strong-password-123')

		self.client.force_authenticate(user_a)
		response = self.client.post('/api/conversations/', {'participant_public_id': Profile.objects.get(user=user_b).public_id}, format='json')
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

		Friendship.objects.create(user_a=user_a, user_b=user_b)
		valid_response = self.client.post('/api/conversations/', {'participant_public_id': Profile.objects.get(user=user_b).public_id}, format='json')
		self.assertEqual(valid_response.status_code, status.HTTP_201_CREATED)

		self.client.force_authenticate(user_c)
		invalid_response = self.client.post('/api/conversations/', {'participant_public_id': Profile.objects.get(user=user_b).public_id}, format='json')
		self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_users_cannot_access_other_private_conversations(self):
		user_a = User.objects.create_user(username='alpha2', password='strong-password-123')
		user_b = User.objects.create_user(username='beta2', password='strong-password-123')
		user_c = User.objects.create_user(username='gamma2', password='strong-password-123')
		Friendship.objects.create(user_a=user_a, user_b=user_b)
		conversation = Conversation.objects.create_for_participants(user_a, user_b)

		self.client.force_authenticate(user_c)
		response = self.client.get(f'/api/conversations/{conversation.pk}/messages/')
		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

	def test_messages_are_only_sent_between_friends(self):
		user_a = User.objects.create_user(username='a2', password='strong-password-123')
		user_b = User.objects.create_user(username='b2', password='strong-password-123')
		Friendship.objects.create(user_a=user_a, user_b=user_b)
		conversation = Conversation.objects.create_for_participants(user_a, user_b)

		self.client.force_authenticate(user_a)
		response = self.client.post(f'/api/conversations/{conversation.pk}/messages/', {'content': 'hello there'}, format='json')
		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(DirectMessage.objects.filter(conversation=conversation).count(), 1)
		self.assertTrue(Notification.objects.filter(recipient=user_b, notification_type='direct_message').exists())

	def test_room_and_direct_message_history_support_incremental_cursors(self):
		user_a = User.objects.create_user(username='cursor-a', password='strong-password-123')
		user_b = User.objects.create_user(username='cursor-b', password='strong-password-123')
		Friendship.create_for_users(user_a, user_b)
		conversation = Conversation.objects.create_for_participants(user_a, user_b)
		old_direct_message = DirectMessage.objects.create(conversation=conversation, sender=user_a, content='Earlier DM')
		new_direct_message = DirectMessage.objects.create(conversation=conversation, sender=user_a, content='New DM')
		room = Room.objects.create(name='Cursor room', owner=user_a)
		RoomMembership.objects.create(room=room, user=user_a)
		RoomMembership.objects.create(room=room, user=user_b)
		old_room_message = RoomMessage.objects.create(room=room, sender=user_a, content='Earlier room message')
		new_room_message = RoomMessage.objects.create(room=room, sender=user_a, content='New room message')
		self.client.force_authenticate(user=user_b)

		direct_response = self.client.get(f'/api/conversations/{conversation.pk}/messages/?after={old_direct_message.pk}')
		self.assertEqual(direct_response.status_code, status.HTTP_200_OK)
		self.assertEqual([message['id'] for message in direct_response.data['data']], [new_direct_message.pk])
		self.assertEqual(
			self.client.get(f'/api/conversations/{conversation.pk}/messages/?after=invalid').status_code,
			status.HTTP_400_BAD_REQUEST,
		)

		room_response = self.client.get(f'/api/rooms/{room.pk}/messages/?after={old_room_message.pk}')
		self.assertEqual(room_response.status_code, status.HTTP_200_OK)
		self.assertEqual([message['id'] for message in room_response.data['data']], [new_room_message.pk])
		self.assertEqual(
			self.client.get(f'/api/rooms/{room.pk}/messages/?after=-1').status_code,
			status.HTTP_400_BAD_REQUEST,
		)

	def test_rooms_are_group_chats_with_member_only_messages(self):
		owner = User.objects.create_user(username='room-owner', password='strong-password-123')
		member = User.objects.create_user(username='room-member', password='strong-password-123')
		outsider = User.objects.create_user(username='room-outsider', password='strong-password-123')
		Friendship.create_for_users(owner, member)
		self.client.force_authenticate(user=owner)
		create_response = self.client.post('/api/rooms/', {'name': 'Movie night'}, format='json')
		self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
		room_id = create_response.data['data']['id']
		invite_response = self.client.post(
			f'/api/rooms/{room_id}/invitations/',
			{'invitee_public_id': Profile.objects.get(user=member).public_id},
			format='json',
		)
		self.assertEqual(invite_response.status_code, status.HTTP_201_CREATED)
		self.assertTrue(Notification.objects.filter(recipient=member, notification_type='room_invitation').exists())
		self.client.force_authenticate(user=member)
		pending_response = self.client.get('/api/room-invitations/')
		self.assertEqual(pending_response.status_code, status.HTTP_200_OK)
		self.assertEqual(pending_response.data['data'][0]['room']['name'], 'Movie night')
		accept_response = self.client.post(f"/api/room-invitations/{invite_response.data['data']['id']}/accept/", format='json')
		self.assertEqual(accept_response.status_code, status.HTTP_200_OK)
		self.assertTrue(RoomMembership.objects.filter(room_id=room_id, user=member).exists())
		self.assertEqual(accept_response.data['data']['status'], RoomInvitation.STATUS_ACCEPTED)
		self.assertIsNotNone(Notification.objects.get(recipient=member, notification_type='room_invitation').read_at)
		self.assertEqual(self.client.get('/api/rooms/').data['data'][0]['member_count'], 2)
		message_response = self.client.post(f'/api/rooms/{room_id}/messages/', {'content': 'Hello group'}, format='json')
		self.assertEqual(message_response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(RoomMessage.objects.filter(room_id=room_id).count(), 1)
		self.client.force_authenticate(user=outsider)
		self.assertEqual(self.client.get('/api/rooms/').data['data'], [])
		self.assertEqual(self.client.post(f'/api/rooms/{room_id}/join/', format='json').status_code, status.HTTP_404_NOT_FOUND)
		read_response = self.client.get(f'/api/rooms/{room_id}/messages/')
		self.assertEqual(read_response.status_code, status.HTTP_404_NOT_FOUND)
		self.assertFalse(RoomMembership.objects.filter(room_id=room_id, user=outsider).exists())

	def test_room_invites_require_membership_friendship_and_reject_duplicates(self):
		owner = User.objects.create_user(username='invite-owner', password='strong-password-123')
		friend = User.objects.create_user(username='invite-friend', password='strong-password-123')
		outsider = User.objects.create_user(username='invite-outsider', password='strong-password-123')
		room = Room.objects.create(name='Private room', owner=owner)
		RoomMembership.objects.create(room=room, user=owner)
		Friendship.create_for_users(owner, friend)
		self.client.force_authenticate(user=outsider)
		denied_response = self.client.post(
			f'/api/rooms/{room.pk}/invitations/',
			{'invitee_public_id': Profile.objects.get(user=friend).public_id},
			format='json',
		)
		self.assertEqual(denied_response.status_code, status.HTTP_404_NOT_FOUND)
		self.client.force_authenticate(user=owner)
		nonfriend_response = self.client.post(
			f'/api/rooms/{room.pk}/invitations/',
			{'invitee_public_id': Profile.objects.get(user=outsider).public_id},
			format='json',
		)
		self.assertEqual(nonfriend_response.status_code, status.HTTP_400_BAD_REQUEST)
		invite_data = {'invitee_public_id': Profile.objects.get(user=friend).public_id}
		first_response = self.client.post(f'/api/rooms/{room.pk}/invitations/', invite_data, format='json')
		duplicate_response = self.client.post(f'/api/rooms/{room.pk}/invitations/', invite_data, format='json')
		self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(RoomInvitation.objects.filter(room=room, invitee=friend, status=RoomInvitation.STATUS_PENDING).count(), 1)
		self.assertEqual(Notification.objects.filter(recipient=friend, notification_type='room_invitation').count(), 1)
		self.assertEqual(self.client.post(f'/api/rooms/{room.pk}/invitations/', {'invitee_public_id': Profile.objects.get(user=owner).public_id}, format='json').status_code, status.HTTP_400_BAD_REQUEST)

	def test_room_invitation_decline_is_recipient_only_and_resolves_notification(self):
		owner = User.objects.create_user(username='decline-owner', password='strong-password-123')
		invitee = User.objects.create_user(username='decline-invitee', password='strong-password-123')
		room = Room.objects.create(name='Decline room', owner=owner)
		RoomMembership.objects.create(room=room, user=owner)
		Friendship.create_for_users(owner, invitee)
		self.client.force_authenticate(user=owner)
		response = self.client.post(
			f'/api/rooms/{room.pk}/invitations/',
			{'invitee_public_id': Profile.objects.get(user=invitee).public_id},
			format='json',
		)
		invitation_id = response.data['data']['id']
		self.client.force_authenticate(user=owner)
		self.assertEqual(self.client.post(f'/api/room-invitations/{invitation_id}/decline/', format='json').status_code, status.HTTP_404_NOT_FOUND)
		self.client.force_authenticate(user=invitee)
		decline_response = self.client.post(f'/api/room-invitations/{invitation_id}/decline/', format='json')
		self.assertEqual(decline_response.status_code, status.HTTP_200_OK)
		self.assertEqual(decline_response.data['data']['status'], RoomInvitation.STATUS_DECLINED)
		self.assertFalse(RoomMembership.objects.filter(room=room, user=invitee).exists())
		self.assertIsNotNone(Notification.objects.get(recipient=invitee, notification_type='room_invitation').read_at)

	def test_room_owner_cannot_leave_and_only_owner_can_delete(self):
		owner = User.objects.create_user(username='owner-control', password='strong-password-123')
		member = User.objects.create_user(username='member-control', password='strong-password-123')
		room = Room.objects.create(name='Owned room', owner=owner)
		RoomMembership.objects.create(room=room, user=owner)
		RoomMembership.objects.create(room=room, user=member)
		self.client.force_authenticate(user=owner)
		self.assertEqual(self.client.post(f'/api/rooms/{room.pk}/leave/', format='json').status_code, status.HTTP_400_BAD_REQUEST)
		self.client.force_authenticate(user=member)
		self.assertEqual(self.client.delete(f'/api/rooms/{room.pk}/').status_code, status.HTTP_403_FORBIDDEN)
		self.client.force_authenticate(user=owner)
		self.assertEqual(self.client.delete(f'/api/rooms/{room.pk}/').status_code, status.HTTP_200_OK)
		self.assertFalse(Room.objects.filter(pk=room.pk).exists())

	def test_activity_counts_and_reading_direct_messages_resolves_unread_state(self):
		sender = User.objects.create_user(username='activity-sender', password='strong-password-123')
		recipient = User.objects.create_user(username='activity-recipient', password='strong-password-123')
		request_sender = User.objects.create_user(username='activity-requester', password='strong-password-123')
		Friendship.create_for_users(sender, recipient)
		conversation = Conversation.objects.create_for_participants(sender, recipient)
		message = DirectMessage.objects.create(conversation=conversation, sender=sender, content='Unread')
		message_notification = Notification.objects.create(
			recipient=recipient,
			notification_type='direct_message',
			content_type=ContentType.objects.get_for_model(DirectMessage),
			object_id=str(message.pk),
		)
		FriendRequest.objects.create(sender=request_sender, recipient=recipient)
		self.client.force_authenticate(user=recipient)
		counts = self.client.get('/api/activity/summary/').data['data']
		self.assertEqual(counts['messages'], 1)
		self.assertEqual(counts['friend_requests'], 1)
		self.client.get(f'/api/conversations/{conversation.pk}/messages/')
		message.refresh_from_db()
		message_notification.refresh_from_db()
		self.assertIsNotNone(message.read_at)
		self.assertIsNotNone(message_notification.read_at)
		self.assertEqual(self.client.get('/api/activity/summary/').data['data']['messages'], 0)

	def test_notifications_include_unread_count_and_can_be_marked_read(self):
		user = User.objects.create_user(username='notification-user', password='strong-password-123')
		notification = Notification.objects.create(recipient=user, notification_type='friend_request')
		self.client.force_authenticate(user=user)

		list_response = self.client.get('/api/notifications/')
		self.assertEqual(list_response.data['data']['unread_count'], 1)
		self.assertEqual(len(list_response.data['data']['notifications']), 1)

		read_response = self.client.post(f'/api/notifications/{notification.pk}/read/', format='json')
		self.assertEqual(read_response.status_code, status.HTTP_200_OK)
		self.assertIsNotNone(read_response.data['data']['read_at'])

	def test_rooms_cannot_be_created_without_a_name(self):
		user = User.objects.create_user(username='room-empty-name', password='strong-password-123')
		self.client.force_authenticate(user=user)

		response = self.client.post('/api/rooms/', {'name': '   '}, format='json')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertFalse(Room.objects.exists())

	def test_profile_can_be_retrieved_and_updated(self):
		user = User.objects.create_user(username='riyad', password='strong-password-123')
		self.assertTrue(Profile.objects.filter(user=user).exists())
		self.client.force_authenticate(user=user)

		get_response = self.client.get('/api/profile/')
		self.assertEqual(get_response.status_code, status.HTTP_200_OK)
		self.assertEqual(get_response.data['data']['username'], 'riyad')

		update_response = self.client.patch(
			'/api/profile/',
			{'username': 'new-riyad', 'display_name': 'Riyad', 'bio': 'Hanging out online.'},
			format='multipart',
		)
		self.assertEqual(update_response.status_code, status.HTTP_200_OK)
		self.assertEqual(update_response.data['data']['username'], 'new-riyad')
		self.assertEqual(update_response.data['data']['display_name'], 'Riyad')
		self.assertEqual(Profile.objects.get(user=user).bio, 'Hanging out online.')

	def test_profile_rejects_oversized_avatar(self):
		user = User.objects.create_user(username='riyad', password='strong-password-123')
		self.client.force_authenticate(user=user)
		avatar = SimpleUploadedFile('avatar.jpg', b'x' * (5 * 1024 * 1024 + 1), content_type='image/jpeg')

		response = self.client.patch('/api/profile/', {'avatar': avatar}, format='multipart')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('avatar', response.data)

	def test_profile_endpoint_only_updates_authenticated_user(self):
		first_user = User.objects.create_user(username='first', password='strong-password-123')
		second_user = User.objects.create_user(username='second', password='strong-password-123')
		self.client.force_authenticate(user=first_user)

		response = self.client.patch(
			'/api/profile/',
			{'display_name': 'First user'},
			format='multipart',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(Profile.objects.get(user=first_user).display_name, 'First user')
		self.assertEqual(Profile.objects.get(user=second_user).display_name, '')


class RealtimeMessagingTests(APITestCase):
	def _connect_user(self, path, user):
		token, _ = Token.objects.get_or_create(user=user)
		communicator = WebsocketCommunicator(application, f'{path}?token={token.key}')
		connected, _ = async_to_sync(communicator.connect)()
		self.assertTrue(connected)
		return communicator

	def test_private_chat_websocket_requires_authorized_friend_access(self):
		async def run_test():
			user_a = await database_sync_to_async(User.objects.create_user)(username='ws-a', password='strong-password-123')
			user_b = await database_sync_to_async(User.objects.create_user)(username='ws-b', password='strong-password-123')
			user_c = await database_sync_to_async(User.objects.create_user)(username='ws-c', password='strong-password-123')
			await database_sync_to_async(Friendship.create_for_users)(user_a, user_b)
			conversation = await database_sync_to_async(Conversation.objects.create_for_participants)(user_a, user_b)

			first_token = await database_sync_to_async(Token.objects.get_or_create)(user=user_a)
			second_token = await database_sync_to_async(Token.objects.get_or_create)(user=user_b)
			third_token = await database_sync_to_async(Token.objects.get_or_create)(user=user_c)
			first_socket = WebsocketCommunicator(application, f'/ws/chat/direct/{conversation.pk}/?token={first_token[0].key}')
			second_socket = WebsocketCommunicator(application, f'/ws/chat/direct/{conversation.pk}/?token={second_token[0].key}')
			connected_first, _ = await first_socket.connect()
			connected_second, _ = await second_socket.connect()
			self.assertTrue(connected_first)
			self.assertTrue(connected_second)

			communicator_c = WebsocketCommunicator(application, f'/ws/chat/direct/{conversation.pk}/?token={third_token[0].key}')
			connected_c, _ = await communicator_c.connect()
			self.assertFalse(connected_c)
			await communicator_c.disconnect()

			await first_socket.send_json_to({'type': 'message', 'content': 'hello from websocket'})
			first_message = await first_socket.receive_json_from()
			second_message = await second_socket.receive_json_from()
			self.assertEqual(first_message['type'], 'message')
			self.assertEqual(first_message['content'], 'hello from websocket')
			self.assertEqual(second_message['id'], first_message['id'])
			self.assertEqual(second_message['content'], 'hello from websocket')
			await first_socket.disconnect()
			await second_socket.disconnect()

		async_to_sync(run_test)()

	def test_room_chat_websocket_broadcasts_to_members_and_rejects_non_members(self):
		async def run_test():
			owner = await database_sync_to_async(User.objects.create_user)(username='ws-room-owner', password='strong-password-123')
			member = await database_sync_to_async(User.objects.create_user)(username='ws-room-member', password='strong-password-123')
			outsider = await database_sync_to_async(User.objects.create_user)(username='ws-room-outsider', password='strong-password-123')
			room = await database_sync_to_async(Room.objects.create)(name='Websocket room', owner=owner)
			await database_sync_to_async(RoomMembership.objects.create)(room=room, user=owner)
			await database_sync_to_async(RoomMembership.objects.create)(room=room, user=member)
			owner_token = await database_sync_to_async(Token.objects.get_or_create)(user=owner)
			member_token = await database_sync_to_async(Token.objects.get_or_create)(user=member)
			outsider_token = await database_sync_to_async(Token.objects.get_or_create)(user=outsider)
			owner_socket = WebsocketCommunicator(application, f'/ws/chat/room/{room.pk}/?token={owner_token[0].key}')
			member_socket = WebsocketCommunicator(application, f'/ws/chat/room/{room.pk}/?token={member_token[0].key}')
			outsider_socket = WebsocketCommunicator(application, f'/ws/chat/room/{room.pk}/?token={outsider_token[0].key}')
			connected_owner, _ = await owner_socket.connect()
			connected_member, _ = await member_socket.connect()
			connected_outsider, _ = await outsider_socket.connect()
			self.assertTrue(connected_owner)
			self.assertTrue(connected_member)
			self.assertFalse(connected_outsider)
			await outsider_socket.disconnect()

			await owner_socket.send_json_to({'type': 'message', 'content': 'hello room'})
			owner_message = await owner_socket.receive_json_from()
			member_message = await member_socket.receive_json_from()
			self.assertEqual(owner_message['type'], 'message')
			self.assertEqual(owner_message['content'], 'hello room')
			self.assertEqual(member_message['id'], owner_message['id'])
			self.assertEqual(member_message['content'], 'hello room')
			await owner_socket.disconnect()
			await member_socket.disconnect()

		async_to_sync(run_test)()

	def test_room_watch_session_accepts_supported_youtube_urls(self):
		owner = User.objects.create_user(username='watch-owner', password='strong-password-123')
		member = User.objects.create_user(username='watch-member', password='strong-password-123')
		room = Room.objects.create(name='Watch room', owner=owner)
		RoomMembership.objects.create(room=room, user=owner)
		RoomMembership.objects.create(room=room, user=member)
		self.client.force_authenticate(user=owner)

		invalid_response = self.client.post(
			f'/api/rooms/{room.pk}/watch/',
			{'video_url': 'https://example.com/not-allowed'},
			format='json',
		)
		self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)

		valid_response = self.client.post(
			f'/api/rooms/{room.pk}/watch/',
			{'video_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'},
			format='json',
		)
		self.assertEqual(valid_response.status_code, status.HTTP_200_OK)
		self.assertEqual(valid_response.data['data']['video_url'], 'https://www.youtube.com/watch?v=dQw4w9WgXcQ')
		self.assertEqual(valid_response.data['data']['is_playing'], False)

		self.client.force_authenticate(user=member)
		member_response = self.client.get(f'/api/rooms/{room.pk}/watch/')
		self.assertEqual(member_response.status_code, status.HTTP_200_OK)
		self.assertEqual(member_response.data['data']['video_url'], 'https://www.youtube.com/watch?v=dQw4w9WgXcQ')

	def test_room_watch_websocket_persists_and_broadcasts_video_state(self):
		async def run_test():
			owner = await database_sync_to_async(User.objects.create_user)(username='ws-watch-owner', password='strong-password-123')
			member = await database_sync_to_async(User.objects.create_user)(username='ws-watch-member', password='strong-password-123')
			room = await database_sync_to_async(Room.objects.create)(name='Websocket watch room', owner=owner)
			await database_sync_to_async(RoomMembership.objects.create)(room=room, user=owner)
			await database_sync_to_async(RoomMembership.objects.create)(room=room, user=member)
			owner_token = await database_sync_to_async(Token.objects.get_or_create)(user=owner)
			member_token = await database_sync_to_async(Token.objects.get_or_create)(user=member)
			owner_socket = WebsocketCommunicator(application, f'/ws/watch/{room.pk}/?token={owner_token[0].key}')
			member_socket = WebsocketCommunicator(application, f'/ws/watch/{room.pk}/?token={member_token[0].key}')
			connected_owner, _ = await owner_socket.connect()
			connected_member, _ = await member_socket.connect()
			self.assertTrue(connected_owner)
			self.assertTrue(connected_member)
			self.assertEqual((await owner_socket.receive_json_from())['type'], 'state')
			self.assertEqual((await member_socket.receive_json_from())['type'], 'state')

			await owner_socket.send_json_to({
				'action': 'set_video',
				'video_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
			})
			owner_update = await owner_socket.receive_json_from()
			member_update = await member_socket.receive_json_from()
			self.assertEqual(owner_update['type'], 'watch_state')
			self.assertEqual(member_update['type'], 'watch_state')
			self.assertEqual(member_update['state']['video_url'], 'https://www.youtube.com/watch?v=dQw4w9WgXcQ')
			session = await database_sync_to_async(RoomWatchSession.objects.get)(room=room)
			self.assertEqual(session.video_url, 'https://www.youtube.com/watch?v=dQw4w9WgXcQ')
			await owner_socket.disconnect()
			await member_socket.disconnect()

		async_to_sync(run_test)()


class ProductionHardeningTests(APITestCase):
	def make_image(self, image_format):
		image_file = BytesIO()
		Image.new('RGB', (2, 2), color='blue').save(image_file, format=image_format)
		return SimpleUploadedFile(
			f'avatar.{image_format.lower()}',
			image_file.getvalue(),
			content_type=f'image/{image_format.lower()}',
		)

	def make_large_image(self):
		image_file = BytesIO()
		Image.new('RGB', (5000, 5000), color='blue').save(image_file, format='PNG')
		return SimpleUploadedFile('large-avatar.png', image_file.getvalue(), content_type='image/png')

	def test_protected_endpoints_reject_unauthenticated_requests(self):
		for path in ('/api/profile/', '/api/rooms/', '/api/notifications/', '/api/conversations/'):
			with self.subTest(path=path):
				self.assertEqual(self.client.get(path).status_code, status.HTTP_401_UNAUTHORIZED)

	def test_notification_read_is_recipient_only(self):
		recipient = User.objects.create_user(username='notification-owner', password='strong-password-123')
		other_user = User.objects.create_user(username='notification-other', password='strong-password-123')
		notification = Notification.objects.create(recipient=recipient, notification_type='private')
		self.client.force_authenticate(user=other_user)

		response = self.client.post(f'/api/notifications/{notification.pk}/read/', format='json')

		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
		notification.refresh_from_db()
		self.assertIsNone(notification.read_at)

	def test_malformed_objects_and_public_ids_return_bad_request(self):
		user = User.objects.create_user(username='malformed-input-user', password='strong-password-123')
		self.client.force_authenticate(user=user)

		self.assertEqual(self.client.post('/api/rooms/', ['not', 'an object'], format='json').status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(
			self.client.post('/api/conversations/', {'participant_public_id': 'not-a-uuid'}, format='json').status_code,
			status.HTTP_400_BAD_REQUEST,
		)

	def test_registration_and_profile_apply_server_side_username_and_password_validation(self):
		weak_password_response = self.client.post(
			'/api/auth/register/',
			{
				'username': 'weak-password-user',
				'password': 'password123',
				'password_confirmation': 'password123',
			},
			format='json',
		)
		self.assertEqual(weak_password_response.status_code, status.HTTP_400_BAD_REQUEST)

		user = User.objects.create_user(username='valid-username', password='strong-password-123')
		self.client.force_authenticate(user=user)
		profile_response = self.client.patch(
			'/api/profile/',
			{'username': 'invalid username'},
			format='multipart',
		)
		self.assertEqual(profile_response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(
			self.client.get(f'/api/users/search/?username={"a" * 151}').status_code,
			status.HTTP_400_BAD_REQUEST,
		)

	def test_message_length_and_type_are_validated_server_side(self):
		user_a = User.objects.create_user(username='message-limit-a', password='strong-password-123')
		user_b = User.objects.create_user(username='message-limit-b', password='strong-password-123')
		Friendship.create_for_users(user_a, user_b)
		conversation = Conversation.objects.create_for_participants(user_a, user_b)
		room = Room.objects.create(name='Message limit room', owner=user_a)
		RoomMembership.objects.create(room=room, user=user_a)
		self.client.force_authenticate(user=user_a)
		oversized_content = {'content': 'x' * 5001}

		self.assertEqual(
			self.client.post(f'/api/conversations/{conversation.pk}/messages/', oversized_content, format='json').status_code,
			status.HTTP_400_BAD_REQUEST,
		)
		self.assertEqual(
			self.client.post(f'/api/rooms/{room.pk}/messages/', oversized_content, format='json').status_code,
			status.HTTP_400_BAD_REQUEST,
		)
		self.assertEqual(
			self.client.post(f'/api/rooms/{room.pk}/messages/', {'content': 123}, format='json').status_code,
			status.HTTP_400_BAD_REQUEST,
		)
		self.assertFalse(DirectMessage.objects.exists())
		self.assertFalse(RoomMessage.objects.exists())

	def test_registration_is_rate_limited(self):
		cache.clear()
		for attempt in range(6):
			payload = {
				'username': f'rate-limited-{attempt}',
				'password': 'strong-password-123',
				'password_confirmation': 'strong-password-123',
			}
			response = self.client.post('/api/auth/register/', payload, format='json')
			expected_status = status.HTTP_201_CREATED if attempt < 5 else status.HTTP_429_TOO_MANY_REQUESTS
			self.assertEqual(response.status_code, expected_status)

	def test_avatar_content_type_is_detected_and_limited_to_jpeg_or_png(self):
		user = User.objects.create_user(username='avatar-format-user', password='strong-password-123')
		profile = Profile.objects.get(user=user)
		self.client.force_authenticate(user=user)

		valid_response = self.client.patch(
			'/api/profile/',
			{'avatar': self.make_image('PNG')},
			format='multipart',
		)
		self.assertEqual(valid_response.status_code, status.HTTP_200_OK)

		invalid_response = self.client.patch(
			'/api/profile/',
			{'avatar': self.make_image('GIF')},
			format='multipart',
		)
		self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)
		large_response = self.client.patch(
			'/api/profile/',
			{'avatar': self.make_large_image()},
			format='multipart',
		)
		self.assertEqual(large_response.status_code, status.HTTP_400_BAD_REQUEST)
		profile.refresh_from_db()
		profile.avatar.delete(save=False)

	def test_message_history_is_bounded_and_supports_before_cursor(self):
		user_a = User.objects.create_user(username='history-page-a', password='strong-password-123')
		user_b = User.objects.create_user(username='history-page-b', password='strong-password-123')
		Friendship.create_for_users(user_a, user_b)
		conversation = Conversation.objects.create_for_participants(user_a, user_b)
		room = Room.objects.create(name='History page room', owner=user_a)
		RoomMembership.objects.create(room=room, user=user_a)
		direct_messages = [
			DirectMessage.objects.create(conversation=conversation, sender=user_a, content=f'Direct {index}')
			for index in range(105)
		]
		room_messages = [
			RoomMessage.objects.create(room=room, sender=user_a, content=f'Room {index}')
			for index in range(105)
		]
		self.client.force_authenticate(user=user_a)

		for path, all_messages in (
			(f'/api/conversations/{conversation.pk}/messages/', direct_messages),
			(f'/api/rooms/{room.pk}/messages/', room_messages),
		):
			with self.subTest(path=path):
				latest_page = self.client.get(path).data['data']
				self.assertEqual(len(latest_page), 100)
				self.assertEqual(latest_page[0]['id'], all_messages[5].pk)
				self.assertEqual(latest_page[-1]['id'], all_messages[-1].pk)
				older_page = self.client.get(f'{path}?before={latest_page[0]["id"]}').data['data']
				self.assertEqual([message['id'] for message in older_page], [message.pk for message in all_messages[:5]])

	def test_notification_lists_are_paginated_without_changing_response_shape(self):
		user = User.objects.create_user(username='notification-page-user', password='strong-password-123')
		Notification.objects.bulk_create([
			Notification(recipient=user, notification_type='test')
			for _ in range(101)
		])
		self.client.force_authenticate(user=user)

		first_page = self.client.get('/api/notifications/', HTTP_ORIGIN='http://localhost:5173')
		self.assertEqual(first_page.status_code, status.HTTP_200_OK)
		self.assertEqual(len(first_page.data['data']['notifications']), 100)
		self.assertEqual(first_page.data['data']['unread_count'], 101)
		self.assertEqual(first_page['X-Has-More'], 'true')
		self.assertEqual(first_page['X-Next-Offset'], '100')
		self.assertIn('x-has-more', first_page['access-control-expose-headers'].lower())

		second_page = self.client.get('/api/notifications/?offset=100')
		self.assertEqual(len(second_page.data['data']['notifications']), 1)
		self.assertEqual(second_page['X-Has-More'], 'false')
		self.assertEqual(second_page['X-Next-Offset'], '101')
