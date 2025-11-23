import pandas as pd
import threading
from typing import Union
from django import forms
from django.conf import settings
from django.core.handlers.wsgi import WSGIRequest
from django.template.response import TemplateResponse
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.urls import path
from django.urls import reverse
from django.utils.translation import gettext as _

from crm.models import Company
from crm.models import Contact
from crm.models import Lead
from crm.utils.create_objects import create_objects
from common.site.crmsite import BaseSite


class UploadFileForm(forms.Form):
    file = forms.FileField(label=_("Your Excel file"))


class CrmAdminSite(BaseSite):

    def system_settings_view(self, request):
        from django.conf import settings as dj_settings
        items = []
        for name in dir(dj_settings):
            if name.isupper():
                try:
                    val = getattr(dj_settings, name)
                except Exception as e:
                    val = f'<error: {e}>'
                tname = type(val).__name__
                items.append({'name': name, 'val': val, 'type': tname})
        items.sort(key=lambda x: x['name'])
        ctx = self.each_context(request)
        ctx.update({'settings_items': items, 'title': 'System settings'})
        return TemplateResponse(request, 'admin/system_settings.html', ctx)

    def each_context(self, request):
        ctx = super().each_context(request)
        # Inject quick link into branding via extra context variable if needed later
        ctx['crm_system_settings_url'] = 'site:system-settings'
        return ctx

    

    def get_urls(self):
        urls = super().get_urls()
        urls.pop(next(
            i for i, v in enumerate(urls) 
            if v.name == 'login'
        ))
        my_urls = [
            path('system-settings/', self.system_settings_view, name='system-settings'),
            path('import_contacts/', self.import_objects,
                 {'attr': 'contact', 'object': Contact,
                  'columns': settings.CONTACT_COLUMNS,
                  'uniq1': 'first_name',
                  'uniq2': 'email'
                  },
                 name='import_contacts',
                 ),
            path('import-companies/', self.import_objects,
                 {'attr': 'company', 'object': Company,
                  'columns': settings.COMPANY_COLUMNS,
                  'uniq1': 'full_name',
                  'uniq2': 'country'
                  },
                 name='import_companies',
                 ),
            path('import_leads/', self.import_objects,
                 {'attr': 'lead', 'object': Lead,
                  'columns': settings.LEAD_COLUMNS,
                  'uniq1': 'first_name',
                  'uniq2': 'email'
                  },
                 name='import_leads',
                 ),
            path(
                settings.SECRET_LOGIN_PREFIX,
                self.login, name='login'
            ),
        ]
        return my_urls + urls

    def import_objects(self, request: WSGIRequest, **kwargs
                       ) -> Union[HttpResponseRedirect, TemplateResponse]:
        request.current_app = self.name
        if request.method == 'POST':
            form = UploadFileForm(request.POST, request.FILES)
            if form.is_valid():
                xl = pd.ExcelFile(request.FILES['file'])
                df1 = xl.parse()
                df1 = df1.fillna('')
                df1.columns = map(str.lower, df1.columns)
                messages.success(
                    request,
                    'Found %s Objects. They are being processed. \
                    Please refresh page in a few minutes.' % len(df1.index)
                )
                t = threading.Thread(
                    target=create_objects, args=(request, df1), kwargs=kwargs
                )
                t.daemon = True
                t.start()
                return HttpResponseRedirect(
                    reverse('site:crm_%s_changelist' % kwargs['attr'])
                )
        else:
            form = UploadFileForm()

        context = self.each_context(request)
        context['form'] = form
        context['field_list'] = kwargs['columns']
        extra_context = dict(
            crm_site.each_context(request),
            opts=kwargs['object']._meta,    # NOQA
            form=form,
            field_list=kwargs['columns']
        )
        return TemplateResponse(
            request, "crm/import_objects.html", extra_context
        )


crm_site = CrmAdminSite(name='site')
crm_site.disable_action('delete_selected')
