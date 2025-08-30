# core/urls.py
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.hello_world, name='hello_world'),
    path('main_page/', views.main_page, name='main_page'),
]