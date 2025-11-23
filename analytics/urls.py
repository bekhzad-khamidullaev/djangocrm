"""
Analytics URLs for built-in dashboard
"""
from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('forecasts/', views.analytics_forecasts, name='forecasts'),
    path('api/forecasts/', views.forecasts_api, name='forecasts_api'),
    path('dashboard/', views.analytics_dashboard, name='dashboard'),
    path('bi/', views.analytics_dashboard, name='bi'),
    path('api/dashboard/', views.dashboard_api, name='dashboard_api'),
]