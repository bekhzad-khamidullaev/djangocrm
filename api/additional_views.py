"""
ViewSets for Massmail, Marketing, VoIP, Help models
"""
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from django.db.models import Q

from massmail.models import EmlMessage, EmailAccount, Signature, MailingOut
from marketing.models import Campaign, MessageTemplate, Segment
from voip.models import Connection, IncomingCall
from help.models import Page, Paragraph

from .additional_serializers import (
    EmlMessageSerializer, EmailAccountSerializer, SignatureSerializer, MailingOutSerializer,
    CampaignSerializer, MessageTemplateSerializer, SegmentSerializer,
    ConnectionSerializer, IncomingCallSerializer,
    PageSerializer, ParagraphSerializer
)


# Massmail ViewSets

@extend_schema(tags=['Massmail'])
class EmailAccountViewSet(viewsets.ModelViewSet):
    serializer_class = EmailAccountSerializer
    queryset = EmailAccount.objects.select_related('owner').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['email', 'name']
    filterset_fields = ['owner', 'main', 'massmail', 'do_import']
    
    def get_queryset(self):
        qs = self.queryset
        if not self.request.user.is_superuser:
            qs = qs.filter(owner=self.request.user)
        return qs


@extend_schema(tags=['Massmail'])
class SignatureViewSet(viewsets.ModelViewSet):
    serializer_class = SignatureSerializer
    queryset = Signature.objects.select_related('owner').all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = self.queryset
        if not self.request.user.is_superuser:
            qs = qs.filter(owner=self.request.user)
        return qs


@extend_schema(tags=['Massmail'])
class EmlMessageViewSet(viewsets.ModelViewSet):
    serializer_class = EmlMessageSerializer
    queryset = EmlMessage.objects.select_related('owner').all().order_by('-creation_date')
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'subject', 'content']
    filterset_fields = ['owner']
    
    def get_queryset(self):
        qs = self.queryset
        if not self.request.user.is_superuser:
            qs = qs.filter(owner=self.request.user)
        return qs


@extend_schema(tags=['Massmail'])
class MailingOutViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MailingOutSerializer
    queryset = MailingOut.objects.select_related('owner', 'message').all().order_by('-sending_date')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['owner', 'status']
    
    def get_queryset(self):
        qs = self.queryset
        if not self.request.user.is_superuser:
            qs = qs.filter(owner=self.request.user)
        return qs


# Marketing ViewSets

@extend_schema(tags=['Marketing'])
class MessageTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = MessageTemplateSerializer
    queryset = MessageTemplate.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'subject']
    filterset_fields = ['channel']


@extend_schema(tags=['Marketing'])
class SegmentViewSet(viewsets.ModelViewSet):
    serializer_class = SegmentSerializer
    queryset = Segment.objects.all().order_by('-updated_at')
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']


@extend_schema(tags=['Marketing'])
class CampaignViewSet(viewsets.ModelViewSet):
    serializer_class = CampaignSerializer
    queryset = Campaign.objects.select_related('segment', 'template').all().order_by('-created_at')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['name']
    filterset_fields = ['is_active', 'segment', 'template']


# VoIP ViewSets

@extend_schema(tags=['VoIP'])
class ConnectionViewSet(viewsets.ModelViewSet):
    serializer_class = ConnectionSerializer
    queryset = Connection.objects.all()
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['provider', 'active']


@extend_schema(tags=['VoIP'])
class IncomingCallViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IncomingCallSerializer
    queryset = IncomingCall.objects.select_related('user').all().order_by('-created_at')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['caller_id', 'client_name']
    filterset_fields = ['user', 'client_type', 'is_consumed']
    
    def get_queryset(self):
        qs = self.queryset
        if not self.request.user.is_superuser:
            qs = qs.filter(user=self.request.user)
        return qs


# Help ViewSets

@extend_schema(tags=['Help'])
class PageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PageSerializer
    queryset = Page.objects.prefetch_related('paragraph_set').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['title', 'slug']
    filterset_fields = ['language_code']


@extend_schema(tags=['Help'])
class ParagraphViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ParagraphSerializer
    queryset = Paragraph.objects.all().order_by('index_number')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['language_code', 'document']
