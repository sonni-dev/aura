import json
from datetime import date
from typing import Any

from django.views.generic import ListView
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Task


class TaskListView(ListView):
    model = Task
    template_name = "tasks/task_list.html"
    context_object_name = 'tasks'

    def get_queryset(self):
        return Task.objects.filter(is_active=True).order_by(
            'is_complete', 'due_date', '-priority'
        )
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.now().date()

        all_active = ctx['tasks']

        overdue = [t for t in all_active if t.is_overdue]
        due_today = [t for t in all_active if not t.is_complete and t.due_date == today]
        in_progress = [t for t in all_active if t.status == Task.STATUS_IN_PROGRESS]
        stalled = [t for t in all_active if t.status == Task.STATUS_STALLED]
        complete = [t for t in all_active if t.is_complete]
        inactive = Task.objects.filter(is_active=False).order_by('-updated_at')

        total_active = all_active.count()
        completion_pct = round((len(complete) / total_active) * 100) if total_active else 0

        ctx.update({
            'today': today,
            'overdue_count': len(overdue),
            'due_today_count': len(due_today),
            'in_progress_count': len(in_progress),
            'stalled_count': len(stalled),
            'complete_count': len(complete),
            'total_active': total_active,
            'completion_pct': completion_pct,
            'inactive': inactive,
            # Modal Dropdowns
            'status_choices': Task.STATUS_CHOICES,
            'priority_choices': Task.PRIORITY_CHOICES,
            'category_choices': Task.CATEGORY_CHOICES,
            'energy_choices': Task.ENERGY_CHOICES,
            'where_choices': Task.WHERE_CHOICES,
        })
        return ctx


# ── AJAX: toggle complete ─────────────────────────────────────────────────

@require_POST
def task_toggle_complete(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if task.is_complete:
        task.is_complete = False
        task.status = Task.STATUS_TODO
        task.completed_at = None
        task.save()
    else:
        task.mark_complete()
    return JsonResponse({'is_complete': task.is_complete, 'status': task.status})


# ── AJAX: create or update a task ────────────────────────────────────────

@require_POST
def task_save(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    name = data.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Name is required'}, status=400)
    
    task_id = data.get('task_id') or None
    task = get_object_or_404(Task, pk=task_id) if task_id else Task()

    task.name = name
    task.description = data.get('description', '').strip()
    task.status = data.get('status', Task.STATUS_TODO)
    task.priority = data.get('priority', Task.PRIORITY_MEDIUM)
    task.category = data.get('category', '')
    task.energy_type = data.get('energy_type', '')
    task.where_task = data.get('where_task', '')

    due_raw = data.get('due_date', '').strip()
    if due_raw:
        try:
            task.due_date = date.fromisoformat(due_raw)
        except ValueError:
            return JsonResponse({'error': 'Invalid due date format (use YYYY-MM-DD).'}, status=400)
    else:
        task.due_date = None
    
    # Sync is_complete with status choice
    if task.status == Task.STATUS_COMPLETE and not task.is_complete:
        task.mark_complete()  # Stamps completed_at and saves
    else:
        task.save()

    return JsonResponse({'ok': True, 'task_id': task.pk})
