from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from .models import Reminder


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
