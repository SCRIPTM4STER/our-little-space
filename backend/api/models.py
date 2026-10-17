import uuid

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.utils import timezone


User = get_user_model()


class Profile(models.Model):
	public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
	display_name = models.CharField(max_length=80, blank=True)
	bio = models.CharField(max_length=240, blank=True)
	avatar = models.ImageField(upload_to='profile-avatars/', blank=True, null=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def save(self, *args, **kwargs):
		if self.pk:
			previous = Profile.objects.filter(pk=self.pk).values_list('public_id', flat=True).first()
			if previous is not None and str(self.public_id) != str(previous):
				raise ValueError('public_id cannot be changed after creation.')
		if not self.public_id:
			self.public_id = uuid.uuid4()
		super().save(*args, **kwargs)

	def __str__(self):
		return self.display_name or self.user.username


class FriendshipQuerySet(models.QuerySet):
	def are_friends(self, user_a, user_b):
		if user_a == user_b:
			return False
		return self.filter(
			Q(user_a=user_a, user_b=user_b) | Q(user_a=user_b, user_b=user_a)
		).exists()

	def for_user(self, user):
		return self.filter(Q(user_a=user) | Q(user_b=user)).select_related(
			'user_a', 'user_b', 'user_a__profile', 'user_b__profile',
		).order_by('-created_at', '-pk')


class Friendship(models.Model):
	user_a = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendships_as_a')
	user_b = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendships_as_b')
	created_at = models.DateTimeField(auto_now_add=True)

	objects = FriendshipQuerySet.as_manager()

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=['user_a', 'user_b'], name='unique_friendship_pair'),
		]

	def save(self, *args, **kwargs):
		if self.user_a_id == self.user_b_id:
			raise ValueError('A user cannot be friends with themselves.')
		if self.user_a_id and self.user_b_id and self.user_a_id > self.user_b_id:
			self.user_a, self.user_b = self.user_b, self.user_a
		if Friendship.objects.filter(
			Q(user_a=self.user_a, user_b=self.user_b) | Q(user_a=self.user_b, user_b=self.user_a)
		).exclude(pk=self.pk).exists():
			raise ValueError('This friendship already exists.')
		super().save(*args, **kwargs)

	@classmethod
	def create_for_users(cls, user_a, user_b):
		if user_a.pk > user_b.pk:
			user_a, user_b = user_b, user_a
		return cls.objects.get_or_create(user_a=user_a, user_b=user_b)[0]

	@classmethod
	def are_friends(cls, user_a, user_b):
		return cls.objects.are_friends(user_a, user_b)

	def other_user(self, user):
		if user.pk == self.user_a.pk:
			return self.user_b
		return self.user_a

	def __str__(self):
		return f'{self.user_a} <-> {self.user_b}'


class FriendRequest(models.Model):
	STATUS_PENDING = 'pending'
	STATUS_ACCEPTED = 'accepted'
	STATUS_REJECTED = 'rejected'
	STATUS_CHOICES = [
		(STATUS_PENDING, 'Pending'),
		(STATUS_ACCEPTED, 'Accepted'),
		(STATUS_REJECTED, 'Rejected'),
	]

	sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_friend_requests')
	recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_friend_requests')
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=['sender', 'recipient'], name='unique_friend_request_sender_recipient'),
		]

	def clean(self):
		if self.sender_id == self.recipient_id:
			raise ValueError('Users cannot send a friend request to themselves.')
		if Friendship.objects.are_friends(self.sender, self.recipient):
			raise ValueError('These users are already friends.')
		reverse_pending = FriendRequest.objects.filter(
			Q(sender=self.sender, recipient=self.recipient) | Q(sender=self.recipient, recipient=self.sender),
			status=self.STATUS_PENDING,
		).exclude(pk=self.pk).exists()
		if reverse_pending:
			raise ValueError('A pending friend request already exists for this user pair.')

	def save(self, *args, **kwargs):
		self.clean()
		super().save(*args, **kwargs)

	def accept(self):
		if self.status != self.STATUS_PENDING:
			raise ValueError('Only pending requests can be accepted.')
		self.status = self.STATUS_ACCEPTED
		self.updated_at = timezone.now()
		Friendship.create_for_users(self.sender, self.recipient)
		Notification.objects.create(
			recipient=self.sender,
			notification_type='friend_request_accepted',
			content_type=ContentType.objects.get_for_model(FriendRequest),
			object_id=str(self.pk),
		)
		FriendRequest.objects.filter(pk=self.pk).update(status=self.status, updated_at=self.updated_at)
		return self

	def reject(self):
		if self.status != self.STATUS_PENDING:
			raise ValueError('Only pending requests can be rejected.')
		self.status = self.STATUS_REJECTED
		self.updated_at = timezone.now()
		FriendRequest.objects.filter(pk=self.pk).update(status=self.status, updated_at=self.updated_at)
		return self

	def __str__(self):
		return f'{self.sender} -> {self.recipient} ({self.status})'


class Notification(models.Model):
	recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
	notification_type = models.CharField(max_length=50)
	content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
	object_id = models.CharField(max_length=255, blank=True, null=True)
	content_object = GenericForeignKey('content_type', 'object_id')
	read_at = models.DateTimeField(blank=True, null=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def mark_read(self):
		if self.read_at is None:
			self.read_at = timezone.now()
			self.save(update_fields=['read_at'])

	def __str__(self):
		return f'{self.recipient}::{self.notification_type}'


class ConversationManager(models.Manager):
	def create_for_participants(self, user_a, user_b):
		if user_a == user_b:
			raise ValueError('A conversation cannot be created with the same user.')
		if not Friendship.objects.are_friends(user_a, user_b):
			raise ValueError('Only friends can create a private conversation.')
		if user_a.pk > user_b.pk:
			user_a, user_b = user_b, user_a
		conversation, _ = self.get_or_create(user_a=user_a, user_b=user_b)
		return conversation

	def for_user(self, user):
		return self.filter(Q(user_a=user) | Q(user_b=user)).select_related('user_a', 'user_b', 'user_a__profile', 'user_b__profile')


class Conversation(models.Model):
	user_a = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations_as_a')
	user_b = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations_as_b')
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	objects = ConversationManager()

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=['user_a', 'user_b'], name='unique_conversation_pair'),
		]

	def save(self, *args, **kwargs):
		if self.user_a_id == self.user_b_id:
			raise ValueError('A conversation cannot be created with the same user.')
		if self.user_a_id and self.user_b_id and self.user_a_id > self.user_b_id:
			self.user_a, self.user_b = self.user_b, self.user_a
		super().save(*args, **kwargs)

	def participant_ids(self):
		return [self.user_a_id, self.user_b_id]

	def is_participant(self, user):
		return user.pk in self.participant_ids()

	def other_participant(self, user):
		if self.user_a_id == user.pk:
			return self.user_b
		return self.user_a

	def __str__(self):
		return f'{self.user_a} <-> {self.user_b}'


class DirectMessage(models.Model):
	conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
	sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_direct_messages')
	content = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True)
	read_at = models.DateTimeField(blank=True, null=True)

	class Meta:
		ordering = ['created_at']

	def __str__(self):
		return f'{self.sender}: {self.content[:40]}'


class Room(models.Model):
	name = models.CharField(max_length=80)
	owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_rooms')
	members = models.ManyToManyField(User, through='RoomMembership', related_name='group_rooms')
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-updated_at']

	def __str__(self):
		return self.name


class RoomMembership(models.Model):
	room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='memberships')
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='room_memberships')
	joined_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=['room', 'user'], name='unique_room_membership'),
		]


class RoomMessage(models.Model):
	room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='messages')
	sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_room_messages')
	content = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['created_at']

	def __str__(self):
		return f'{self.sender}: {self.content[:40]}'


class RoomWatchSession(models.Model):
	room = models.OneToOneField(Room, on_delete=models.CASCADE, related_name='watch_session')
	owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_watch_sessions')
	controller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='controlled_watch_sessions', null=True, blank=True)
	video_url = models.URLField(max_length=500, blank=True, default='')
	is_playing = models.BooleanField(default=False)
	position = models.FloatField(default=0.0)
	playback_rate = models.FloatField(default=1.0)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-updated_at']

	def __str__(self):
		return f'{self.room}: {self.video_url or "no video"}'


class RoomInvitation(models.Model):
	STATUS_PENDING = 'pending'
	STATUS_ACCEPTED = 'accepted'
	STATUS_DECLINED = 'declined'
	STATUS_CHOICES = [
		(STATUS_PENDING, 'Pending'),
		(STATUS_ACCEPTED, 'Accepted'),
		(STATUS_DECLINED, 'Declined'),
	]

	room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='invitations')
	inviter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_room_invitations')
	invitee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_room_invitations')
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=['room', 'invitee'],
				condition=Q(status='pending'),
				name='unique_pending_room_invitation',
			),
		]
		indexes = [
			models.Index(fields=['invitee', 'status'], name='room_invite_inbox_idx'),
		]

	def __str__(self):
		return f'{self.inviter} invited {self.invitee} to {self.room}'

