# service_provider/consumers.py
#
# Drop this next to models.py / views.py in the same app.
#
# Two consumers:
#
#  - NotifyConsumer  -> one per logged-in user, group "user_<id>".
#                       Pushes inbox/unread updates to the chat widget
#                       even when a specific thread isn't open (badge
#                       count, conversation list re-ordering, etc).
#
#  - ChatConsumer     -> one per open conversation, group "chat_<id>".
#                       Handles the live back-and-forth inside a thread.
#
# Both are AsyncWebsocketConsumers backed by the ORM via
# database_sync_to_async, so no extra sync machinery is needed.

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class NotifyConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope['user']
        if not user or not user.is_authenticated:
            await self.close()
            return
        self.group_name = f"user_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Fired when ChatConsumer publishes {"type": "chat.notify", ...}
    # to this user's group.
    async def chat_notify(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notify',
            'conversation_id': event['conversation_id'],
            'sender_name': event['sender_name'],
            'preview': event['preview'],
            'unread_count': event['unread_count'],
            'total_unread': event['total_unread'],
            'created_at': event['created_at'],
        }))


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope['user']
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']

        if not user or not user.is_authenticated:
            await self.close()
            return

        allowed = await self.user_can_access(user, self.conversation_id)
        if not allowed:
            await self.close()
            return

        self.group_name = f"chat_{self.conversation_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Mark the other person's messages read the moment this thread opens.
        await self.mark_read(user, self.conversation_id)

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        user = self.scope['user']
        try:
            data = json.loads(text_data)
        except (TypeError, ValueError):
            return

        # Lightweight "user is typing" ping — nothing is persisted, it's
        # just relayed to whoever else is in the thread's group right now.
        if data.get('type') == 'typing':
            await self.channel_layer.group_send(self.group_name, {
                'type': 'chat.typing',
                'sender_id': user.id,
            })
            return

        content = (data.get('message') or '').strip()
        if not content:
            return

        message = await self.save_message(user, self.conversation_id, content)
        other_user_id, other_unread, other_total_unread = await self.recipient_info(
            user, self.conversation_id
        )

        payload = {
            'type': 'chat.message',
            'id': message['id'],
            'sender_id': user.id,
            'sender_name': user.get_full_name() or user.username,
            'content': message['content'],
            'created_at': message['created_at'],
        }

        # Both sides currently viewing the thread get it instantly.
        await self.channel_layer.group_send(self.group_name, payload)

        # The recipient's badge/inbox updates even without the thread open.
        await self.channel_layer.group_send(f"user_{other_user_id}", {
            'type': 'chat.notify',
            'conversation_id': int(self.conversation_id),
            'sender_name': payload['sender_name'],
            'preview': content[:120],
            'unread_count': other_unread,
            'total_unread': other_total_unread,
            'created_at': payload['created_at'],
        })

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'id': event['id'],
            'sender_id': event['sender_id'],
            'sender_name': event['sender_name'],
            'content': event['content'],
            'created_at': event['created_at'],
        }))

    async def chat_typing(self, event):
        # Everyone in the group gets this, including the sender's own
        # connection — skip re-sending it back to whoever typed it.
        if event['sender_id'] == self.scope['user'].id:
            return
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'sender_id': event['sender_id'],
        }))

    # ---------------- DB helpers ----------------

    @database_sync_to_async
    def user_can_access(self, user, conversation_id):
        from .models import Conversation
        try:
            convo = Conversation.objects.select_related('provider').get(id=conversation_id)
        except Conversation.DoesNotExist:
            return False
        return user.id == convo.seeker_id or user.id == convo.provider.user_id

    @database_sync_to_async
    def save_message(self, user, conversation_id, content):
        from .models import Conversation, Message
        convo = Conversation.objects.get(id=conversation_id)
        msg = Message.objects.create(conversation=convo, sender=user, content=content)
        convo.save(update_fields=[])  # bumps updated_at (auto_now)
        return {
            'id': msg.id,
            'content': msg.content,
            'created_at': msg.created_at.isoformat(),
        }

    @database_sync_to_async
    def mark_read(self, user, conversation_id):
        from .models import Conversation
        convo = Conversation.objects.get(id=conversation_id)
        convo.messages.exclude(sender=user).filter(is_read=False).update(is_read=True)

    @database_sync_to_async
    def recipient_info(self, sender, conversation_id):
        from django.db.models import Q
        from .models import Conversation, Message, ServiceProvider
        convo = Conversation.objects.select_related('provider').get(id=conversation_id)
        other = convo.other_participant(sender)
        other_unread = convo.messages.exclude(sender=sender).filter(is_read=False).count()

        other_provider = ServiceProvider.objects.filter(user=other).first()
        convo_filter = Q(provider=other_provider) if other_provider else Q(seeker=other)
        total_unread = Message.objects.filter(
            conversation__in=Conversation.objects.filter(convo_filter),
            is_read=False,
        ).exclude(sender=other).count()

        return other.id, other_unread, total_unread