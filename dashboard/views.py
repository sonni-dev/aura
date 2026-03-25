from django.http import JsonResponse
from django.views.generic import TemplateView
from django.utils import timezone
 
from tasks.models import Task
from routines.models import Routine, RoutineCompletion
from habits.models import Habit, HabitLog
from goals.models import Goal
from reminders.models import Reminder

from datetime import timedelta


class HudView(TemplateView):
    template_name = 'dashboard/hud.html'


## ---------- API calls for stats ---------- ##


# ── /api/stats/ ───────────────────────────────────────────────────────────────

def stats_api(request):
    """
    Aggregate counts for the four stat cards at the top of the HUD.
    """
    today = timezone.now().date()

    tasks_due_today = Task.objects.filter(
        is_active=True,
        is_complete=False,
        due_date=today,
    ).count()

    tasks_overdue = Task.objects.filter(
        is_active=True,
        is_complete=False,
        due_date__lt=today,
    ).count()

    active_reminders = Reminder.objects.filter(is_active=True).count()

    # Completion rate: tasks completed in last 30 days vs total active tasks
    thirty_days_ago = today - timedelta(days=30)
    completed_30 = Task.objects.filter(
        is_complete=True,
        completed_at__date__gte=thirty_days_ago,
    ).count()

    total_active = Task.objects.filter(is_active=True).count()
    completion_rate = (
        round((completed_30 / total_active) * 100) if total_active else 0
    )

    # Count active goal streaks (routines w streak > 0)
    routines_today = [r for r in Routine.objects.filter(is_active=True) if r.runs_today()]
    active_streaks = sum(1 for r in routines_today if r.streak() > 0)

    return JsonResponse({
        'tasks_due_today': tasks_due_today,
        'tasks_overdue': tasks_overdue,
        'active_reminders': active_reminders,
        'completion_rate': completion_rate,
        'active_streaks': active_streaks,
    })


# ── /api/routines/today/ ──────────────────────────────────────────────────────
 
def routines_today_api(request):
    """
    Returns all routines scheduled for today with their completion progress
    and streak count. Used by the routine rings panel.
    """
    today = timezone.now().date()
    routines = Routine.objects.filter(is_active=True).prefetch_related('items')

    data = []
    for routine in routines:
        if not routine.runs_today(today):
            continue
        done, total = routine.today_progress(today)
        data.append({
            'id': routine.id,
            'name': routine.name,
            'slot': routine.slot,
            'days': routine.day_labels(),
            'done': done,
            'total': total,
            'pct': routine.completion_pct(today),
            'streak': routine.streak(today),
            'items': [
                {
                    'id': item.id,
                    'title': item.title,
                    'category': item.category,
                    'done': item.is_done_today(today),
                }
                for item in routine.items.filter(is_active=True).order_by('order')
            ],
        })

    return JsonResponse({
        'routines': data,
    })