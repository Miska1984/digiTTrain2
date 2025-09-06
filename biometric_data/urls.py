# biometric_data/urls.py

from django.urls import path
from . import views

app_name = 'biometric_data'

urlpatterns = [
    path('add/', views.add_weight, name='add_weight'),
    path('list/', views.list_weight, name='list_weight'),
]