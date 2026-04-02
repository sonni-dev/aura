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
from routines.models import Routine
from goals.models import Goal
from habits.models import Habit


class ReminderListView(ListView):
    model = Reminder
    template_name = 'reminders/reminder_list.html'
    context_object_name = 'reminders'

    def get_queryset(self):
        return (
            Reminder.objects.filter(is_active=True)
            .select_related('task', 'routine', 'goal', 'habit')
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
            .select_related('task', 'routine', 'goal', 'habit')
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

            # Modal dropdown - source FK options
            'freq_choices': Reminder.FREQ_CHOICES,
            'channel_choices': Reminder.CHANNEL_CHOICES,
            'tasks': Task.objects.filter(is_active=True, is_complete=False).order_by('name'),
            'routines': Routine.objects.filter(is_active=True).order_by('name'),
            'goals': Goal.objects.filter(is_active=True, is_complete=False).order_by('name'),
            'habits': Habit.objects.filter(is_active=True).order_by('name'),
        })
        return ctx


# ── AJAX: dismiss (deactivate one-time / advance recurring) ───────────────


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
