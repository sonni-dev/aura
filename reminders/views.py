from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from .models import Reminder


@require_POST
def dismiss(request, pk):
    """Deactivate a one-time reminder from the display."""
    reminder = get_object_or_404(Reminder, pk=pk)
    if reminder.recurrence == Reminder.RECURRENCE_NONE:
        reminder.active = False
        reminder.save()
    return JsonResponse({'active': reminder.active, 'id': reminder.pk})
