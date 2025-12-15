from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model

from .models import ChatMessage

User = get_user_model()


class UserMiniSerializer(serializers.ModelSerializer):
    """Minimal user info for chat messages"""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name', 'email']
    
    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class ChatMessageListSerializer(serializers.ModelSerializer):
    """Serializer for listing chat messages (minimal data)"""
    owner = UserMiniSerializer(read_only=True)
    reply_count = serializers.SerializerMethodField()
    is_reply = serializers.SerializerMethodField()
    preview = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatMessage
        fields = [
            'id',
            'content',
            'preview',
            'owner',
            'creation_date',
            'answer_to',
            'topic',
            'reply_count',
            'is_reply',
            'content_type',
            'object_id',
        ]
    
    def get_reply_count(self, obj):
        """Count replies to this message"""
        return ChatMessage.objects.filter(answer_to=obj).count()
    
    def get_is_reply(self, obj):
        """Check if this is a reply to another message"""
        return obj.answer_to is not None
    
    def get_preview(self, obj):
        """Return first 100 characters as preview"""
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content


class ChatMessageDetailSerializer(serializers.ModelSerializer):
    """Serializer for chat message details (full data)"""
    owner = UserMiniSerializer(read_only=True)
    recipients = UserMiniSerializer(many=True, read_only=True)
    to = UserMiniSerializer(many=True, read_only=True)
    answer_to = serializers.SerializerMethodField()
    topic = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()
    content_object_data = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatMessage
        fields = [
            'id',
            'content',
            'owner',
            'creation_date',
            'answer_to',
            'topic',
            'recipients',
            'to',
            'content_type',
            'object_id',
            'content_object_data',
            'replies',
        ]
    
    def get_answer_to(self, obj):
        """Get parent message info"""
        if obj.answer_to:
            return {
                'id': obj.answer_to.id,
                'content': obj.answer_to.content[:100],
                'owner': UserMiniSerializer(obj.answer_to.owner).data if obj.answer_to.owner else None,
            }
        return None
    
    def get_topic(self, obj):
        """Get topic message info"""
        if obj.topic:
            return {
                'id': obj.topic.id,
                'content': obj.topic.content[:100],
                'owner': UserMiniSerializer(obj.topic.owner).data if obj.topic.owner else None,
            }
        return None
    
    def get_replies(self, obj):
        """Get all replies to this message"""
        replies = ChatMessage.objects.filter(answer_to=obj).select_related('owner').order_by('creation_date')
        return ChatMessageListSerializer(replies, many=True).data
    
    def get_content_object_data(self, obj):
        """Get basic info about the linked object"""
        if obj.content_object:
            return {
                'type': obj.content_type.model,
                'id': obj.object_id,
                'str': str(obj.content_object),
            }
        return None


class ChatMessageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating chat messages"""
    recipient_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
        help_text="List of user IDs to send message to"
    )
    to_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
        help_text="List of user IDs mentioned in message"
    )
    
    class Meta:
        model = ChatMessage
        fields = [
            'id',
            'content',
            'content_type',
            'object_id',
            'answer_to',
            'topic',
            'recipient_ids',
            'to_ids',
            'creation_date',
        ]
        read_only_fields = ['id', 'creation_date']
    
    def validate_content(self, value):
        """Validate message content"""
        if not value or not value.strip():
            raise serializers.ValidationError("Message content cannot be empty")
        if len(value) > 10000:
            raise serializers.ValidationError("Message is too long (max 10000 characters)")
        return value.strip()
    
    def validate(self, data):
        """Validate the entire message"""
        # If it's a reply, ensure answer_to exists
        if data.get('answer_to'):
            if not ChatMessage.objects.filter(id=data['answer_to'].id).exists():
                raise serializers.ValidationError({"answer_to": "Parent message does not exist"})
        
        # Ensure content_type and object_id are provided
        if not data.get('content_type') or not data.get('object_id'):
            raise serializers.ValidationError("content_type and object_id are required")
        
        return data
    
    def create(self, validated_data):
        """Create message with recipients"""
        recipient_ids = validated_data.pop('recipient_ids', [])
        to_ids = validated_data.pop('to_ids', [])
        
        # Create message
        message = ChatMessage.objects.create(**validated_data)
        
        # Add recipients
        if recipient_ids:
            recipients = User.objects.filter(id__in=recipient_ids)
            message.recipients.set(recipients)
        
        # Add mentioned users
        if to_ids:
            to_users = User.objects.filter(id__in=to_ids)
            message.to.set(to_users)
        
        return message


class ChatMessageUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating chat messages"""
    
    class Meta:
        model = ChatMessage
        fields = ['content']
    
    def validate_content(self, value):
        """Validate message content"""
        if not value or not value.strip():
            raise serializers.ValidationError("Message content cannot be empty")
        if len(value) > 10000:
            raise serializers.ValidationError("Message is too long (max 10000 characters)")
        return value.strip()


class ChatThreadSerializer(serializers.Serializer):
    """Serializer for chat thread (topic + all messages)"""
    topic = ChatMessageDetailSerializer()
    messages = ChatMessageListSerializer(many=True)
    total_count = serializers.IntegerField()


class ChatStatisticsSerializer(serializers.Serializer):
    """Serializer for chat statistics"""
    total_messages = serializers.IntegerField()
    unread_count = serializers.IntegerField()
    conversations = serializers.IntegerField()
    recent_conversations = serializers.ListField()
