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
])


@admin.register(RoomMessage)
class RoomMessageAdmin(admin.ModelAdmin):
    list_display = ("short_id", "room", "sender", "content_preview", "created_at", "deleated_at")
    list_display_links = ("short_id",)
    list_filter = ("room", "created_at", "deleated_at")
    search_fields = ("content", "sender__username", "room__name")
    readonly_fields = ("id", "created_at")
    ordering = ("-created_at",)

    def short_id(self, obj):
        return str(obj.pk)[:8]

    short_id.short_description = "ID"

    def content_preview(self, obj):
        return obj.content[:70]

    content_preview.short_description = "Content"
