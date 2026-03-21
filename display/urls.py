from django.urls import path
from . import views

app_name = 'display'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('data/', views.dashboard_data, name='data'),
]
