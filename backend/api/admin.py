from django.contrib import admin

from .models import (
	Conversation,
	DirectMessage,
	FriendRequest,
	Friendship,
	Notification,
	Profile,
	Room,
	RoomMembership,
	RoomMessage,
)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
	list_display = ('user', 'display_name', 'updated_at')
	search_fields = ('user__username', 'display_name')


admin.site.register([
	Friendship,
	FriendRequest,
	Notification,
	Conversation,
	DirectMessage,
	Room,
	RoomMembership,
	RoomMessage,
])
