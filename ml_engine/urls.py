# ml_engine/urls.py
from django.urls import path
from . import views

app_name = 'ml_engine'


urlpatterns = [
    path('form-prediction/', views.form_prediction_view, name='form_prediction'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('api/ditta-chat/', views.ditta_chat_api, name='ditta_chat_api'),

]