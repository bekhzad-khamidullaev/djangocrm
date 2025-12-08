"""
ViewSets for Common/Settings models API endpoints
"""
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from django.db.models import Q

from common.models import Department, Reminder, UserProfile

from .common_serializers import (
    DepartmentSerializer, ReminderSerializer, UserProfileSerializer
)


@extend_schema(tags=['Departments'])
class DepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only API for departments/groups"""
    serializer_class = DepartmentSerializer
    queryset = Department.objects.all().order_by('name')
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']
    
    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """Get all members of a department"""
        from api.serializers import UserSerializer
        
        department = self.get_object()
        users = department.user_set.all().order_by('username')
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)


@extend_schema(tags=['Reminders'])
class ReminderViewSet(viewsets.ModelViewSet):
    """CRUD API for reminders"""
    serializer_class = ReminderSerializer
    queryset = Reminder.objects.select_related('owner', 'content_type').all().order_by('-reminder_date')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['owner', 'content_type', 'active']
    search_fields = ['subject', 'description']
    ordering_fields = ['reminder_date', 'creation_date']
    
    def get_queryset(self):
        """Only show user's own reminders"""
        return self.queryset.filter(owner=self.request.user)
    
    def perform_create(self, serializer):
        """Set owner to current user"""
        serializer.save(owner=self.request.user)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming active reminders (next 7 days)"""
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        next_week = now + timedelta(days=7)
        
        reminders = self.get_queryset().filter(
            active=True,
            reminder_date__gte=now.date(),
            reminder_date__lte=next_week.date()
        ).order_by('reminder_date')
        
        serializer = self.get_serializer(reminders, many=True)
        return Response(serializer.data)


@extend_schema(tags=['User Profiles'])
class UserProfileViewSet(viewsets.ModelViewSet):
    """CRUD API for user profiles"""
    serializer_class = UserProfileSerializer
    queryset = UserProfile.objects.select_related('user').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['user']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'pbx_number']
    
    def get_queryset(self):
        """Non-staff users can only see their own profile"""
        qs = self.queryset
        user = self.request.user
        
        if user.is_staff or user.is_superuser:
            return qs
        
        return qs.filter(user=user)
    
    @action(detail=False, methods=['get', 'put', 'patch'])
    def me(self, request):
        """Get or update current user's profile"""
        try:
            profile = UserProfile.objects.get(user=request.user)
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=request.user)
        
        if request.method == 'GET':
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        else:
            serializer = self.get_serializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
