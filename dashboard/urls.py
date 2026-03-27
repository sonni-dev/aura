from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Main HUD view
    path('', views.HudView.as_view(), name='hud'),
 
    # JSON API endpoints — consumed by the HUD template via fetch()
    path('api/stats/',                views.stats_api,              name='api-stats'),
    path('api/routines/today/',       views.routines_today_api,     name='api-routines-today'),
    path('api/habits/week/',          views.habits_week_api,        name='api-habits-week'),
    path('api/goals/',                views.goals_api,              name='api-goals'),
    path('api/reminders/upcoming/',   views.reminders_upcoming_api, name='api-reminders-upcoming'),
    path('api/tasks/upcoming/',       views.tasks_upcoming_api,     name='api-tasks-upcoming'),
    path('api/calendar/events/',      views.calendar_events_api,    name='api-calendar-events'),
]