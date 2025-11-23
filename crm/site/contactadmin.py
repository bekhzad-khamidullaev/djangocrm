from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.urls import path

from common.utils.parse_full_name import parse_contacts_name
from crm.forms.admin_forms import ContactForm
from crm.models.contact import Contact
from crm.models.company import Company
from crm.models.deal import Deal
from crm.site.crmmodeladmin import CrmModelAdmin
from crm.utils.admfilters import ByOwnerFilter
from crm.utils.admfilters import ScrollRelatedOnlyFieldListFilter
from massmail.admin_actions import make_mailing_out
from massmail.admin_actions import remove_vip_status
from massmail.admin_actions import specify_vip_recipients


class ContactAdmin(CrmModelAdmin):
    actions = [
        make_mailing_out,
        specify_vip_recipients,
        remove_vip_status,
        'bulk_send_sms',
        'bulk_send_telegram',
        'export_selected'
    ]
    form = ContactForm
    list_display = [
        'the_full_name',
        'the_email',
        'the_phone',
        'contact_company',
        'newsletters_subscriptions',
        'created',
        'person',
        'comm_actions',
    ]
    list_filter = (
        ByOwnerFilter,
        ('company__industry', ScrollRelatedOnlyFieldListFilter),
        ('company__type', admin.RelatedOnlyFieldListFilter),
    )
    radio_fields = {"sex": admin.HORIZONTAL}
    raw_id_fields = ('city', 'company')
    readonly_fields = [
        'owner',
        'modified_by',
        'creation_date',
        'update_date',
        'tag_list',
        'the_full_name',
        'the_email',
        'contact_company',
        'connections_to_phone',
        'connections_to_other_phone',
        'connections_to_mobile',
        'create_email',
        'unsubscribed'
    ]
    save_on_top = True
    search_fields = [
        'first_name', 'last_name',
        'email', 'secondary_email',
        'description', 'phone',
        'other_phone', 'mobile',
        'city_name',
        'address', 'company__full_name',
        'company__website',
        'company__city_name',
        'company__address',
        'company__email',
        'company__description',
    ]

    # -- ModelAdmin methods -- #

    def change_view(self, request, object_id,
                    form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['emails'] = self.get_latest_emails(
            'contact_id', object_id)
        extra_context['deal_num'] = Deal.objects.filter(
            contact_id=object_id).count()
        extra_context['del_dup_url'] = self.del_dup_url(object_id)
        self.add_remainder_context(
            request, extra_context, object_id,
            ContentType.objects.get_for_model(Contact)
        )
        return super().change_view(
            request, object_id, form_url,
            extra_context=extra_context,
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "company":
            initial = dict(request.GET.items())
            if initial.get('company', None):
                kwargs["queryset"] = Company.objects.filter(
                    id=int(initial['company'])
                )
        return super().formfield_for_foreignkey(
            db_field, request, **kwargs)

    def get_fieldsets(self, request, obj=None):
        return (
            [None if not obj else f'{obj}', {
                'fields': (
                    ('first_name', 'middle_name', 'last_name'),
                    ('title', 'sex'),
                    ('birth_date', 'was_in_touch'),
                    'description',
                    ('disqualified', self.massmail_field_name(obj))
                )
            }],
            *self.get_tag_fieldsets(obj),
            (_('Contact details'), {
                'fields': (
                    'email',
                    'create_email',
                    'secondary_email',
                    'phone',
                    'connections_to_phone',
                    'other_phone',
                    'connections_to_other_phone',
                    'mobile',
                    'connections_to_mobile',
                    ('lead_source', 'company'),
                    ('city', 'country'),
                    'region',
                    'district',
                    'address'
                )
            }),
            (_('Additional information'), {
                'classes': ('collapse',) if request.user.department_id else (),
                'fields': (
                    ('owner', 'department'),
                    'modified_by',
                    ('creation_date', 'update_date'),
                )
            }),
        )

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = self.readonly_fields
        if request.user.is_superuser:
            if readonly_fields.count('owner'):
                readonly_fields.remove('owner')
        return readonly_fields

    @admin.display(description=_('Comm'))
    def comm_actions(self, obj):
        from django.template.loader import render_to_string
        try:
            return mark_safe(render_to_string('admin/includes/comm_toolbar_row.html', {'obj': obj}))
        except Exception:
            # Fallback if template missing
            tel = getattr(obj, 'telegram_username', '') or ''
            ig = getattr(obj, 'instagram_username', '') or ''
            phone = getattr(obj, 'phone', '') or ''
            mobile = getattr(obj, 'mobile', '') or ''
            return mark_safe(f'<div class="comm-toolbar" data-phone="{phone}" data-mobile="{mobile}" data-telegram="{tel}" data-instagram="{ig}">\
              <button type="button" class="button" onclick="window.comm.clickToCall(this)">📞</button>\
              <button type="button" class="button" onclick="window.comm.sendSMS(this)">💬</button>\
              <button type="button" class="button" onclick="window.comm.sendTelegram(this)">✈️</button>\
              <button type="button" class="button" onclick="window.comm.sendInstagram(this)">📸</button></div>')

    def bulk_collect_phones(self, queryset):
        def first_phone(o):
            for f in ('mobile','phone','other_phone'):
                v = getattr(o, f, '')
                if v:
                    return v
            if getattr(o, 'company', None) and getattr(o.company, 'phone', ''):
                return o.company.phone
            return ''
        return [(o.id, first_phone(o)) for o in queryset]

    def bulk_collect_telegram(self, queryset):
        return [(o.id, (getattr(o, 'telegram_username', '') or '').lstrip('@')) for o in queryset]

    def bulk_send_sms(self, request, queryset):
        from django.shortcuts import render, redirect
        from django.contrib import messages
        from django.conf import settings
        from integrations.tasks import send_sms_task
        ids = list(queryset.values_list('id', flat=True))
        if 'apply' in request.POST:
            channel_id = int(request.POST.get('channel_id') or 0)
            text = (request.POST.get('text') or '').strip()
            if not (channel_id and text):
                messages.error(request, 'Channel and text are required')
                return redirect(request.get_full_path())
            for obj_id, to in self.bulk_collect_phones(queryset):
                if not to:
                    continue
                try:
                    # schedule async task
                    send_sms_task.delay(channel_id, to, text)
                except Exception:
                    send_sms_task(channel_id, to, text)
            messages.success(request, f'SMS queued for {len(ids)} objects')
            return redirect(request.get_full_path())
        ctx = {
            'action': 'bulk_send_sms',
            'ids': ids,
            'default_channel_id': getattr(settings, 'COMM_SMS_CHANNEL_ID', None),
        }
        return render(request, 'admin/bulk_actions/confirm_send.html', ctx)
    bulk_send_sms.short_description = 'Bulk send SMS'

    def bulk_send_telegram(self, request, queryset):
        from django.shortcuts import render, redirect
        from django.contrib import messages
        import requests
        from integrations.models import ChannelAccount
        acc = ChannelAccount.objects.filter(type='telegram', is_active=True).first()
        if not acc or not acc.telegram_bot_token:
            messages.error(request, 'Telegram channel not configured')
            return redirect(request.get_full_path())
        ids = list(queryset.values_list('id', flat=True))
        if 'apply' in request.POST:
            text = (request.POST.get('text') or '').strip()
            if not text:
                messages.error(request, 'Text is required')
                return redirect(request.get_full_path())
            api = f"https://api.telegram.org/bot{acc.telegram_bot_token}/sendMessage"
            sent = 0
            for obj_id, username in self.bulk_collect_telegram(queryset):
                if not username:
                    continue
                try:
                    requests.post(api, json={"chat_id": f"@{username}", "text": text}, timeout=10)
                    sent += 1
                except Exception:
                    pass
            messages.success(request, f'Telegram messages queued for {sent} users')
            return redirect(request.get_full_path())
        ctx = {
            'action': 'bulk_send_telegram',
            'ids': ids,
        }
        return render(request, 'admin/bulk_actions/confirm_send.html', ctx)
    bulk_send_telegram.short_description = 'Bulk send Telegram'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        initial = dict(request.GET.items())
        if initial.get('company', None):
            form.base_fields['company'].initial = Company.objects.get(
                id=int(initial['company'])
            )
        return form

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('make_massmail/',
                 admin.views.decorators.staff_member_required(
                    self.admin_site.admin_view(self.make_massmail)),
                 name='contact_make_massmail'
                 ),
        ]
        return my_urls + urls

    def save_model(self, request, obj, form, change):
        parse_contacts_name(obj)
        obj.owner = obj.company.owner
        obj.department_id = obj.company.department_id
        super().save_model(request, obj, form, change)

    # -- ModelAdmin callables -- #

    @admin.display(description=mark_safe(
        '<i class="material-icons" style="color: var(--body-quiet-color)">business</i>'
        ),
        ordering='company'
    )
    def contact_company(self, obj):
        return obj.company
