"""
Serializers for Massmail, Marketing, VoIP, Help models
"""
from rest_framework import serializers
from massmail.models import EmlMessage, EmailAccount, Signature, MailingOut
from marketing.models import Campaign, MessageTemplate, Segment
from voip.models import Connection, IncomingCall
from help.models import Page, Paragraph


# Massmail serializers

class EmailAccountSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    
    class Meta:
        model = EmailAccount
        fields = [
            'id', 'owner', 'owner_name', 'email_host_user', 'name', 
            'email_host', 'imap_host', 'from_email', 'main', 'massmail', 'do_import'
        ]
        extra_kwargs = {
            'email_host_password': {'write_only': True},
        }


class SignatureSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    
    class Meta:
        model = Signature
        fields = ['id', 'owner', 'owner_name', 'name', 'content']


class EmlMessageSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    
    class Meta:
        model = EmlMessage
        fields = ['id', 'owner', 'owner_name', 'subject', 'content', 'creation_date', 'update_date']
        read_only_fields = ['creation_date', 'update_date']


class MailingOutSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    message_name = serializers.CharField(source='message.name', read_only=True)
    
    class Meta:
        model = MailingOut
        fields = [
            'id', 'name', 'owner', 'owner_name', 'message', 'message_name',
            'sending_date', 'status', 'recipients_number', 'creation_date'
        ]
        read_only_fields = ['creation_date']


# Marketing serializers

class MessageTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageTemplate
        fields = ['id', 'name', 'channel', 'locale', 'subject', 'body', 'version', 'updated_at']
        read_only_fields = ['version', 'updated_at']


class SegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Segment
        fields = ['id', 'name', 'description', 'rules', 'size_cache', 'updated_at']
        read_only_fields = ['size_cache', 'updated_at']


class CampaignSerializer(serializers.ModelSerializer):
    segment_name = serializers.CharField(source='segment.name', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    
    class Meta:
        model = Campaign
        fields = ['id', 'name', 'segment', 'segment_name', 'template', 'template_name', 
                  'start_at', 'is_active', 'created_at']
        read_only_fields = ['created_at']


# VoIP serializers

class ConnectionSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.username', read_only=True)
    
    class Meta:
        model = Connection
        fields = ['id', 'provider', 'type', 'number', 'owner', 'owner_name', 'callerid', 'active']


class IncomingCallSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = IncomingCall
        fields = ['id', 'caller_id', 'user', 'user_name', 'client_name', 'client_type', 
                  'is_consumed', 'created_at']
        read_only_fields = ['created_at']


# Help serializers

class ParagraphSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paragraph
        fields = ['id', 'title', 'content', 'index_number', 'language_code']


class PageSerializer(serializers.ModelSerializer):
    paragraphs = ParagraphSerializer(many=True, read_only=True, source='paragraph_set')
    
    class Meta:
        model = Page
        fields = ['id', 'title', 'language_code', 'paragraphs']
