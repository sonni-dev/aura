from django.urls import path
from . import views

app_name = 'voice_api'

urlpatterns = [
    path('reminders/', views.create_reminder, name='create_reminder'),
    path('reminders/due/', views.due_reminders, name='due_reminders'),
    path('reminders/<int:pk>/dismiss/', views.dismiss_reminder, name='dismiss_reminder'),
    path('reminders/<int:pk>/advance/', views.advance_reminder, name='advance_reminder'),

    path('lists/<str:list_name>/items/', views.list_items, name='list_items'),
    path('lists/items/<int:pk>/complete/', views.complete_list_item, name='complete_list_item'),
    path('lists/items/<int:pk>/delete/', views.delete_list_item, name='delete_list_item'),
]