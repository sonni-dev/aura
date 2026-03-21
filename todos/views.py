from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from .models import Todo


@require_POST
def toggle_complete(request, pk):
    """Toggle a todo's completed state. Called from the display via fetch()."""
    todo = get_object_or_404(Todo, pk=pk)
    if todo.completed:
        todo.completed = False
        todo.completed_at = None
        todo.save()
    else:
        todo.mark_complete()
    return JsonResponse({'completed': todo.completed, 'id': todo.pk})