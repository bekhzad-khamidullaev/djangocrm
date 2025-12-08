"""
Serializers for Common/Settings models API endpoints
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from common.models import Department, Reminder, UserProfile

User = get_user_model()


class DepartmentSerializer(serializers.ModelSerializer):
    """Serializer for Department (groups) model"""
    member_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Department
        fields = ['id', 'name', 'member_count']
    
    def get_member_count(self, obj):
        return obj.user_set.count()


class ReminderSerializer(serializers.ModelSerializer):
    """Serializer for Reminder model"""
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    
    class Meta:
        model = Reminder
        fields = [
            'id', 'owner', 'owner_name', 'subject', 'description',
            'reminder_date', 'send_notification_email', 'active',
            'creation_date', 'content_type', 'object_id'
        ]
        read_only_fields = ['creation_date']


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model"""
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = UserProfile
        fields = [
            'user', 'username', 'email', 'full_name',
            'pbx_number', 'utc_timezone', 'activate_timezone', 'language_code',
            'jssip_ws_uri', 'jssip_sip_uri', 'jssip_sip_password', 'jssip_display_name'
        ]
        read_only_fields = ['user']
        extra_kwargs = {
            'jssip_sip_password': {'write_only': True},
        }
