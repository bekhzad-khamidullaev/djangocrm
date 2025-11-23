from django.contrib import admin
from .models import Segment, MessageTemplate, Campaign, CampaignRun, DeliveryTask, DeliveryLog, Preferences


@admin.register(Segment)
class SegmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'size_cache', 'updated_at')
    search_fields = ('name',)


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'channel', 'locale', 'version', 'updated_at')
    list_filter = ('channel', 'locale')
    search_fields = ('name', 'body')


class CampaignRunInline(admin.TabularInline):
    model = CampaignRun
    extra = 0
    readonly_fields = ('started_at', 'finished_at', 'size', 'sent', 'delivered', 'failed', 'replied')


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'channel', 'segment', 'template', 'start_at', 'is_active')
    list_filter = ('channel', 'is_active')
    search_fields = ('name',)
    inlines = [CampaignRunInline]


@admin.register(DeliveryTask)
class DeliveryTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'campaign_run', 'target', 'status', 'created_at')
    list_filter = ('status',)


@admin.register(DeliveryLog)
class DeliveryLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'task', 'status', 'created_at')


@admin.register(Preferences)
class PreferencesAdmin(admin.ModelAdmin):
    list_display = ('target', 'allow_sms', 'allow_tg', 'allow_ig', 'allow_email', 'updated_at')
    list_filter = ('allow_sms', 'allow_tg', 'allow_ig', 'allow_email')
