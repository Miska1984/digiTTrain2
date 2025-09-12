# digiTTrain/users/urls.py
from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from .debug_views import debug_gcs_upload
from .debug_views import debug_gcs_upload, debug_settings 

app_name = 'users'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='core:hello_world'), name='logout'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    # path('profile/', views.profile, name='profile'), # Ezt is hamarosan elkészítjük
    
    # Jelszómódosító URL-ek
    path('password_change/', auth_views.PasswordChangeView.as_view(template_name='users/password_change.html'), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='users/password_change_done.html'), name='password_change_done'),
    
    # AJAX URL-ek a dinamikus űrlapokhoz és a műveletekhez
    path('role/new/', views.new_role_view, name='new_role'),
    path('get-next-step-form/<int:role_id>/', views.get_next_step_form, name='get_next_step_form'),
    path('club/create-ajax/', views.club_create_ajax_view, name='club_create_ajax'),
    path('club/join-ajax/', views.club_join_ajax_view, name='club_join_ajax'),
    
    # DEBUG URL-ek
    path('debug/gcs-upload/', debug_gcs_upload, name='debug_gcs_upload'),
    path('debug/settings/', debug_settings, name='debug_settings'),
]