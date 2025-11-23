from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

class SipmlClientView(LoginRequiredMixin, TemplateView):
    template_name = "voip/sipml_client.html"
