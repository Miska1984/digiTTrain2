# digiTTrain/users/urls.py
from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

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
]