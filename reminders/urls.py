from django.urls import path
from . import views

app_name = 'reminders'

urlpatterns = [
    path('<int:pk>/dismiss/', views.dismiss, name='dismiss'),
]
