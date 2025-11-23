# from django.contrib.auth.decorators import login_required
# from django.contrib.admin.views.decorators import staff_member_required
from django.urls import path
from voip.views.callback import ConnectionView
from voip.views.incoming import IncomingCallPollView
from voip.views.jssip import JsSipClientView
from voip.views.sipml import SipmlClientView
from voip.views.voipwebhook import VoIPWebHook
from voip.views.onlinepbx_webhook import OnlinePBXWebHook
from voip.views.onlinepbx_api import OnlinePBXAuthView, OnlinePBXCallView
from voip.views.routing import (
    IncomingCallView, CallStatusUpdateView, QueueManagementView, 
    CallStatisticsView, handle_incoming_call, update_call_status_api, 
    get_queue_status
)
from voip.views.dashboard import (
    CallDashboardView, QueueMonitorView, DashboardStatsAPIView,
    GroupPerformanceAPIView, RecentCallsAPIView, LiveQueueAPIView,
    SystemStatusAPIView, dashboard_view, queue_monitor_view
)

app_name = 'voip'


urlpatterns = [
    path('get-callback/',
         ConnectionView.as_view(),
         name='get_callback'
         ),    
    path('zd/',
         VoIPWebHook.as_view(),
         name='voip-zadarma-pbx-notification'
         ),
    path('api/incoming-call/',
         IncomingCallPollView.as_view(),
         name='voip_incoming_call_poll'
         ),
     path('obx/',
          OnlinePBXWebHook.as_view(),
          name='voip-onlinepbx-webhook'
          ),
    path('client/',
         JsSipClientView.as_view(),
         name='voip_jssip_client'
         ),
    path('sipml/',
         SipmlClientView.as_view(),
         name='voip_sipml_client'
         ),
     # OnlinePBX management endpoints
     path('obx/auth/',
          OnlinePBXAuthView.as_view(),
          name='voip-onlinepbx-auth'
          ),
     path('obx/call/',
          OnlinePBXCallView.as_view(),
          name='voip-onlinepbx-call'
          ),
     
     # Call Routing and Queue Management API
     path('incoming/',
          IncomingCallView.as_view(),
          name='voip-incoming-call'
          ),
     path('status/',
          CallStatusUpdateView.as_view(),
          name='voip-call-status'
          ),
     path('queue/',
          QueueManagementView.as_view(),
          name='voip-queue-management'
          ),
     path('queue/<int:group_id>/',
          QueueManagementView.as_view(),
          name='voip-queue-group'
          ),
     path('stats/',
          CallStatisticsView.as_view(),
          name='voip-call-statistics'
          ),
     
     # Simple function-based endpoints
     path('api/incoming/',
          handle_incoming_call,
          name='voip-api-incoming'
          ),
     path('api/status/',
          update_call_status_api,
          name='voip-api-status'
          ),
     path('api/queue/',
          get_queue_status,
          name='voip-api-queue'
          ),
     path('api/queue/<int:group_id>/',
          get_queue_status,
          name='voip-api-queue-group'
          ),
     
     # Dashboard and Monitoring
     path('dashboard/',
          CallDashboardView.as_view(),
          name='voip-dashboard'
          ),
     path('monitor/',
          QueueMonitorView.as_view(),
          name='voip-queue-monitor'
          ),
     
     # Dashboard API endpoints
     path('api/dashboard/stats/',
          DashboardStatsAPIView.as_view(),
          name='voip-dashboard-stats'
          ),
     path('api/dashboard/groups/',
          GroupPerformanceAPIView.as_view(),
          name='voip-group-performance'
          ),
     path('api/dashboard/recent-calls/',
          RecentCallsAPIView.as_view(),
          name='voip-recent-calls'
          ),
     path('api/dashboard/live-queue/',
          LiveQueueAPIView.as_view(),
          name='voip-live-queue'
          ),
     path('api/system/status/',
          SystemStatusAPIView.as_view(),
          name='voip-system-status'
          ),
     
     # Simple function endpoints
     path('simple/dashboard/',
          dashboard_view,
          name='voip-simple-dashboard'
          ),
     path('simple/monitor/',
          queue_monitor_view,
          name='voip-simple-monitor'
          ),
]
