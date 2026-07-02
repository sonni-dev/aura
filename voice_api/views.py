import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware, is_naive
from django.views.decorators.http import require_GET, require_POST, require_http_methods


from reminders.models import Reminder
from lists.models import NamedList, ListItem
from .decorators import api_token_required


def _parse_body(request):
    try:
        return json.loads(request.body), None
    except json.JSONDecodeError:
        return None, JsonResponse({'error': 'Invalid JSON'}, status=400)


# ── Reminders & timers ───────────────────────────────────────────────────
# A "timer" is just a one-time Reminder with a near-term next_run - no
# separate model needed, the existing scheduling engine already covers it.


@api_token_required
@require_POST
def create_reminder(request):
    data, err = _parse_body(request)
    if err:
        return err

    title = data.get('title', '').strip()
    if not title:
        return JsonResponse({'error': 'A Title is required'}, status=400)

    frequency = data.get('frequency', Reminder.FREQ_ONCE)
    if frequency not in dict(Reminder.FREQ_CHOICES):
        return JsonResponse({'error': f'Unknown frequency: {frequency}'}, status=400)
    interval = max(1, int(data.get('interval', 1) or 1))

    next_run_raw = data.get('next_run')
    if next_run_raw:
        parsed = parse_datetime(next_run_raw)
        if parsed is None:
            return JsonResponse({'error': 'Invalid next_run - expected ISO 8601'}, status=400)
        next_run = make_aware(parsed) if is_naive(parsed) else parsed
    else:
        next_run = timezone.now()

    reminder = Reminder.objects.create(
        title=title,
        description=data.get('description', ''),
        frequency=frequency,
        interval=interval,
        next_run=next_run,
        start_date=next_run,
    )
    return JsonResponse({
        'id': reminder.pk,
        'title': reminder.title,
        'frequency': reminder.frequency,
        'next_run': reminder.next_run.isoformat(),
    })


