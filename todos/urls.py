from django.urls import path
from . import views

app_name = 'todos'

urlpatterns = [
    path('<int:pk>/toggle/', views.toggle_complete, name='toggle'),
]
