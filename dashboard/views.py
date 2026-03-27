from django.views.generic import TemplateView
from django.utils import timezone
from django.http import JsonResponse
from datetime import timedelta

from tasks.models import Task
from routines.models import Routine, RoutineCompletion, RoutineItem, WEEKDAY_MAP
from goals.models import Goal
from habits.models import Habit, HabitLog
from reminders.models import Reminder


class HudView(TemplateView):
    template_name = 'dashboard/hud.html'

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


# ── JSON API endpoints ────────────────────────────────────────────────────────

def stats_api(request):
    today = timezone.now().date()
    now   = timezone.now()
    from datetime import timedelta
    thirty_ago   = today - timedelta(days=30)
    completed_30 = Task.objects.filter(is_complete=True, completed_at__date__gte=thirty_ago).count()
    total_active = Task.objects.filter(is_active=True).count()
    routines_today = [r for r in Routine.objects.filter(is_active=True) if r.runs_today()]
    return JsonResponse({
        'tasks_due_today':  Task.objects.filter(is_active=True, is_complete=False, due_date=today).count(),
        'tasks_overdue':    Task.objects.filter(is_active=True, is_complete=False, due_date__lt=today).count(),
        'active_reminders': Reminder.objects.filter(is_active=True).count(),
        'completion_rate':  round((completed_30/total_active)*100) if total_active else 0,
        'active_streaks':   sum(1 for r in routines_today if r.streak() > 0),
    })


def routines_today_api(request):
    today = timezone.now().date()
    data  = []
    for r in Routine.objects.filter(is_active=True).prefetch_related('items'):
        if not r.runs_today(today):
            continue
        done, total = r.today_progress(today)
        data.append({
            'id': r.id, 'name': r.name, 'slot': r.slot,
            'done': done, 'total': total,
            'pct': r.completion_pct(today), 'streak': r.streak(today),
            'items': [{'id': i.id, 'title': i.title, 'done': i.is_done_today(today)}
                      for i in r.items.filter(is_active=True).order_by('order')],
        })
    return JsonResponse({'routines': data})


def habits_week_api(request):
    data = []
    for h in Habit.objects.filter(is_active=True).order_by('order', 'name'):
        week_logs = h.logs_for_week()
        days = []
        for log in week_logs:
            if log is None:
                days.append(None)
            elif h.metric_type == Habit.METRIC_YN:
                days.append({'done': log.yn_value, 'value': log.display_value()})
            else:
                days.append({'done': log.scale_value is not None, 'value': log.display_value()})
        data.append({
            'id': h.id, 'name': h.name, 'metric_type': h.metric_type,
            'streak': h.streak(), 'rate_30': h.completion_rate(30),
            'days': days, 'logged_today': h.is_logged_today(),
        })
    return JsonResponse({'habits': data})


def goals_api(request):
    data = []
    for g in Goal.objects.filter(is_active=True, is_complete=False).order_by('-priority', 'due_date').prefetch_related('items'):
        data.append({
            'id': g.id, 'name': g.name, 'category': g.category, 'priority': g.priority,
            'pct': g.completion_pct(),
            'due_date': g.due_date.isoformat() if g.due_date else None,
            'is_overdue': g.is_overdue, 'days_since_progress': g.days_since_progress,
            'items_total': g.items.filter(is_active=True).count(),
            'items_done':  g.items.filter(is_active=True, is_complete=True).count(),
        })
    return JsonResponse({'goals': data})


def reminders_upcoming_api(request):
    limit = int(request.GET.get('limit', 8))
    data  = []
    for r in Reminder.objects.filter(is_active=True).order_by('next_run')[:limit]:
        src = r.source
        data.append({
            'id': r.id, 'title': r.title, 'frequency': r.frequency, 'channel': r.channel,
            'next_run': r.next_run.isoformat() if r.next_run else None,
            'is_urgent': r.is_urgent, 'is_due': r.is_due,
            'source_label': getattr(src, 'name', None) or getattr(src, 'title', None) if src else None,
        })
    return JsonResponse({'reminders': data})


def tasks_upcoming_api(request):
    limit = int(request.GET.get('limit', 10))
    data  = []
    for t in Task.objects.filter(is_active=True, is_complete=False).order_by('due_date', '-priority')[:limit]:
        data.append({
            'id': t.id, 'name': t.name, 'priority': t.priority, 'category': t.category,
            'energy_type': t.energy_type, 'where_task': t.where_task,
            'due_date': t.due_date.isoformat() if t.due_date else None,
            'is_overdue': t.is_overdue, 'status': t.status,
        })
    return JsonResponse({'tasks': data})


def calendar_events_api(request):
    start = request.GET.get('start')
    end   = request.GET.get('end')
    qs    = Reminder.objects.filter(is_active=True)
    if start:
        qs = qs.filter(next_run__gte=start)
    if end:
        qs = qs.filter(next_run__lte=end)
    COLOR_MAP = {
        Reminder.FREQ_DAILY:   '#1bc5bd',
        Reminder.FREQ_WEEKLY:  '#6f42c1',
        Reminder.FREQ_MONTHLY: '#ffa800',
        Reminder.FREQ_ONCE:    '#00cfde',
        Reminder.FREQ_CUSTOM:  '#b8ff47',
    }
    return JsonResponse([{
        'id': r.id, 'title': r.title, 'start': r.next_run.isoformat(),
        'color': COLOR_MAP.get(r.frequency, '#888'),
        'extendedProps': {'frequency': r.frequency, 'description': r.description},
    } for r in qs], safe=False)
