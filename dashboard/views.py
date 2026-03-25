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


# ── /api/habits/week/ ─────────────────────────────────────────────────────────
 
def habits_week_api(request):
    """
    Returns all active habits with their 7-day log for the current week
    (Mon-Sun). Used by the habit dot-grid panel.
 
    Each day entry is either null (not logged) or an object with the value.
    """
    habits = Habit.objects.filter(is_active=True).order_by('order', 'name')

    data = []
    for habit in habits:
        week_logs = habit.logs_for_week()  # List of 7 HabitLog-or-None
        days = []
        for log in week_logs:
            if log is None:
                days.append(None)
            elif habit.metric_type == Habit.METRIC_YN:
                days.append({
                    'done': log.yn_value,
                    'value': log.display_value()
                })
            else:
                days.append({
                    'done': log.scale_value is not None, 
                    'value': log.display_value()
                })
        data.append({
            'id': habit.id,
            'name': habit.name,
            'metric_type': habit.metric_type,
            'streak': habit.streak(),
            'rate_30': habit.completion_rate(30),
            'days': days,   # index 0 = Monday
            'logged_today': habit.is_logged_today(),
        })
    return JsonResponse({'habits': data})


# ── /api/goals/ ───────────────────────────────────────────────────────────────
 
def goals_api(request):
    """
    Returns active goals with completion percentage and stall status.
    Used by the goal progress bars panel.
    """
    goals = Goal.objects.filter(is_active=True, is_complete=False).order_by(
        '-priority',
        'due_date'
    ).prefetch_related('items')

    data = []
    for goal in goals:
        data.append({
            'id': goal.id,
            'name': goal.name,
            'category': goal.category,
            'priority': goal.priority,
            'pct': goal.completion_pct(),
            'due_date': goal.due_date.isoformat() if goal.due_date else None,
            'is_overdue': goal.is_overdue,
            'days_since_progress': goal.days_since_progress,
            'items_total': goal.items.filter(is_active=True).count(),
            'items_done': goal.items.filter(is_active=True, is_complete=True).count(),
        })
    
    return JsonResponse({'goals': data})


