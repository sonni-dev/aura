from django.urls import path
from . import views
 
app_name = 'goals'
 
urlpatterns = [
    # ── Pages ─────────────────────────────────────────────────────────────
    path('',          views.GoalListView.as_view(),   name='list'),
    path('<int:pk>/', views.GoalDetailView.as_view(), name='detail'),
 
    # ── AJAX ──────────────────────────────────────────────────────────────
    path('item/<int:pk>/toggle/',        views.goal_item_toggle,        name='item_toggle'),
    path('item/<int:pk>/toggle-active/', views.goal_item_toggle_active, name='item_toggle_active'),
    path('<int:goal_pk>/item/save/',     views.goal_item_save,          name='item_save'),
]
