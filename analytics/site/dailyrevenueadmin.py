from django.utils.translation import gettext_lazy as _
from analytics.site.anlmodeladmin import AnlModelAdmin
from django.contrib.auth.models import User
from common.models import Department
from analytics.views import get_dashboard_data

class DailyRevenueAdmin(AnlModelAdmin):
    change_list_template = 'analytics/daily_revenue_changelist.html'
    list_display = ()

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

    def changelist_view(self, request, extra_context=None):
        period = request.GET.get('period', '30d')
        owner = request.GET.get('owner')
        department = request.GET.get('department')
        if request.user.is_superuser:
            dept_qs = Department.objects.all()
            owner_qs = User.objects.all()
        else:
            dept_qs = Department.objects.filter(id__in=request.user.groups.values('id'))
            owner_qs = User.objects.filter(groups__in=dept_qs).distinct()
        data = get_dashboard_data(period=period, owner_id=owner, department_id=department)
        extra = {
            'title': _('Daily Revenue Forecast'),
            'revenue_daily_forecast': data.get('revenue_daily_forecast'),
            'owners': list(owner_qs.values('id','first_name','last_name').order_by('first_name','last_name')),
            'departments': list(dept_qs.values('id','name').order_by('name')),
            'period': period,
            'owner': owner,
            'department': department,
        }
        if extra_context:
            extra_context.update(extra)
        else:
            extra_context = extra
        return super().changelist_view(request, extra_context=extra_context)
