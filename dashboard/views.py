from django.views.generic import TemplateView
from django.utils import timezone
from datetime import timedelta

from tasks.models import Task
from routines.models import Routine, RoutineCompletion, RoutineItem, WEEKDAY_MAP
from goals.models import Goal
from habits.models import Habit, HabitLog
from reminders.models import Reminder


class HudView(TemplateView):
    template_name = 'dashboard/hud3.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.now().date()
        now   = timezone.now()

        # ── Tasks ─────────────────────────────────────────────────────────
        tasks_overdue = Task.objects.filter(
            is_active=True, is_complete=False, due_date__lt=today
        ).order_by('due_date', '-priority')

        tasks_due_today = Task.objects.filter(
            is_active=True, is_complete=False, due_date=today
        ).order_by('-priority')

        tasks_upcoming = Task.objects.filter(
            is_active=True, is_complete=False, due_date__gt=today
        ).order_by('due_date', '-priority')[:5]

        tasks_in_progress = Task.objects.filter(
            is_active=True, is_complete=False, status='in_progress'
        ).count()

        tasks_todo_count = Task.objects.filter(
            is_active=True, is_complete=False
        ).count()

        # Recent completions (last 30 days) for completion rate
        completed_30 = Task.objects.filter(
            is_complete=True,
            completed_at__gte=now - timedelta(days=30)
        ).count()
        total_30 = Task.objects.filter(
            created_at__lte=now,
            created_at__gte=now - timedelta(days=30)
        ).count()
        task_completion_rate = round((completed_30 / total_30 * 100) if total_30 else 0)

        # ── Routines ──────────────────────────────────────────────────────
        all_routines = Routine.objects.filter(is_active=True).prefetch_related('items')
        today_routines_raw = [r for r in all_routines if r.runs_today(today)]

        today_routines = []
        global_done = 0
        global_total = 0

        for r in today_routines_raw:
            active_items = list(r.items.filter(is_active=True).order_by('order', 'title'))
            done_set = set(
                RoutineCompletion.objects.filter(
                    item__in=active_items, completed_on=today
                ).values_list('item_id', flat=True)
            )
            done  = len(done_set)
            total = len(active_items)
            global_done  += done
            global_total += total
            pct = round((done / total * 100) if total else 0)

            items_annotated = [
                {'item': item, 'done': item.id in done_set}
                for item in active_items
            ]
            today_routines.append({
                'routine': r,
                'done':    done,
                'total':   total,
                'pct':     pct,
                'streak':  r.streak(today),
                'items':   items_annotated,
            })

        overall_routine_pct = round((global_done / global_total * 100) if global_total else 0)

        # ── Goals ─────────────────────────────────────────────────────────
        active_goals = Goal.objects.filter(is_active=True, is_complete=False).prefetch_related('items')
        goals_data = []
        for g in active_goals:
            pct = g.completion_pct()
            # Color tier for progress bar
            if pct >= 75:
                color_class = 'bg-theme'
            elif pct >= 40:
                color_class = 'bg-warning'
            else:
                color_class = 'bg-danger'

            goals_data.append({
                'goal':         g,
                'pct':          pct,
                'is_overdue':   g.is_overdue,
                'stalled_days': g.days_since_progress,
                'color_class':  color_class,
                'open_items':   g.items.filter(is_active=True, is_complete=False).count(),
            })

        # ── Habits ────────────────────────────────────────────────────────
        active_habits = Habit.objects.filter(is_active=True).order_by('order', 'name')
        habits_data = []
        logged_today_count = 0

        for h in active_habits:
            log         = h.get_log(today)
            logged      = h.is_logged_today(today)
            streak      = h.streak(today)
            week_logs   = h.logs_for_week(today)
            comp_rate   = h.completion_rate(30)

            if logged:
                logged_today_count += 1

            habits_data.append({
                'habit':      h,
                'log':        log,
                'logged':     logged,
                'streak':     streak,
                'week_logs':  week_logs,
                'comp_rate':  comp_rate,
                'display':    log.display_value() if log else '—',
            })

        # ── Reminders ─────────────────────────────────────────────────────
        due_reminders = Reminder.objects.filter(
            is_active=True, next_run__lte=now
        ).select_related('task', 'routine', 'goal', 'habit').order_by('next_run')[:5]

        upcoming_reminders = Reminder.objects.filter(
            is_active=True, next_run__gt=now
        ).order_by('next_run')[:8]

        # ── Assemble context ──────────────────────────────────────────────
        ctx.update({
            'today':                  today,
            'now':                    now,

            # Tasks
            'tasks_overdue':          tasks_overdue,
            'tasks_due_today':        tasks_due_today,
            'tasks_upcoming':         tasks_upcoming,
            'tasks_due_count':        tasks_due_today.count() + tasks_overdue.count(),
            'tasks_overdue_count':    tasks_overdue.count(),
            'tasks_todo_count':       tasks_todo_count,
            'tasks_in_progress':      tasks_in_progress,
            'task_completion_rate':   task_completion_rate,

            # Routines
            'today_routines':         today_routines,
            'routine_done':           global_done,
            'routine_total':          global_total,
            'routine_pct':            overall_routine_pct,
            'routines_today_count':   len(today_routines),

            # Goals
            'goals_data':             goals_data,
            'goals_count':            active_goals.count(),

            # Habits
            'habits_data':            habits_data,
            'habits_count':           active_habits.count(),
            'habits_logged_today':    logged_today_count,

            # Reminders
            'due_reminders':          due_reminders,
            'upcoming_reminders':     upcoming_reminders,
            'due_reminders_count':    due_reminders.count(),
        })

        return ctx
