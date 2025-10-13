from django.urls import path
from . import views

urlpatterns = [
    # Credit és előfizetés áttekintése
    path('dashboard/', views.billing_dashboard, name='billing_dashboard'),
    
    # Credit vásárlás és számla igénylés
    path('topup/', views.top_up_view, name='billing_top_up'),
    
    # Hirdetésnézés Creditért
    path('ad-for-credit/', views.ad_credit_earn_view, name='ad_credit_earn'),
    
    # Hirdetésmentes előfizetés aktiválása/megújítása
    path('toggle-ad-free/', views.toggle_ad_free, name='toggle_ad_free'),

    # Algoritmus futtatás (ez egy API végpont lesz)
    path('run-algorithm/<str:algorithm_name>/', views.run_algorithm, name='run_algorithm'),
]