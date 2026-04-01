from typing import Any

from django.db.models.query import QuerySet
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict
import json
 
from .models import Routine, RoutineItem, RoutineCompletion, CATEGORY_CHOICES


# Ordered day abbreviations used for the schedule pill display
DAY_ABBR = [
    ('mon', 'Mo'), ('tue', 'Tu'), ('wed', 'We'), ('thu', 'Th'),
    ('fri', 'Fr'), ('sat', 'Sa'), ('sun', 'Su'),
]


class RoutineListView(ListView):
    model = Routine
    template_name = "routines/routine_list.html"
    context_object_name = "routines"

    def get_queryset(self):
        return Routine.objects.prefetch_related('items').order_by('slot', 'order', 'name')
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        routines_data = []
        for r in ctx['routines']:
            done, total = r.today_progress()
            routines_data.append({
                'routine': r,
                'done': done,
                'total': total,
                'pct': round((done / total) * 100) if total else 0,
                'streak': r.streak(),
                'item_count': r.items.filter(is_active=True).count(),
                'runs_today': r.runs_today(),
            })

        ctx['routines_data'] = routines_data


        # Summary stats for the header bar
        active_list = [r for r in ctx['routines'] if r.is_active]
        today_list = [rd for rd in routines_data if rd['runs_today']]
        total_done = sum(rd['done'] for rd in today_list)
        total_items = sum(rd['total'] for rd in today_list)

        ctx.update({
            'total_count': ctx['routines'].count(),
            'active_count': len(active_list),
            'today_count': len(today_list),
            'today_overall_done': total_done,
            'today_overall_total': total_items,
            'max_streak': max((rd['streak'] for rd in routines_data), default=0),
        })

        return ctx


class RoutineDetailView(DetailView):
    model = Routine
    template_name = 'routines/routine_detail.html'
    context_object_name = 'routine'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        routine = self.object 
        today = timezone.now().date()

        # Active items annotated with today completion + individual streak
        active_items = list(routine.items.filter(is_active=True))
        items_data = [
            {
                'item': item,
                'done_today': item.is_done_today(),
                'streak': item.item_streak(),
            }
            for item in active_items
        ]

        done, total = routine.today_progress()

        ctx.update({
            'items_data': items_data,
            'inactive_items': routine.items.filter(is_active=False),
            'today_done': done,
            'today_total': total,
            'today_pct': round((done / total) * 100) if total else 0,
            'streak': routine.streak(),
            'today': today,
            'category_choices': CATEGORY_CHOICES,
            'day_abbr': DAY_ABBR,
            'routine_days': routine.get_days_list(),
        })

        # ── Completion history — up to 30 most-recent scheduled days ─────
        start = today - timedelta(days=89)
        completions = RoutineCompletion.objects.filter(
            item__routine=routine,
            completed_on__gte=start,
        ).select_related('item').order_by('-completed_on')

        by_date: dict = defaultdict(list)
        for c in completions:
            by_date[c.completed_on].append(c)
        

        history = []
        for i in range(90):
            d = today - timedelta(days=i)
            if routine.runs_today(d):
                day_done = len(by_date.get(d, []))
                history.append({
                    'date': d,
                    'done': day_done,
                    'total': total,
                    'pct': round((day_done / total) * 100) if total else 0,
                    'is_today': d == today,
                })
            if len(history) >= 30:
                break
        
        ctx['history'] = history


        # ── 35-cell heatmap grid (5 weeks × 7 days, oldest → newest) ────
        grid_days = []
        for i in range(34, -1, -1):
            d = today - timedelta(days=i)
            day_done = len(by_date.get(d, []))
            scheduled = routine.runs_today(d)
            grid_days.append({
                'date': d,
                'pct': round((day_done / total) * 100) if (scheduled and total) else None,
                'scheduled': scheduled,
                'is_today': d == today,
            })
        
        ctx['grid_days'] = grid_days

        return ctx


# ── AJAX Endpoints ────────────────────────────────────────────────────────

@require_POST
def routine_item_toggle(request, pk):
    """Toggle a RoutineItem's completion for today and return updated progress."""
    item = get_object_or_404(RoutineItem, pk=pk)
    new_state = item.toggle_today()
    done, total = item.routine.today_progress()
    return JsonResponse({
        'done': new_state,
        'routine_done': done,
        'routine_total': total,
        'routine_pct': round((done / total) * 100) if total else 0,
    })


@require_POST
def routine_item_save(request, routine_pk):
    """Create or update a RoutineItem. Include item_id in body to update."""
    routine = get_object_or_404(Routine, pk=routine_pk)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    title = data.get('title', '').strip()
    if not title:
        return JsonResponse({'error': 'Title is required.'}, status=400)
    
    category = data.get('category', '')
    order = int(data.get('order', 0))
    item_id = data.get('item_id')

    if item_id:
        item = get_object_or_404(RoutineItem, pk=item_id, routine=routine)
        item.title = title
        item.category = category
        item.order = order
        item.save()
        action = 'updated'
    else:
        item = RoutineItem.objects.create(
            routine=routine, title=title, category=category, order=order,
        )
        action = 'created'
    
    return JsonResponse({
        'action': action,
        'item_id': item.pk,
        'title': item.title,
        'category': item.category,
        'category_display': item.get_category_display(),
        'order': item.order,
        'is_active': item.is_active,
    })


@require_POST
def routine_item_toggle_active(request, pk):
    """Toggle a RoutineItem's is_active status (archive / restore)."""
    item = get_object_or_404(RoutineItem, pk=pk)
    item.is_active = not item.is_active
    item.save()
    return JsonResponse({
        'is_active': item.is_active,
        'item_id': item.pk,
    })
