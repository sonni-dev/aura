import json
import difflib

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware, is_naive
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt


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

@csrf_exempt
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


@csrf_exempt
@api_token_required
@require_GET
def due_reminders(request):
    """Reminders due within the next N minutes (default 0 = due right now)"""
    within_minutes = int(request.GET.get('within_minutes', 0))
    cutoff = timezone.now() + timezone.timedelta(minutes=within_minutes)
    qs = (
        Reminder.objects
        .filter(is_active=True, is_complete=False, next_run__lte=cutoff)
        .order_by('next_run')
    )
    return JsonResponse({'reminders': [{
        'id': r.pk,
        'title': r.title,
        'frequency': r.frequency,
        'next_run': r.next_run.isoformat()}
        for r in qs
    ]})


@csrf_exempt
@api_token_required
@require_POST
def dismiss_reminder(request, pk):
    """Permanently complete a reminder (one-time reminders, or ending a recurring one early)"""
    print("!!!! DISMISS VIEW ACTUALLY RUNNING !!!!", flush=True)
    reminder = get_object_or_404(Reminder, pk=pk)
    reminder.dismiss(sync_source=True)
    return JsonResponse({'dismissed': True, 'id': reminder.pk})


@csrf_exempt
@api_token_required
@require_POST
def advance_reminder(request, pk):
    """For recurring reminders: push to next cycle after it fires, without completing it"""
    reminder = get_object_or_404(Reminder, pk=pk)
    if reminder.frequency == Reminder.FREQ_ONCE:
        return JsonResponse({'error': 'One-time reminder - use dismiss instead'}, status=400)
    reminder.advance_next_run()
    return JsonResponse({
        'advanced': True,
        'id': reminder.pk,
        'next_run': reminder.next_run.isoformat()
    })


# ── Lists ─────────────────────────────────────────────────────────────────


@csrf_exempt
@api_token_required
@require_http_methods(['GET', 'POST'])
def list_items(request, list_name):
    named_list, _ = NamedList.objects.get_or_create(name=list_name.lower().strip())

    if request.method == 'POST':
        data, err = _parse_body(request)
        if err:
            return err
        text = data.get('item', '').strip()
        if not text:
            return JsonResponse({'error': 'Item is required'}, status=400)
        item = ListItem.objects.create(list=named_list, text=text)
        return JsonResponse({'id': item.pk, 'item': item.text, 'list': named_list.name})

    items = named_list.items.filter(is_complete=False).order_by('created_at')
    return JsonResponse({
        'list': named_list.name,
        'items': [{'id': i.pk, 'item': i.text} for i in items],
    })


@csrf_exempt
@api_token_required
@require_POST
def complete_list_item(request, pk):
    item = get_object_or_404(ListItem, pk=pk)
    item.complete()
    return JsonResponse({'completed': True, 'id': item.pk})


@csrf_exempt
@api_token_required
@require_POST
def delete_list_item(request, pk):
    item = get_object_or_404(ListItem, pk=pk)
    item.delete()
    return JsonResponse({'deleted': True})


# ── Fuzzy Matching ─────────────────────────────────────────────────────────────────


def _fuzzy_match(query: str, candidates: dict):
    """
    candidates: dict of {lowercased_text: object}
    Returns a list of matched objects, best guesses first.
    Substring matches come first (cheap and usually exactly right for
    short spoken phrases), then difflib close-matches on whatever's left.
    """
    query = query.strip().lower()
    substring_hits = [obj for text, obj in candidates.items() if query in text]
    substring_texts = {text for text, obj in candidates.items() if query in text}
    remaining_texts = [t for t in candidates if t not in substring_texts]
    close = difflib.get_close_matches(query, remaining_texts, n=5, cutoff=0.4)
    fuzzy_hits = [candidates[t] for t in close]
    return (substring_hits + fuzzy_hits)[:5]


@csrf_exempt
@api_token_required
@require_GET
def search_reminders(request):
    """?q=<spoken phrase> -> ranked candidate reminders, best guess first."""
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'error': 'q parameter is required'}, status=400)

    qs = Reminder.objects.filter(is_active=True, is_complete=False)
    candidates = {r.title.lower(): r for r in qs}
    matches = _fuzzy_match(query, candidates)

    return JsonResponse({'results': [
        {'id': r.pk, 'title': r.title, 'frequency': r.frequency, 'next_run': r.next_run.isoformat()}
        for r in matches
    ]})


@csrf_exempt
@api_token_required
@require_GET
def search_list_items(request, list_name):
    """?q=<spoken phrase> -> ranked candidate items within one named list."""
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'error': 'q parameter is required'}, status=400)

    named_list = NamedList.objects.filter(name=list_name.lower().strip()).first()
    if not named_list:
        return JsonResponse({'results': []})

    qs = named_list.items.filter(is_complete=False)
    candidates = {i.text.lower(): i for i in qs}
    matches = _fuzzy_match(query, candidates)

    return JsonResponse({'results': [{'id': i.pk, 'item': i.text} for i in matches]})


@csrf_exempt
@api_token_required
@require_POST
def update_reminder(request, pk):
    """Change a reminder's title, time, and/or recurrence"""
    reminder = get_object_or_404(Reminder, pk=pk)
    data, err = _parse_body(request)
    if err:
        return err

    if 'title' in data:
        reminder.title = data['title'].strip()
    if 'next_run' in data:
        parsed = parse_datetime(data['next_run'])
        if parsed is None:
            return JsonResponse({'error': 'Invalid next_run - expected ISO 8601'}, status=400)
        reminder.next_run = make_aware(parsed) if is_naive(parsed) else parsed
    if 'frequency' in data:
        if data['frequency'] not in dict(Reminder.FREQ_CHOICES):
            return JsonResponse({'error': f'Unknown frequency: {data['frequency']}'}, status=400)
        reminder.frequency = data['frequency']
    if 'interval' in data:
        reminder.interval = max(1, int(data['interval']))


    reminder.save()
    return JsonResponse({
        'id': reminder.pk,
        'title': reminder.title,
        'frequency': reminder.frequency,
        'next_run': reminder.next_run.isoformat(),
    })
