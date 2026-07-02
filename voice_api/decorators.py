from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


def api_token_required(view_func):
    """
    Simple shared-secret auth for script/device access, as opposed to the
    session-based CSRF-protected views used by the browser dashboard.
 
    Expects header: Authorization: Bearer <VOICE_ASSISTANT_API_TOKEN>
 
    This is intentionally lightweight rather than full DRF - swap in DRF
    token/session auth later if this API surface grows past a handful of
    endpoints (already on the project roadmap).
    """
    @csrf_exempt
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        expected = f'Bearer {settings.VOICE_ASSISTANT_API_TOKEN}'
        if not settings.VOICE_ASSISTANT_API_TOKEN or request.headers.get('Authorization') != expected:
            return JsonResponse({'error': 'Unauthorized'}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapped
