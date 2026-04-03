import json
from datetime import timedelta
from typing import Any
 
from django.views.generic import ListView
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.utils import timezone
 
from .models import Reminder
from tasks.models import Task
from routines.models import Routine, RoutineItem
from goals.models import Goal, GoalItem
from habits.models import Habit


class ReminderListView(ListView):
    model = Reminder
    template_name = 'reminders/reminder_list.html'
    context_object_name = 'reminders'

    # All 6 FKs in select_related so the template never issues extra queries
    _SELECT = ('task', 'routine_item', 'routine', 'goal_item', 'goal', 'habit')

    def get_queryset(self):
        return (
            Reminder.objects.filter(is_active=True, is_complete=False)
            .select_related(*self._SELECT)
            .order_by('next_run')
        )
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        now = timezone.now()
        in_24h = now + timedelta(hours=24)

        active = ctx['reminders']

        due_now = [r for r in active if r.is_due]
        upcoming = [r for r in active if r.next_run and now < r.next_run <= in_24h]
        one_time = [r for r in active if r.frequency == Reminder.FREQ_ONCE]
        recurring = [r for r in active if r.frequency != Reminder.FREQ_ONCE]
        inactive = (
            Reminder.objects
            .filter(is_active=False)
            .select_related(*self._SELECT)
            .order_by('-updated_at')
        )

        ctx.update({
            'now': now,
            'total_active': active.count(),
            'due_now_count': len(due_now),
            'upcoming_count': len(upcoming),
            'one_time_count': len(one_time),
            'recurring_count': len(recurring),
            'inactive': inactive,

            # ── Modal dropdown source options — all 6 types ───────────────
            'freq_choices': Reminder.FREQ_CHOICES,
            'channel_choices': Reminder.CHANNEL_CHOICES,

            'tasks': Task.objects.filter(is_active=True, is_complete=False).order_by('name'),
            'routine_items': RoutineItem.objects.filter(is_active=True).select_related('routine').order_by('routine__name', 'order', 'title'),
            'routines': Routine.objects.filter(is_active=True).order_by('name'),
            'goal_items': GoalItem.objects.filter(is_active=True, is_complete=False).select_related('goal').order_by('goal__name', 'order', 'name'),
            'goals': Goal.objects.filter(is_active=True, is_complete=False).order_by('name'),
            'habits': Habit.objects.filter(is_active=True).order_by('name'),
        })
        return ctx


# ── AJAX: dismiss ─────────────────────────────────────────────────────────
#
# Calls Reminder.dismiss(sync_source=True) — the model method handles:
#   • Marking is_complete=True / is_active=False on the reminder
#   • Propagating to Task.mark_complete(), GoalItem.mark_complete(),
#     or RoutineItem.toggle_today() as appropriate
#   • Goal/Routine/Habit-level reminders are NOT auto-completed (too coarse)
#
# Use this for one-time reminders, or when permanently completing a
# recurring reminder tied to a specific item.


@require_POST
def dismiss(request, pk):
    """
    Dismiss a reminder from the HUD. Calls Reminder.dismiss(sync_source=True)
    so the linked source object (Task, GoalItem, RoutineItem) is also marked
    complete when applicable.
 
    Returns JSON so the template JS can remove the row without a page reload.
    """
    reminder = get_object_or_404(Reminder, pk=pk)
    reminder.dismiss(sync_source=True)
    return JsonResponse({'dismissed': True, 'id': reminder.pk})


# ── AJAX: advance ─────────────────────────────────────────────────────────
#
# For recurring reminders only. Pushes next_run forward to the next
# scheduled cycle WITHOUT marking the reminder complete and WITHOUT
# propagating to the source object. Use this when you've acknowledged
# the reminder but want it to come back on schedule (e.g., a weekly
# goal check-in that you've just reviewed).

@require_POST
def advance(request, pk):
    reminder = get_object_or_404(Reminder, pk=pk)
    if reminder.frequency == Reminder.FREQ_ONCE:
        return JsonResponse({'error': 'Cannot advance one-time reminder - use dismiss instead.'}, status=400)
    reminder.advance_next_run()
    return JsonResponse({
        'advanced': True,
        'id': reminder.pk,
        'next_run': reminder.next_run.isoformat() if reminder.next_run else None,
        'is_active': reminder.is_active,
    })


# ── AJAX: snooze ──────────────────────────────────────────────────────────
#
# Pushes next_run forward by N hours without touching the schedule or the
# source. Useful for "remind me again in an hour".

@require_POST
def snooze(request, pk):
    reminder = get_object_or_404(Reminder, pk=pk)
    try:
        data = json.loads(request.body)
        hours = int(data.get('hours', 1))
        if hours < 1:
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid snooze duration.'}, status=400)
    
    reminder.next_run = timezone.now() + timedelta(hours=hours)
    reminder.save(update_fields=['next_run', 'updated_at'])
    return JsonResponse({'snoozed': True, 'next_run': reminder.next_run.isoformat()})


# ── AJAX: save (create or update) ────────────────────────────────────────

@require_POST
def reminder_save(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)
    
    title = data.get('title', '').strip()
    if not title:
        return JsonResponse({'error': 'Title is required.'}, status=400)
    
    rid = data.get('reminder_id') or None
    r = get_object_or_404(Reminder, pk=rid) if rid else Reminder()

    r.title = title
    r.description = data.get('description', '').strip()
    r.frequency = data.get('frequency', Reminder.FREQ_ONCE)
    r.channel = data.get('channel', Reminder.CHANNEL_IN_APP)
    r.interval = max(1, int(data.get('interval', 1) or 1))

    # next_run — expects ISO datetime-local string (YYYY-MM-DDTHH:MM)
    next_run_raw = data.get('next_run', '').strip()
    if next_run_raw:
        try:
            from django.utils.dateparse import parse_datetime
            from django.utils.timezone import make_aware, is_naive

            parsed = parse_datetime(next_run_raw)
            if parsed is None:
                raise ValueError
            if is_naive(parsed):
                parsed = make_aware(parsed)
            r.next_run = parsed
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid date/time format.'}, status=400)
    elif not rid:
        r.next_run = timezone.now()
    
    # ── Source FK — clear all 6, then set the one chosen ─────────────────
    
    r.task         = None
    r.routine_item = None
    r.routine      = None
    r.goal_item    = None
    r.goal         = None
    r.habit        = None

    source_type = data.get('source_type', '').strip()
    source_id = data.get('source_id') or None

    SOURCE_MAP = {
        'task':         (Task,        'task'),
        'routine_item': (RoutineItem, 'routine_item'),
        'routine':      (Routine,     'routine'),
        'goal_item':    (GoalItem,    'goal_item'),
        'goal':         (Goal,        'goal'),
        'habit':        (Habit,       'habit'),
    }

    if source_type and source_id:
        entry = SOURCE_MAP.get(source_type)
        if not entry:
            return JsonResponse({'error': f'Unknown source type: {source_type}'}, status=400)
        model_cls, field = entry
        try:
            obj = model_cls.objects.get(pk=int(source_id))
            setattr(r, field, obj)
        except (ValueError, model_cls.DoesNotExist):
            return JsonResponse({'error': 'Linked source not found.'}, status=400)
    
    r.save()
    return JsonResponse({'ok': True, 'reminder_id': r.pk})
