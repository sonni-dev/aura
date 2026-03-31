from django.urls import path
from . import views
 
app_name = 'routines'
 
urlpatterns = [
    # ── Pages ─────────────────────────────────────────────────────────────
    path('',          views.RoutineListView.as_view(),   name='list'),
    path('<int:pk>/', views.RoutineDetailView.as_view(), name='detail'),
 
    # ── AJAX ──────────────────────────────────────────────────────────────
    path('item/<int:pk>/toggle/',        views.routine_item_toggle,        name='item_toggle'),
    path('item/<int:pk>/toggle-active/', views.routine_item_toggle_active, name='item_toggle_active'),
    path('<int:routine_pk>/item/save/',  views.routine_item_save,          name='item_save'),
]