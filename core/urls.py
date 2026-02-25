# core/urls.py
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.hello_world, name='hello_world'),

    path('contact/', views.contact_view, name='contact'),
    path('privacy-policy/', views.privacy_policy_view, name='privacy_policy'),
    path('funkciok/', views.features_view, name='features'),
    path('tudastar/', views.knowledge_base_view, name='knowledge_base'),


    path('main_page/', views.main_page, name='main_page'),
    path('imprint-terms/', views.imprint_terms_view, name='imprint_terms'),
]