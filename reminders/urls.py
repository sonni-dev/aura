from django.urls import path
from . import views

app_name = 'reminders'

urlpatterns = [
    # ── Pages ─────────────────────────────────────────────────────────────
    path('', views.ReminderListView.as_view(), name='list'),
 
    # ── AJAX ──────────────────────────────────────────────────────────────
    path('<int:pk>/dismiss/', views.dismiss,         name='dismiss'),
    path('<int:pk>/advance/', views.advance,         name='advance'),
    path('<int:pk>/snooze/',  views.snooze,          name='snooze'),
    path('save/',             views.reminder_save,   name='save'),
]