from __future__ import annotations
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
@require_POST
def preview_template(request):
    return JsonResponse({'status': 'ok'})
