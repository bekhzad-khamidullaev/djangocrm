from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
)

from .views import (
    ChatMessageViewSet,
    CompanyViewSet,
    ContactViewSet,
    CrmTagViewSet,
    CustomTokenObtainPairView,
    DealViewSet,
    LeadViewSet,
    MemoViewSet,
    ProjectStageViewSet,
    ProjectViewSet,
    StageViewSet,
    TaskStageViewSet,
    TaskTagViewSet,
    CallLogViewSet,
    TaskViewSet,
    UserViewSet,
    auth_status,
    auth_statistics,
    dashboard_analytics,
    dashboard_activity,
    dashboard_funnel,
)

# Import CRM views
from .crm_views import (
    RequestViewSet,
    OutputViewSet,
    PaymentViewSet,
    ProductViewSet,
    CurrencyViewSet,
    CountryViewSet,
    CityViewSet,
    IndustryViewSet,
    LeadSourceViewSet,
    ClientTypeViewSet,
    ClosingReasonViewSet,
    CrmEmailViewSet,
    ShipmentViewSet,
    ProductCategoryViewSet,
)

# Import Common views
from .common_views import (
    DepartmentViewSet,
    ReminderViewSet,
    UserProfileViewSet,
)

# Import Analytics views
from .analytics_views import analytics_overview, PredictionViewSet

# Import Additional views (Massmail, Marketing, VoIP, Help)
from .additional_views import (
    EmailAccountViewSet, SignatureViewSet, EmlMessageViewSet, MailingOutViewSet,
    MessageTemplateViewSet, SegmentViewSet, CampaignViewSet,
    ConnectionViewSet, IncomingCallViewSet,
    PageViewSet, ParagraphViewSet
)

# Import Settings and SMS views
from .settings_views import SystemSettingsViewSet
from .sms_views import SMSViewSet

# Import VoIP views
from .voip_views import VoIPViewSet

# Import new comprehensive settings views
from .settings_api_views import (
    GeneralSettingsViewSet,
    APIKeyViewSet,
    WebhookViewSet,
    NotificationSettingsViewSet,
    SecuritySettingsViewSet,
    IntegrationLogViewSet,
    InstagramAccountViewSet,
    FacebookPageViewSet,
    TelegramBotViewSet,
)

app_name = 'api'

router = DefaultRouter()

# Core CRM endpoints
router.register('users', UserViewSet, basename='user')
router.register('deals', DealViewSet, basename='deal')
router.register('leads', LeadViewSet, basename='lead')
router.register('companies', CompanyViewSet, basename='company')
router.register('contacts', ContactViewSet, basename='contact')
router.register('requests', RequestViewSet, basename='request')
router.register('outputs', OutputViewSet, basename='output')
router.register('payments', PaymentViewSet, basename='payment')
router.register('shipments', ShipmentViewSet, basename='shipment')
router.register('crm-emails', CrmEmailViewSet, basename='crm-email')

# Products
router.register('products', ProductViewSet, basename='product')
router.register('product-categories', ProductCategoryViewSet, basename='product-category')

# CRM Reference data
router.register('stages', StageViewSet, basename='stage')
router.register('crm-tags', CrmTagViewSet, basename='crm-tag')
router.register('currencies', CurrencyViewSet, basename='currency')
router.register('countries', CountryViewSet, basename='country')
router.register('cities', CityViewSet, basename='city')
router.register('industries', IndustryViewSet, basename='industry')
router.register('lead-sources', LeadSourceViewSet, basename='lead-source')
router.register('client-types', ClientTypeViewSet, basename='client-type')
router.register('closing-reasons', ClosingReasonViewSet, basename='closing-reason')

# Tasks & Projects
router.register('tasks', TaskViewSet, basename='task')
router.register('projects', ProjectViewSet, basename='project')
router.register('memos', MemoViewSet, basename='memo')
router.register('task-stages', TaskStageViewSet, basename='task-stage')
router.register('project-stages', ProjectStageViewSet, basename='project-stage')
router.register('task-tags', TaskTagViewSet, basename='task-tag')

# Chat & Communication
router.register('chat-messages', ChatMessageViewSet, basename='chat-message')
router.register('call-logs', CallLogViewSet, basename='calllog')

# Common/Settings
router.register('departments', DepartmentViewSet, basename='department')
router.register('reminders', ReminderViewSet, basename='reminder')
router.register('profiles', UserProfileViewSet, basename='profile')

# Analytics endpoints are function-based views, not in router

# Massmail
router.register('massmail/email-accounts', EmailAccountViewSet, basename='email-account')
router.register('massmail/signatures', SignatureViewSet, basename='signature')
router.register('massmail/messages', EmlMessageViewSet, basename='eml-message')
router.register('massmail/mailings', MailingOutViewSet, basename='mailing-out')

# Marketing
router.register('marketing/templates', MessageTemplateViewSet, basename='message-template')
router.register('marketing/segments', SegmentViewSet, basename='segment')
router.register('marketing/campaigns', CampaignViewSet, basename='campaign')

# VoIP
router.register('voip/connections', ConnectionViewSet, basename='voip-connection')
router.register('voip/incoming-calls', IncomingCallViewSet, basename='incoming-call')

# Help/Documentation
router.register('help/pages', PageViewSet, basename='help-page')
router.register('help/paragraphs', ParagraphViewSet, basename='help-paragraph')

# System Settings (Legacy)
router.register('settings', SystemSettingsViewSet, basename='settings')

# New Settings Endpoints
router.register('settings/general', GeneralSettingsViewSet, basename='general-settings')
router.register('settings/api-keys', APIKeyViewSet, basename='api-keys')
router.register('settings/webhooks', WebhookViewSet, basename='webhooks')
router.register('settings/notifications', NotificationSettingsViewSet, basename='notifications')
router.register('settings/security', SecuritySettingsViewSet, basename='security')
router.register('settings/integration-logs', IntegrationLogViewSet, basename='integration-logs')

# Social Media Integrations
router.register('settings/instagram/accounts', InstagramAccountViewSet, basename='instagram-accounts')
router.register('settings/facebook/pages', FacebookPageViewSet, basename='facebook-pages')
router.register('settings/telegram/bots', TelegramBotViewSet, basename='telegram-bots')

# SMS
router.register('sms', SMSViewSet, basename='sms')

# VoIP & Cold Calls
router.register('voip', VoIPViewSet, basename='voip')

# Analytics & Predictions
router.register('predictions', PredictionViewSet, basename='predictions')

urlpatterns = [
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path(
        'docs/',
        SpectacularSwaggerView.as_view(url_name='api:schema'),
        name='docs',
    ),
    path(
        'redoc/',
        SpectacularRedocView.as_view(url_name='api:schema'),
        name='redoc',
    ),
    # JWT Authentication endpoints
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    # Legacy Token Authentication (for backward compatibility)
    path('auth/token/', obtain_auth_token, name='api-token'),
    # Authentication status and statistics
    path('auth/status/', auth_status, name='auth-status'),
    path('auth-stats/', auth_statistics, name='auth-statistics'),
    # Dashboard endpoints
    path('dashboard/analytics/', dashboard_analytics, name='dashboard-analytics'),
    path('dashboard/activity/', dashboard_activity, name='dashboard-activity'),
    path('dashboard/funnel/', dashboard_funnel, name='dashboard-funnel'),
    # Analytics
    path('analytics/overview/', analytics_overview, name='analytics-overview'),
    path('', include(router.urls)),
]
