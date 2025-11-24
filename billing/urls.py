# billing/urls.py
from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    # ==============================================================================
    # 1. VEZÉRLŐPULT (Dashboard)
    # ==============================================================================
    path('dashboard/', views.billing_dashboard_view, name='billing_dashboard'),
    
    # ==============================================================================
    # 2. VÁSÁRLÁS (Előfizetés / Elemzési csomag)
    # ==============================================================================
    path('purchase/', views.purchase_view, name='billing_purchase'),
    
    # ==============================================================================
    # 3. HIRDETÉSNÉZÉS (Ingyenes elemzésért)
    # ==============================================================================
    path('ad-for-credit/', views.ad_for_credit_view, name='ad_credit_earn'),
    
    # ==============================================================================
    # 4. HIRDETÉSMENTESSÉG KI/BE KAPCSOLÁSA
    # ==============================================================================
    path('toggle-ad-free/', views.toggle_ad_free_view, name='billing_toggle_ad_free'),
    
    # ==============================================================================
    # 5. RÉGI URL-EK (Visszafelé kompatibilitás miatt)
    # ==============================================================================
    # Ezek átirányítanak az új URL-ekre
    # path('top-up-invoice/', views.top_up_invoice_request_view, name='billing_top_up'),
    path('toggle-ad-free-old/', views.toggle_ad_free_view, name='toggle_ad_free'),
]