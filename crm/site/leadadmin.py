from email.utils import parseaddr
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.contrib import admin
from django.db import IntegrityError
from django.db.models import Q
from django.utils.safestring import mark_safe
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from common.utils.parse_full_name import parse_contacts_name
from crm.forms.admin_forms import LeadForm
from crm.models import Company
from crm.models import Contact
from crm.models import Deal
from crm.models import Lead
from crm.models import CrmEmail
from crm.models import Request
from crm.site.crmmodeladmin import CrmModelAdmin
from crm.utils.admfilters import ByOwnerFilter
from crm.utils.admfilters import IsDisqualifiedFilter
from crm.utils.admfilters import TagFilter
from crm.utils.check_city import check_city
from crm.utils.helpers import get_email_domain
from massmail.admin_actions import make_mailing_out
from massmail.admin_actions import remove_vip_status
from massmail.admin_actions import specify_vip_recipients

THE_SAME_COMPANY_NAME_MSG = "Error! A new company was not created because a company " \
                            "with the same name already exists in the database."
MULTIPLE_COMPANIES_MSG = "Error! Found multiple companies '{}' in the database."
MULTIPLE_CONTACTS_MSG = "Error! Found multiple CONTACTS '{}' in the database."


class LeadAdmin(CrmModelAdmin):
    @admin.display(description=_('Comm'))
    def comm_actions(self, obj):
        from django.template.loader import render_to_string
        try:
            return mark_safe(render_to_string('admin/includes/comm_toolbar_row.html', {'obj': obj}))
        except Exception:
            tel = getattr(obj, 'telegram_username', '') or ''
            ig = getattr(obj, 'instagram_username', '') or ''
            phone = getattr(obj, 'phone', '') or ''
            mobile = getattr(obj, 'mobile', '') or ''
            return mark_safe(f'<div class="comm-toolbar" data-phone="{phone}" data-mobile="{mobile}" data-telegram="{tel}" data-instagram="{ig}">\
              <button type="button" class="button" onclick="window.comm.clickToCall(this)">📞</button>\
              <button type="button" class="button" onclick="window.comm.sendSMS(this)">💬</button>\
              <button type="button" class="button" onclick="window.comm.sendTelegram(this)">✈️</button>\
              <button type="button" class="button" onclick="window.comm.sendInstagram(this)">📸</button></div>')
    actions = [
        make_mailing_out,
        specify_vip_recipients,
        remove_vip_status,
        'export_selected'
    ]
    filter_horizontal = ('industry',)
    form = LeadForm
    list_display = [
        'comm_actions',

        'the_full_name',
        'the_email',
        'display_company_name',
        'person',
        'newsletters_subscriptions',
        'created'
    ]
    list_display_links = ('the_full_name',)
    list_filter = (
        IsDisqualifiedFilter,
        ByOwnerFilter,
        TagFilter
    )
    raw_id_fields = (
        'city',
        'contact',
        'company'
        )
    readonly_fields = (
        'modified_by',
        'warning',
        'creation_date',
        'update_date',
        'tag_list',
        'the_full_name',
        'the_email',
        'display_company_name',
        'connections_to_phone',
        'connections_to_other_phone',
        'connections_to_mobile',
        'create_email'
    )
    search_fields = [
        'first_name',
        'last_name',
        'email',
        'secondary_email',
        'company_name',
        'description',
        'phone',
        'other_phone',
        'mobile',
        'city_name',
        'address'
    ]

    # -- ModelAdmin methods -- #

    def change_view(self, request, object_id,
                    form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['emails'] = self.get_latest_emails('lead_id', object_id)
        extra_context['deal_num'] = Deal.objects.filter(
            lead_id=object_id).count()
        extra_context['del_dup_url'] = self.del_dup_url(object_id)
        self.add_remainder_context(
            request, extra_context, object_id,
            ContentType.objects.get_for_model(Lead)
        )
        return super().change_view(
            request, object_id, form_url,
            extra_context=extra_context,
        )

    def get_fieldsets(self, request, obj=None):
        tag_fieldset = self.get_tag_fieldsets(obj)
        fieldsets = (
            (None, {
                'fields': [
                    ('lead_source', 'disqualified', 
                     self.massmail_field_name(obj)),
                    ('contact', 'company')
                ],
            }),
            (_('Person contact details'), {
                'fields': (
                    ('first_name', 'middle_name', 'last_name'),
                    ('email', 'title'),
                    'create_email',
                    'phone',
                    'connections_to_phone',
                )
            }),
            (_('Additional person details'), {
                'classes': ('collapse',),
                'fields': (
                    ('sex', 'birth_date'),
                    'was_in_touch',
                    'secondary_email',
                    'other_phone',
                    'connections_to_other_phone',
                    'mobile',
                    'connections_to_mobile',
                )
            }),
            (_('Company contact details'), {
                'fields': (
                    ('company_name', 'website'),
                    'company_email',
                    ('city', 'country'),
                    'region',
                    'district',
                    'address',
                    'type',
                    'industry',
                )
            }),
            (None, {
                'fields': ('description',)
            }),
            *tag_fieldset,
            (_('Additional information'), {
                'classes': ('collapse',) if request.user.department_id else (),
                'fields': (
                    ('owner', 'department'),
                    'modified_by',
                    ('creation_date', 'update_date'),
                )
            }),
        )
        fls = fieldsets[0][1]['fields']
        if obj and obj.disqualified:
            if fls[0] != 'warning':
                fls.insert(0, 'warning')       # NOQA
        else:
            if fls[0] == 'warning':
                fls.pop(0)
        return fieldsets

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
            channel_name = (request.POST.get('channel_name') or '').strip()
            text = (request.POST.get('text') or '').strip()
            from integrations.models import ChannelAccount
            acc = ChannelAccount.objects.filter(is_active=True, type__in=['eskiz','playmobile'], name__iexact=channel_name).first()
            if not (acc and text):
                messages.error(request, 'Channel and text are required')
                return redirect(request.get_full_path())
            for obj_id, to in self.bulk_collect_phones(queryset):
                if not to:
                    continue
                try:
                    send_sms_task.delay(acc.id, to, text)
                except Exception:
                    send_sms_task(acc.id, to, text)
            messages.success(request, f'SMS queued for {len(ids)} objects')
            return redirect(request.get_full_path())
        ctx = {
            'action': 'bulk_send_sms',
            'ids': ids,
            'sms_channels': list(ChannelAccount.objects.filter(is_active=True, type__in=['eskiz','playmobile']).values('id','name','type')),
            'default_channel_name': getattr(settings, 'COMM_SMS_CHANNEL_NAME', None),
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
        if '_convert' in request.POST:
            form.convert = True
        return form

    def response_post_save_change(self, request, obj):
        if '_convert' in request.POST:
            if obj.company:
                company = obj.company
            else:
                _, email = parseaddr(obj.company_email)
                domain = get_email_domain(email)
                q_params = Q(full_name=obj.company_name)
                try:  # TODO: improve this with phone & secondary email
                    if domain:
                        q_params &= Q(email__contains=domain)
                    company = Company.objects.get(q_params)

                except Company.DoesNotExist:
                    try:
                        company = create_company(obj)
                        company.industry.add(*obj.industry.all())
                    except IntegrityError:
                        messages.error(
                            request,
                            gettext(THE_SAME_COMPANY_NAME_MSG.format(
                                obj.company_name))
                        )
                        return super().response_post_save_change(request, obj)

                except Company.MultipleObjectsReturned:
                    messages.error(
                        request,
                        gettext(MULTIPLE_COMPANIES_MSG.format(obj.company_name))
                    )
                    return super().response_post_save_change(request, obj)

            if obj.contact:
                contact = obj.contact
            else:
                q_params = Q()
                if obj.email:
                    emails = obj.email.split(',')
                    for email in emails:
                        _, email = parseaddr(obj.email)
                        q_params |= Q(email__contains=email)
                        q_params |= Q(secondary_email__contains=email)
                if obj.phone:
                    digits = [i for i in obj.phone if i.isdigit()]
                    digits_re = ''.join((f'[^0-9]*[{i}]{{1}}' for i in digits))
                    phone_re = fr"{digits_re}"
                    q_params |= Q(phone__iregex=phone_re)
                    q_params |= Q(other_phone__iregex=phone_re)
                try:
                    contact = Contact.objects.get(
                        q_params,
                        first_name=obj.first_name,
                        last_name=obj.last_name,
                    )
                except Contact.DoesNotExist:
                    contact = create_contact(obj, company)
                except Contact.MultipleObjectsReturned:
                    messages.error(
                        request,
                        gettext(MULTIPLE_CONTACTS_MSG.format(obj.full_name))
                    )
                    return super().response_post_save_change(request, obj)

            Deal.objects.filter(lead=obj).update(
                lead=None, contact=contact, company=contact.company)
            Request.objects.filter(lead=obj).update(
                lead=None, contact=contact)
            CrmEmail.objects.filter(lead=obj).update(
                lead=None, contact=contact, company=contact.company)
            messages.success(
                request,
                gettext(f'The lead "{obj}" has been converted successfully.')
            )
            obj.delete()

        return super().response_post_save_change(request, obj)

    def save_model(self, request, obj, form, change):
        parse_contacts_name(obj)
        check_city(obj, form)
        super().save_model(request, obj, form, change)

    # -- ModelAdmin Callables -- #

    @admin.display(description=_('Warning:'))
    def warning(self, instance):       # NOQA
        txt = _('This Lead is disqualified! Please read the description.')
        return mark_safe(f'<span style="color: var(--error-fg);">{txt}</span>')


# -- Custom Methods-- #

def create_company(obj: Lead) -> Company:
    return Company.objects.create(
        full_name=obj.company_name,
        website=obj.website,
        phone=obj.company_phone,
        city_name=obj.city_name,
        city=obj.city,
        address=obj.address,
        email=obj.company_email,
        description=obj.description,
        lead_source=obj.lead_source,
        country=obj.country,
        type=obj.type,
        owner=obj.owner,
        department=obj.department,
        disqualified=obj.disqualified,
        massmail=obj.massmail,
        # -- new fields --#
        region=obj.region,
        district=obj.district
    )


def create_contact(obj: Lead, company: Company) -> Contact:
    return Contact.objects.create(
        first_name=obj.first_name,
        last_name=obj.last_name,
        title=obj.title,
        sex=obj.sex,
        birth_date=obj.birth_date,
        was_in_touch=obj.was_in_touch,
        email=obj.email,
        secondary_email=obj.secondary_email,
        phone=obj.phone,
        other_phone=obj.other_phone,
        mobile=obj.mobile,
        company=company,
        country=obj.country,
        address=obj.address,
        description=obj.description,
        lead_source=obj.lead_source,
        owner=obj.owner,
        department=obj.department,
        disqualified=obj.disqualified,
        massmail=obj.massmail,
        # -- new fields --#
        region=obj.region,
        district=obj.district
    )
