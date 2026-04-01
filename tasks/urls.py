from django.urls import path
from . import views
 
app_name = 'tasks'
 
urlpatterns = [
    # ── Pages ─────────────────────────────────────────────────────────────
    path('', views.TaskListView.as_view(), name='list'),
 
    # ── AJAX ──────────────────────────────────────────────────────────────
    path('<int:pk>/toggle/',  views.task_toggle_complete, name='toggle'),
    path('save/',             views.task_save,            name='save'),
]