from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone

from todos.models import Todo
from reminders.models import Reminder


def dashboard(request):
    """Main projection wall view."""
    now = timezone.now()

    todos = Todo.objects.filter(completed=False).order_by('due_date', '-priority')

    reminders = Reminder.objects.filter(
        active=True,
        remind_at__gte=now
    ).order_by('remind_at')[:6]

    # Flag reminders due within 15 minutes for visual urgency
    for r in reminders:
        r.urgent = r.is_due_now

    context = {
        'todos': todos,
        'reminders': reminders,
        'now': now,
        'today': now.date(),
    }
    return render(request, 'display/dashboard.html', context)


def dashboard_data(request):
    """
    JSON endpoint polled by the display every 60s to refresh data
    without a full page reload.
    """
    now = timezone.now()

    todos_qs = Todo.objects.filter(completed=False).order_by('due_date', '-priority')
    reminders_qs = Reminder.objects.filter(
        active=True, remind_at__gte=now
    ).order_by('remind_at')[:6]

    todos = [
        {
            'id': t.pk,
            'title': t.title,
            'priority': t.priority,
            'due_date': t.due_date.isoformat() if t.due_date else None,
            'is_overdue': t.is_overdue,
        }
        for t in todos_qs
    ]

    reminders = [
        {
            'id': r.pk,
            'title': r.title,
            'description': r.description,
            'remind_at': r.remind_at.isoformat(),
            'recurrence': r.recurrence,
            'urgent': r.is_due_now,
        }
        for r in reminders_qs
    ]

    return JsonResponse({'todos': todos, 'reminders': reminders})
