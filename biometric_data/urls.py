# biometric_data/urls.py

from django.urls import path
from . import views

app_name = 'biometric_data'

urlpatterns = [
    path('add/', views.add_weight, name='add_weight'),
    path('list/', views.list_weight, name='list_weight'),

    path('add-hrv-sleep/', views.add_hrv_and_sleep, name='add_hrv_and_sleep'),
    path('add-workout-feedback/', views.add_workout_feedback, name='add_workout_feedback'),
    path('add-running-performance/', views.add_running_performance, name='add_running_performance'),
]