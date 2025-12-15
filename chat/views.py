from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Max
from django.contrib.contenttypes.models import ContentType
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample

from .models import ChatMessage
from .serializers import (
    ChatMessageListSerializer,
    ChatMessageDetailSerializer,
    ChatMessageCreateSerializer,
    ChatMessageUpdateSerializer,
    ChatThreadSerializer,
    ChatStatisticsSerializer,
)


@extend_schema(tags=['Chat'])
class ChatMessageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing chat messages.
    
    Supports:
    - List messages filtered by content_object
    - Create new messages
    - Reply to existing messages
    - Get message threads
    - Get unread count
    - Mark messages as read
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Get messages visible to the current user"""
        user = self.request.user
        
        # Base queryset with optimizations
        qs = ChatMessage.objects.select_related(
            'owner',
            'content_type',
            'answer_to',
            'topic',
        ).prefetch_related(
            'recipients',
            'to',
        )
        
        # Filter: user is owner, recipient, or mentioned
        qs = qs.filter(
            Q(owner=user) | Q(recipients=user) | Q(to=user)
        ).distinct()
        
        # Additional filters from query params
        content_type_id = self.request.query_params.get('content_type')
        object_id = self.request.query_params.get('object_id')
        
        if content_type_id and object_id:
            qs = qs.filter(content_type_id=content_type_id, object_id=object_id)
        
        # Filter by topic (thread)
        topic_id = self.request.query_params.get('topic')
        if topic_id:
            qs = qs.filter(Q(topic_id=topic_id) | Q(id=topic_id))
        
        # Filter root messages only (no replies)
        root_only = self.request.query_params.get('root_only')
        if root_only and root_only.lower() in ['true', '1', 'yes']:
            qs = qs.filter(answer_to__isnull=True)
        
        return qs.order_by('-creation_date')
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return ChatMessageListSerializer
        elif self.action == 'retrieve':
            return ChatMessageDetailSerializer
        elif self.action == 'create':
            return ChatMessageCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ChatMessageUpdateSerializer
        return ChatMessageDetailSerializer
    
    def perform_create(self, serializer):
        """Set the owner to the current user"""
        serializer.save(owner=self.request.user)
    
    def perform_update(self, serializer):
        """Only owner can update their messages"""
        message = self.get_object()
        if message.owner != self.request.user:
            return Response(
                {'error': 'You can only edit your own messages'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer.save()
    
    def perform_destroy(self, instance):
        """Only owner can delete their messages"""
        if instance.owner != self.request.user and not self.request.user.is_staff:
            return Response(
                {'error': 'You can only delete your own messages'},
                status=status.HTTP_403_FORBIDDEN
            )
        instance.delete()
    
    @extend_schema(
        description="Reply to an existing message",
        request=ChatMessageCreateSerializer,
        responses={201: ChatMessageDetailSerializer}
    )
    @action(detail=True, methods=['post'])
    def reply(self, request, pk=None):
        """Create a reply to a message"""
        parent_message = self.get_object()
        
        # Create reply data
        data = request.data.copy()
        data['answer_to'] = parent_message.id
        data['content_type'] = parent_message.content_type_id
        data['object_id'] = parent_message.object_id
        
        # Set topic (inherit from parent or use parent as topic)
        data['topic'] = parent_message.topic_id if parent_message.topic else parent_message.id
        
        serializer = ChatMessageCreateSerializer(data=data)
        if serializer.is_valid():
            message = serializer.save(owner=request.user)
            detail_serializer = ChatMessageDetailSerializer(message)
            return Response(detail_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        description="Get all replies to a message",
        responses={200: ChatMessageListSerializer(many=True)}
    )
    @action(detail=True, methods=['get'])
    def replies(self, request, pk=None):
        """Get all replies to a specific message"""
        message = self.get_object()
        replies = ChatMessage.objects.filter(answer_to=message).select_related('owner').order_by('creation_date')
        serializer = ChatMessageListSerializer(replies, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        description="Get entire thread (topic + all messages in thread)",
        responses={200: ChatThreadSerializer}
    )
    @action(detail=True, methods=['get'])
    def thread(self, request, pk=None):
        """Get all messages in a thread (topic)"""
        message = self.get_object()
        topic = message.topic if message.topic else message
        
        # Get all messages in thread
        thread_messages = ChatMessage.objects.filter(
            Q(topic=topic) | Q(id=topic.id)
        ).select_related('owner').order_by('creation_date')
        
        return Response({
            'topic': ChatMessageDetailSerializer(topic).data,
            'messages': ChatMessageListSerializer(thread_messages, many=True).data,
            'total_count': thread_messages.count(),
        })
    
    @extend_schema(
        description="Get chat statistics for current user",
        responses={200: ChatStatisticsSerializer}
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get statistics about user's messages"""
        user = request.user
        
        # Total messages where user is involved
        total_messages = ChatMessage.objects.filter(
            Q(owner=user) | Q(recipients=user) | Q(to=user)
        ).distinct().count()
        
        # Unread count (messages where user is recipient but not owner)
        unread_count = ChatMessage.objects.filter(
            recipients=user
        ).exclude(owner=user).count()
        
        # Number of conversations (unique content_objects)
        conversations = ChatMessage.objects.filter(
            Q(owner=user) | Q(recipients=user) | Q(to=user)
        ).values('content_type', 'object_id').distinct().count()
        
        # Recent conversations
        recent = ChatMessage.objects.filter(
            Q(owner=user) | Q(recipients=user) | Q(to=user)
        ).values('content_type', 'object_id').annotate(
            last_message=Max('creation_date'),
            message_count=Count('id')
        ).order_by('-last_message')[:10]
        
        return Response({
            'total_messages': total_messages,
            'unread_count': unread_count,
            'conversations': conversations,
            'recent_conversations': list(recent),
        })
    
    @extend_schema(
        description="Get messages for a specific object (Deal, Lead, Task, etc)",
        parameters=[
            OpenApiParameter(name='content_type', description='Content type ID', required=True, type=int),
            OpenApiParameter(name='object_id', description='Object ID', required=True, type=int),
        ],
        responses={200: ChatMessageListSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def by_object(self, request):
        """Get all messages for a specific object"""
        content_type_id = request.query_params.get('content_type')
        object_id = request.query_params.get('object_id')
        
        if not content_type_id or not object_id:
            return Response(
                {'error': 'content_type and object_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        messages = self.get_queryset().filter(
            content_type_id=content_type_id,
            object_id=object_id
        ).order_by('creation_date')
        
        serializer = ChatMessageListSerializer(messages, many=True)
        return Response({
            'count': messages.count(),
            'results': serializer.data
        })
    
    @extend_schema(
        description="Get unread message count for current user",
        responses={200: {'type': 'object', 'properties': {'unread_count': {'type': 'integer'}}}}
    )
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get count of unread messages for current user"""
        user = request.user
        
        # Messages where user is recipient but not owner
        count = ChatMessage.objects.filter(
            recipients=user
        ).exclude(owner=user).count()
        
        return Response({'unread_count': count})
