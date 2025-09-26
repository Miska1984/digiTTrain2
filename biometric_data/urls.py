# biometric_data/urls.py
from django.urls import path
from . import views

app_name = 'biometric_data'

urlpatterns = [
    # Napi/Reggeli Adatok
    path('morning-check/', views.morning_check, name='morning_check'), # Súly + HRV/Alvás

    # Edzéshez Kötött Napi Adatok
    path('after-training/', views.after_training, name='after_training'), # Edzés előtti/utáni súly + Intenzitás

    # Eseti/Periodikus Adatok (Testzsír, Marokerő, Futás)
    path('occasional-measurements/', views.occasional_measurements, name='occasional_measurements'), 

    # DEDIKÁLT útvonal a futóteljesítmény rögzítéséhez
    path('add-running-performance/', views.add_running_performance, name='add_running_performance'),
    
    # Adatok Listázása
    path('dashboard/', views.athlete_dashboard, name='athlete_dashboard'),
]