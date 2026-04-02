from django.urls import path
from . import views
 
app_name = 'habits'
 
urlpatterns = [
    # ── Pages ─────────────────────────────────────────────────────────────
    path('',          views.HabitListView.as_view(),   name='list'),
    path('<int:pk>/', views.HabitDetailView.as_view(), name='detail'),
 
    # ── AJAX ──────────────────────────────────────────────────────────────
    path('<int:pk>/log/', views.habit_log_today, name='log_today'),
]