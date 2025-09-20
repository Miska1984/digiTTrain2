# data_sharing/urls.py
from django.urls import path
from . import views

app_name = 'data_sharing'

urlpatterns = [
    path('', views.sharing_center, name='sharing_center'),
    path('toggle-permission/', views.toggle_permission, name='toggle_permission'),
    path('shared-with-me/', views.shared_data_view, name='shared_data_view'),
]