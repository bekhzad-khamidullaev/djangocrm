"""
Analytics URLs for built-in dashboard
"""
from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('dashboard/', views.analytics_dashboard, name='dashboard'),
    path('bi/', views.analytics_dashboard, name='bi'),
    path('api/dashboard/', views.dashboard_api, name='dashboard_api'),
]