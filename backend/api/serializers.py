from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Conversation, DirectMessage, FriendRequest, Friendship, Notification, Profile, Room, RoomInvitation, RoomMessage


User = get_user_model()


def validate_username_value(value, excluded_user_id=None):
    value = value.strip()
    if not value:
        raise serializers.ValidationError('Username cannot be empty.')
    try:
        User._meta.get_field('username').run_validators(value)
    except DjangoValidationError as error:
        raise serializers.ValidationError(error.messages) from error
    if User.objects.filter(username__iexact=value).exclude(pk=excluded_user_id).exists():
        raise serializers.ValidationError('A user with this username already exists.')
    return value


class UserSerializer(serializers.ModelSerializer):
    public_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'public_id')

    def get_public_id(self, obj):
        profile = getattr(obj, 'profile', None)
        return str(profile.public_id) if profile and profile.public_id else None


class ProfileSerializer(serializers.ModelSerializer):
    public_id = serializers.UUIDField(read_only=True)
    username = serializers.CharField(required=False, max_length=150)
    avatar = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Profile
        fields = ('public_id', 'username', 'display_name', 'bio', 'avatar', 'created_at', 'updated_at')
        read_only_fields = ('public_id', 'username', 'created_at', 'updated_at')

    def validate_avatar(self, value):
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError('Profile pictures must be 5 MB or smaller.')
        image = getattr(value, 'image', None)
        image_format = getattr(image, 'format', None)
        if image_format not in ('JPEG', 'PNG'):
            raise serializers.ValidationError('Profile pictures must be JPEG or PNG images.')
        if image.width * image.height > 20_000_000:
            raise serializers.ValidationError('Profile pictures must be 20 megapixels or smaller.')
        return value

    def validate_username(self, value):
        user = self.instance.user if self.instance else None
        return validate_username_value(value, user.pk if user else None)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['username'] = instance.user.username
        data['avatar'] = instance.avatar.url if instance.avatar else None
        return data

    def update(self, instance, validated_data):
        username = validated_data.pop('username', None)
        if username is not None:
            instance.user.username = username
            instance.user.save(update_fields=('username',))
        return super().update(instance, validated_data)


class PublicProfileSerializer(serializers.ModelSerializer):
    public_id = serializers.UUIDField(read_only=True)
    username = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = ('public_id', 'username', 'display_name', 'bio', 'avatar')

    def get_username(self, obj):
        return obj.user.username

    def get_avatar(self, obj):
        return obj.avatar.url if obj.avatar else None


class FriendRequestSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    recipient = serializers.SerializerMethodField()

    class Meta:
        model = FriendRequest
        fields = ('id', 'sender', 'recipient', 'status', 'created_at', 'updated_at')

    def get_sender(self, obj):
        return PublicProfileSerializer(obj.sender.profile).data

    def get_recipient(self, obj):
        return PublicProfileSerializer(obj.recipient.profile).data


class FriendshipSerializer(serializers.ModelSerializer):
    friend = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()

    class Meta:
        model = Friendship
        fields = ('id', 'user', 'friend', 'created_at')

    def get_user(self, obj):
        return PublicProfileSerializer(obj.user_a.profile).data

    def get_friend(self, obj):
        return PublicProfileSerializer(obj.user_b.profile).data


class NotificationSerializer(serializers.ModelSerializer):
    related_object = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ('id', 'notification_type', 'related_object', 'read_at', 'created_at')

    def get_related_object(self, obj):
        related_object = obj.content_object
        if related_object is None:
            return None
        if isinstance(related_object, FriendRequest):
            return FriendRequestSerializer(related_object).data
        if isinstance(related_object, RoomInvitation):
            return RoomInvitationSerializer(related_object).data
        if isinstance(related_object, DirectMessage):
            return {
                'id': related_object.pk,
                'conversation_id': related_object.conversation_id,
                'sender': PublicProfileSerializer(related_object.sender.profile).data,
                'content': related_object.content[:120],
            }
        return None


class DirectMessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()

    class Meta:
        model = DirectMessage
        fields = ('id', 'sender', 'content', 'created_at', 'read_at')

    def get_sender(self, obj):
        return PublicProfileSerializer(obj.sender.profile).data


class ConversationSerializer(serializers.ModelSerializer):
    other_user = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ('id', 'other_user', 'last_message', 'created_at', 'updated_at')

    def get_other_user(self, obj):
        user = obj.user_b if obj.user_a_id == self.context['request'].user.pk else obj.user_a
        return PublicProfileSerializer(user.profile).data

    def get_last_message(self, obj):
        latest_messages = getattr(obj, 'latest_messages', None)
        message = latest_messages[0] if latest_messages else None
        if latest_messages is None:
            message = obj.messages.order_by('-created_at').first()
        if message is None:
            return None
        return DirectMessageSerializer(message).data


class RoomMessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()

    class Meta:
        model = RoomMessage
        fields = ('id', 'sender', 'content', 'created_at')

    def get_sender(self, obj):
        return PublicProfileSerializer(obj.sender.profile).data


class RoomSerializer(serializers.ModelSerializer):
    owner = serializers.SerializerMethodField()
    is_member = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = ('id', 'name', 'owner', 'is_owner', 'is_member', 'member_count', 'last_message', 'created_at', 'updated_at')

    def get_owner(self, obj):
        return PublicProfileSerializer(obj.owner.profile).data

    def get_is_member(self, obj):
        request = self.context.get('request')
        annotated_membership = getattr(obj, 'request_user_is_member', None)
        if annotated_membership is not None:
            return annotated_membership
        return bool(request and obj.memberships.filter(user=request.user).exists())

    def get_is_owner(self, obj):
        request = self.context.get('request')
        return bool(request and obj.owner_id == request.user.pk)

    def get_member_count(self, obj):
        memberships = getattr(obj, 'room_memberships', None)
        if memberships is not None:
            return len(memberships)
        annotated_count = getattr(obj, 'member_count', None)
        return annotated_count if annotated_count is not None else obj.memberships.count()

    def get_last_message(self, obj):
        latest_messages = getattr(obj, 'latest_messages', None)
        message = latest_messages[0] if latest_messages is not None and latest_messages else None
        if latest_messages is None:
            message = obj.messages.order_by('-created_at').first()
        return RoomMessageSerializer(message).data if message else None


class RoomInvitationSerializer(serializers.ModelSerializer):
    room = serializers.SerializerMethodField()
    inviter = serializers.SerializerMethodField()
    invitee = serializers.SerializerMethodField()

    class Meta:
        model = RoomInvitation
        fields = ('id', 'room', 'inviter', 'invitee', 'status', 'created_at', 'updated_at')

    def get_room(self, obj):
        return {'id': obj.room_id, 'name': obj.room.name}

    def get_inviter(self, obj):
        return PublicProfileSerializer(obj.inviter.profile).data

    def get_invitee(self, obj):
        return PublicProfileSerializer(obj.invitee.profile).data


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirmation = serializers.CharField(write_only=True)

    def validate_username(self, value):
        return validate_username_value(value)

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirmation']:
            raise serializers.ValidationError({'password_confirmation': 'Passwords do not match.'})
        candidate_user = User(username=attrs['username'], email=attrs.get('email', ''))
        try:
            validate_password(attrs['password'], user=candidate_user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({'password': error.messages}) from error
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirmation')
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            username=attrs['username'],
            password=attrs['password'],
        )
        if user is None:
            raise serializers.ValidationError('Invalid username or password.')
        if not user.is_active:
            raise serializers.ValidationError('This account is inactive.')
        attrs['user'] = user
        return attrs