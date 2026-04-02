import json
from datetime import date, timedelta
from typing import Any

from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.utils import timezone
 
from .models import Habit, HabitLog, CATEGORY_CHOICES, FREQ_CHOICES


class HabitListView(ListView):
    model = Habit
    template_name = 'habits/habit_list.html'
    context_object_name = 'habits'

    def get_queryset(self):
        return Habit.objects.filter(is_active=True).order_by('order', 'name')
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        today = date.today()
        context['day_abbrs'] = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']

        habits_data = []
        logged_today = 0
        total_streak = 0

        for h in context['habits']:
            log = h.get_log(today)
            is_logged = h.is_logged_today(today)
            streak = h.streak(today)
            week_logs = h.logs_for_week(today)
            comp_rate = h.completion_rate(30)

            if is_logged:
                logged_today += 1
            total_streak += streak

            # Build the 7 cell week-dot data
            week_start = today - timedelta(days=today.weekday())
            week_cells = []
            for i, wl in enumerate(week_logs):
                day = week_start + timedelta(days=i)
                if wl is None:
                    state = 'empty'
                elif h.metric_type == Habit.METRIC_YN:
                    state = 'yes' if wl.yn_value else 'no'
                else:
                    state = 'scale'
                
                week_cells.append({
                    'day': day,
                    'wl': wl,
                    'state': state,
                    'value': wl.scale_value if wl and h.metric_type == Habit.METRIC_SCALE else None,
                })
        
            habits_data.append({
                'habit': h,
                'log': log,
                'is_logged': is_logged,
                'streak': streak,
                'week_cells': week_cells,
                'comp_rate': comp_rate,
                'display': log.display_value() if log else '—',
            })
        
        inactive = Habit.objects.filter(is_active=False).order_by('order', 'name')

        context.update({
            'today': today,
            'habits_data': habits_data,
            'inactive': inactive,
            'total_count': context['habits'].count(),
            'logged_today': logged_today,
            'total_streak': total_streak,
            'category_choices': CATEGORY_CHOICES,
        })
        return context



class HabitDetailView(DetailView):
    model = Habit
    template_name = 'habits/habit_detail.html'
    context_object_name = 'habit'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        habit = self.object 
        today = date.today()
        ctx['day_abbrs'] = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']

        # ── 91-day heatmap (13 weeks × 7 days, oldest → newest) ──────────
        start = today - timedelta(days=90)
        logs = {
            log.logged_on: log
            for log in HabitLog.objects.filter(habit=habit, logged_on__gte=start)
        }

        # Pad so the grid always starts on a Monday
        grid_start = start - timedelta(days=start.weekday())    # previous Mon
        total_cells = ((today - grid_start).days + 1)
        
        # Round up to full weeks
        total_cells = ((total_cells + 6) // 7) * 7

        grid_days = []
        for i in range(total_cells):
            d = grid_start + timedelta(days=i)
            log = logs.get(d)
            in_range = d >= start

            if not in_range:
                # Padding cell before range - render blank
                cell_type = 'pad'
            elif log is None:
                cell_type = 'empty'
            elif habit.metric_type == Habit.METRIC_YN:
                cell_type = 'yes' if log.yn_value else 'no'
            else:
                cell_type = 'scale'
            
            grid_days.append({
                'date': d,
                'log': log,
                'cell_type': cell_type,
                'is_today': d == today,
                'in_range': in_range,
                'scale_value': log.scale_value if log else None,
                # Opacity for scale cells (0.15 → 0.90)
                'scale_opacity': round(0.15 + (log.scale_value / 10) * 0.75, 2) if log and log.scale_value else 0.15,
            })
        
        # ── Recent log history (last 14 days with a log) ──────────────────

        recent_logs = HabitLog.objects.filter(
            habit=habit, logged_on__gte=today - timedelta(days=30)
        ).order_by('-logged_on')[:14]

        ctx.update({
            'today': today,
            'grid_days': grid_days,
            'grid_weeks': total_cells // 7,
            'recent_logs': recent_logs,
            'streak': habit.streak(today),
            'comp_rate_30': habit.completion_rate(30),
            'comp_rate_7': habit.completion_rate(7),
            'is_logged': habit.is_logged_today(today),
            'today_log': habit.get_log(today),
        })
        return ctx


# ── AJAX: log / toggle today ──────────────────────────────────────────────
 
@require_POST
def habit_log_today(request, pk):
    """
    For yn habits:    toggle yes/no. If already logged yes, un-log it.
    For scale habits: expects { value: int } in JSON body.
    """
    habit = get_object_or_404(Habit, pk=pk)
    today = date.today()

    if habit.metric_type == Habit.METRIC_YN:
        existing = habit.get_log(today)
        if existing and existing.yn_value is True:
            # Already logged yes - toggle off (delete)
            existing.delete()
            return JsonResponse({
                'logged': False,
                'display': '—',
                'streak': habit.streak(today)
            })
        else:
            log = habit.log_today(yn_value=True)
            return JsonResponse({
                'logged': True, 
                'display': 'yes',
                'streak': habit.streak(today)
            })
    else:
        # Scale habit - value required
        try:
            data = json.loads(request.body)
            value = int(data.get('value', 0))
            if not (1 <= value <= 10):
                raise ValueError
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Value must be between 1-10.'}, status=400)
        
        log = habit.log_today(scale_value=value)
        return JsonResponse({
            'logged': True,
            'display': str(value),
            'streak': habit.streak(today)
        })
