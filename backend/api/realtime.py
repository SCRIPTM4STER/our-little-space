from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def broadcast_chat_message(group_name, payload):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    message = dict(payload)
    message['type'] = 'message'
    async_to_sync(channel_layer.group_send)(
        group_name,
        {'type': 'chat_message', 'message': message},
    )
