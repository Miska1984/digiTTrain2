# users/urls.py
from django.urls import path
from . import views
from . import role_views
from .forms import CustomPasswordResetForm, CustomLoginForm
from users.views import register, edit_profile
from users.role_views import club_leader, all_roles, coach, parent, athlete
from users.role_views.base import pending_roles, approve_role, reject_role, cancel_role
from django.contrib.auth import views as auth_views
from .debug_views import debug_gcs_upload
from .debug_views import debug_gcs_upload, debug_settings 

app_name = 'users'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(
        template_name='users/login.html',
        authentication_form=CustomLoginForm 
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='core:hello_world'), name='logout'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    
    # Jelszómódosító URL-ek
    path('password_change/', auth_views.PasswordChangeView.as_view(template_name='users/password_change.html'), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='users/password_change_done.html'), name='password_change_done'),
    
    # Jelszó-visszaállítás URL-ek (elfelejtett jelszóhoz)
    path('reset_password/', 
        auth_views.PasswordResetView.as_view(
            template_name="users/password_reset.html", 
            email_template_name='users/password_reset_email.html', 
            subject_template_name='users/password_reset_subject.txt',
            form_class=CustomPasswordResetForm,
            success_url='/users/reset_password_sent/'
        ),
        name="password_reset"),
    path('reset_password_sent/', 
        auth_views.PasswordResetDoneView.as_view(template_name="users/password_reset_sent.html"),
        name="password_reset_done"),
    path('reset/<uidb64>/<token>/', 
        auth_views.PasswordResetConfirmView.as_view(template_name="users/password_reset_form.html"),
        name="password_reset_confirm"),
    path('reset_password_complete/', 
        auth_views.PasswordResetCompleteView.as_view(template_name="users/password_reset_done.html"),
        name="password_reset_complete"),

    path('roles/', views.role_dashboard, name='role_dashboard'),

    # Jóváhagyási folyamat
    path("roles/pending/", pending_roles, name="pending_roles"),
    path("roles/<int:role_id>/approve/", approve_role, name="approve_role"),
    path("roles/<int:role_id>/reject/", reject_role, name="reject_role"),
    path('roles/cancel/<int:role_id>/', cancel_role, name='cancel_role'),

    # Egyesületi vezető
    path("roles/club_leader/create/", club_leader.create_club_and_leader_role, name="create_club_leader"),
    path("roles/club_leader/<int:role_id>/edit/", club_leader.edit_club_leader_role, name="edit_club_leader_role"),
    path("roles/<int:role_id>/edit/", all_roles.edit_user_role, name="edit_user_role"),
    
    # Edző
    path("roles/coach/create/", coach.create_coach, name="create_coach_role"),  
    path("roles/coach/<int:role_id>/edit/", role_views.edit_coach_role, name="edit_coach_role"),
    path("roles/coach/get-sports/<int:club_id>/", coach.get_sports_for_club, name="get_sports_for_club"),

    # Szülő
    path("roles/parent/create/", parent.create_parent, name="create_parent"),
    path("roles/parent/<int:role_id>/edit/", parent.edit_parent, name="edit_parent"),
    path("roles/parent/get_sports_by_club/", parent.get_sports_by_club, name="get_sports_by_club"),
    path("roles/parent/get_coaches_by_club_and_sport/", parent.get_coaches_by_club_and_sport, name="get_coaches_by_club_and_sport"),

    # Sportoló
    path("roles/athlete/create/", athlete.create_athlete, name="create_athlete"),
    path("roles/athlete/<int:role_id>/edit/", athlete.edit_athlete, name="edit_athlete"),
    path("ajax/get-sports-by-club/", athlete.get_sports_by_club, name="get_sports_by_club"),
    path("ajax/get-coaches-by-club-and-sport/", athlete.get_coaches_by_club_and_sport, name="get_coaches_by_club_and_sport"),
    path("ajax/get-parents-by-club-sport-coach/", athlete.get_parents_by_club_sport_and_coach, name="get_parents_by_club_sport_and_coach"),

    # DEBUG URL-ek
    path('debug/gcs-upload/', debug_gcs_upload, name='debug_gcs_upload'),
    path('debug/settings/', debug_settings, name='debug_settings'),
]