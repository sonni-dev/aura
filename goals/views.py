import json
from datetime import date
from typing import Any

from django.db.models.query import QuerySet
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Goal, GoalItem, CATEGORY_CHOICES, PRIORITY_CHOICES


class GoalListView(ListView):
    model = Goal
    template_name = 'goals/goal_list.html'
    context_object_name = 'goals'

    def get_queryset(self):
        return Goal.objects.filter(is_active=True).prefetch_related('items').order_by(
            'is_complete', '-priority', 'due_date'
        )
    
    def get_context_data(self, **kwargs: Any):
        ctx = super().get_context_data(**kwargs)
        today = timezone.now().date()

        all_active = ctx['goals']
        overdue = [g for g in all_active if g.is_overdue]
        in_progress = [g for g in all_active if not g.is_complete and g.items.filter(is_complete=True, is_active=True).exists()]
        stalled = [g for g in all_active if not g.is_complete and g.days_since_progress is not None and g.days_since_progress > 14]
        complete = [g for g in all_active if g.is_complete]
        inactive = Goal.objects.filter(is_active=False).prefetch_related('items').order_by('-updated_at')

        total_active = all_active.count()

        # Annotate each goal w pre-computed values for template
        goals_data = []
        for g in all_active:
            pct = g.completion_pct()
            item_total = g.items.filter(is_active=True).count()
            item_done = g.items.filter(is_active=True, is_complete=True).count()
            goals_data.append({
                'goal': g,
                'pct': pct,
                'item_total': item_total,
                'item_done': item_done,
                'is_stalled': g.days_since_progress is not None and g.days_since_progress > 14,
            })
        
        ctx.update({
            'today': today,
            'goals_data': goals_data,
            'inactive': inactive,
            'overdue_count': len(overdue),
            'in_progress_count': len(in_progress),
            'stalled_count': len(stalled),
            'complete_count': len(complete),
            'total_active': total_active,
            'category_choices': CATEGORY_CHOICES,
            'priority_choices': PRIORITY_CHOICES,
        })

        return ctx



class GoalDetailView(DetailView):
    model = Goal
    template_name = 'goals/goal_detail.html'
    context_object_name = 'goal'

    def get_context_data(self, **kwargs: Any):
        ctx = super().get_context_data(**kwargs)
        goal = self.object
        today = timezone.now().date()

        active_items = goal.items.filter(is_active=True).order_by('order', 'due_date', 'name')
        inactive_items = goal.items.filter(is_active=False).order_by('order', 'name')

        item_total = active_items.count()
        item_done = active_items.filter(is_complete=True).count()
        pct = round((item_done / item_total) * 100) if item_total else 0

        ctx.update({
            'today': today,
            'active_items': active_items,
            'inactive_items': inactive_items,
            'item_total': item_total,
            'item_done': item_done,
            'pct': pct,
            # For add/edit modal dropdowns
            'type_choices': GoalItem.TYPE_CHOICES,
            'priority_choices': PRIORITY_CHOICES,
        })
        return ctx



# ── AJAX: toggle GoalItem complete ────────────────────────────────────────

@require_POST
def goal_item_toggle(request, pk):
    item = get_object_or_404(GoalItem, pk=pk)

    if item.is_complete:
        # Un-complete: revert item
        item.is_complete = False
        item.completed_at = None
        item.save()

        # Recalculate goal's last_progress from remaining completed items
        goal = item.goal
        last = goal.items.filter(is_complete=True).order_by('-completed_at').first()
        goal.last_progress = last.completed_date.date() if last and last.completed_at else None
        goal.is_complete = False
        goal.completed_at = None
        goal.save(update_fields=['last_progress', 'is_complete', 'completed_at', 'updated_at'])
    else:
        # Handles last_progress + check_completion
        item.mark_complete()
    
    goal = item.goal
    item_done = goal.items.filter(is_active=True, is_complete=True).count()
    item_total = goal.items.filter(is_active=True).count()
    pct = round((item_done / item_total) * 100) if item_total else 0

    return JsonResponse({
        'done': item.is_complete,
        'goal_done': goal.is_complete,
        'item_done': item_done,
        'item_total': item_total,
        'pct': pct,
    })


# ── AJAX: toggle GoalItem active/inactive ────────────────────────────────

@require_POST
def goal_item_toggle_active(request, pk):
    item = get_object_or_404(GoalItem, pk=pk)
    item.is_active = not item.is_active
    item.save(update_fields=['is_active', 'updated_at'])
    return JsonResponse({
        'is_active': item.is_active,
    })


# ── AJAX: create or update a GoalItem ────────────────────────────────────

@require_POST
def goal_item_save(request, goal_pk):
    goal = get_object_or_404(Goal, pk=goal_pk)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    name = data.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Name is required'}, status=400)
    
    item_id = data.get('item_id') or None
    item = get_object_or_404(GoalItem, pk=item_id, goal=goal) if item_id else GoalItem(goal=goal)

    item.name = name
    item.description = data.get('description', '').strip()
    item.item_type = data.get('item_type', GoalItem.TYPE_TASK)
    item.priority = data.get('priority', '')
    item.order = int(data.get('order', 0) or 0)

    due_raw = data.get('due_date', '').strip()
    if due_raw:
        try:
            item.due_date = date.fromisoformat(due_raw)
        except ValueError:
            return JsonResponse({'error': 'Invalid due date (use YYYY-MM-DD).'}, status=400)
    else:
        item.due_date = None
    
    item.save()
    return JsonResponse({
        'ok': True,
        'item_id': item.pk,
    })
