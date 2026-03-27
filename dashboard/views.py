import json
from datetime import timedelta

from django.http import JsonResponse
from django.views.generic import TemplateView
from django.utils import timezone

from tasks.models import Task
from routines.models import Routine
from habits.models import Habit
from goals.models import Goal
from reminders.models import Reminder


class HudView(TemplateView):
    """
    Primary dashboard view. All panel data is rendered server-side and
    passed to the template as both Django context variables and JSON
    script blocks (for ApexCharts). Zero loading states on first paint.

    JavaScript handles: clock, weather, ApexCharts rendering,
    and 60s periodic refresh via the JSON API endpoints.
    """

    template_name = 'dashboard/hud2.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        now   = timezone.now()

        # ── Stat cards ────────────────────────────────────────────────────
        context['tasks_due_today']   = Task.objects.filter(
            is_active=True, is_complete=False, due_date=today).count()
        context['tasks_overdue']     = Task.objects.filter(
            is_active=True, is_complete=False, due_date__lt=today).count()
        context['reminders_active']  = Reminder.objects.filter(is_active=True).count()
        context['reminders_due_now'] = Reminder.objects.filter(
            is_active=True, next_run__lte=now).count()

        thirty_ago   = today - timedelta(days=30)
        completed_30 = Task.objects.filter(
            is_complete=True, completed_at__date__gte=thirty_ago).count()
        total_active = Task.objects.filter(is_active=True).count()
        context['completion_rate'] = (
            round((completed_30 / total_active) * 100) if total_active else 0)

        # Sparkline: completions each day for last 7 days
        sparkline = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            sparkline.append(
                Task.objects.filter(is_complete=True, completed_at__date=d).count())
        context['tasks_sparkline_json'] = json.dumps(sparkline)

        # ── Routines ──────────────────────────────────────────────────────
        routines_today = []
        for r in Routine.objects.filter(is_active=True).prefetch_related('items'):
            if not r.runs_today(today):
                continue
            done, total = r.today_progress(today)
            routines_today.append({
                'id':           r.id,
                'name':         r.name,
                'slot':         r.slot,
                'slot_display': r.get_slot_display(),
                'pct':          r.completion_pct(today),
                'streak':       r.streak(today),
                'done':         done,
                'total':        total,
                'items': [
                    {'id': i.id, 'title': i.title,
                     'category': i.category, 'done': i.is_done_today(today)}
                    for i in r.items.filter(is_active=True).order_by('order')
                ],
            })

        context['routines_today']        = routines_today
        context['routines_json']         = json.dumps(routines_today)
        context['active_streaks']        = sum(1 for r in routines_today if r['streak'] > 0)
        context['max_streak']            = max((r['streak'] for r in routines_today), default=0)
        context['routines_pct_json']     = json.dumps([r['pct']  for r in routines_today])
        context['routines_labels_json']  = json.dumps([r['name'] for r in routines_today])

        # ── Habits ────────────────────────────────────────────────────────
        habits_data = []
        for h in Habit.objects.filter(is_active=True).order_by('order', 'name'):
            week_logs = h.logs_for_week(today)
            days = []
            for log in week_logs:
                if log is None:
                    days.append(None)
                elif h.metric_type == Habit.METRIC_YN:
                    days.append({'done': log.yn_value, 'value': log.display_value()})
                else:
                    days.append({
                        'done':  log.scale_value is not None,
                        'value': log.display_value()})
            habits_data.append({
                'id':           h.id,
                'name':         h.name,
                'metric_type':  h.metric_type,
                'streak':       h.streak(today),
                'rate_30':      h.completion_rate(30),
                'days':         days,
                'logged_today': h.is_logged_today(today),
            })

        context['habits_json']         = json.dumps(habits_data)
        context['habits_logged_today'] = sum(1 for h in habits_data if h['logged_today'])
        context['habits_total']        = len(habits_data)

        # ── Goals ─────────────────────────────────────────────────────────
        goals_data = []
        for g in (Goal.objects
                  .filter(is_active=True, is_complete=False)
                  .order_by('-priority', 'due_date')
                  .prefetch_related('items')[:6]):
            goals_data.append({
                'id':                  g.id,
                'name':                g.name,
                'category':            g.category,
                'priority':            g.priority,
                'pct':                 g.completion_pct(),
                'due_date':            g.due_date.strftime('%b %d') if g.due_date else None,
                'is_overdue':          g.is_overdue,
                'days_since_progress': g.days_since_progress,
                'items_total':         g.items.filter(is_active=True).count(),
                'items_done':          g.items.filter(is_active=True, is_complete=True).count(),
            })
        context['goals']      = goals_data
        context['goals_json'] = json.dumps(goals_data)

        # ── Reminders ─────────────────────────────────────────────────────
        reminders_data = []
        for r in Reminder.objects.filter(is_active=True).order_by('next_run')[:8]:
            reminders_data.append({
                'id':        r.id,
                'title':     r.title,
                'frequency': r.frequency,
                'channel':   r.channel,
                'next_run':  r.next_run.strftime('%b %d · %I:%M %p') if r.next_run else '—',
                'is_urgent': r.is_urgent,
                'is_due':    r.is_due,
            })
        context['reminders']      = reminders_data
        context['reminders_json'] = json.dumps(reminders_data)

        # ── Upcoming tasks ────────────────────────────────────────────────
        tasks_data = []
        for t in (Task.objects
                  .filter(is_active=True, is_complete=False)
                  .order_by('due_date', '-priority')[:10]):
            tasks_data.append({
                'id':             t.id,
                'name':           t.name,
                'priority':       t.priority,
                'category':       t.get_category_display() if t.category else '—',
                'energy_type':    t.energy_type,
                'due_date':       t.due_date.strftime('%b %d') if t.due_date else '—',
                'is_overdue':     t.is_overdue,
                'status':         t.status,
                'status_display': t.get_status_display(),
            })
        context['upcoming_tasks']      = tasks_data
        context['upcoming_tasks_json'] = json.dumps(tasks_data)

        context['today'] = today
        context['now']   = now
        return context


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