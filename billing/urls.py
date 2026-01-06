# billing/urls.py
from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    # ======================================================================
    # 1. VEZÉRLŐPULT (Dashboard)
    # ======================================================================
    # Itt látja a felhasználó az elemzési egyenlegét és a kreditjeit
    path('dashboard/', views.billing_dashboard_view, name='billing_dashboard'),

    # ======================================================================
    # 2. VÁSÁRLÁS ÉS BEVÁLTÁS (Hibrid nézet)
    # ======================================================================
    # Ez az oldal kezeli a pénzes igénylést és a kredites beváltást is
    path('purchase/', views.purchase_view, name='billing_purchase'),

    # ======================================================================
    # 3. KREDIT GYŰJTÉS (Hirdetésnézés)
    # ======================================================================
    # Itt lehet hirdetéseket nézni, amiért krediteket kap a user
    path('ad-for-credit/', views.ad_for_credit_view, name='ad_credit_earn'),

    # ======================================================================
    # 4. HIRDETÉSMENTESSÉG KEZELÉSE
    # ======================================================================
    # Ha van aktív előfizetése, itt kapcsolhatja ki-be (opcionális)
    path('toggle-ad-free/', views.toggle_ad_free_view, name='billing_toggle_ad_free'),

    # ======================================================================
    # 5. AJAX / API VÉGPONTOK (A dinamikus felülethez)
    # ======================================================================
    # Ezt hívja meg a purchase.html-ben lévő JavaScript, 
    # hogy betöltse a csomagokat (AD_FREE, ML, ANALYSIS)
    path('api/plans/', views.get_plans_ajax, name='get_plans_ajax'),

]