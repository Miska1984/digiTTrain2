# /app/data_sharing/urls.py

from django.urls import path
from . import views
from .sharing_views import parent, coach, leader

app_name = 'data_sharing'

urlpatterns = [
    # -------------------- Közös Megosztás Nézetek --------------------
    path('', views.data_sharing_center, name='sharing_center'),
    path('toggle/', views.toggle_permission, name='toggle_permission'),
    path('shared/', views.shared_data_view, name='shared_data_view'),

    # -------------------- Szülői Nézetek --------------------
    # 1. Szülői Áttekintő Lista (Ahol a gyerekek kártyái látszanak)
    path('parent/dashboard/', parent.parent_dashboard, name='parent_dashboard'),
     path('parent/athlete/details/<int:athlete_id>/', parent.parent_athlete_details, name='parent_athlete_details'),
    

    # -------------------- Egyesületi Vezetői Nézetek --------------------
    path('leader/', leader.leader_dashboard, name='leader_dashboard'),
    path('leader/athlete/details/<str:athlete_type>/<int:athlete_id>/', leader.leader_athlete_details, name='leader_athlete_details'), 
    
    # -------------------- Edzői Nézetek --------------------
    path('coach/', coach.coach_dashboard, name='coach_dashboard'),
    
    # Edzői részletes sportoló nézet (ha szükséges)
    path('coach/athlete/details/<str:athlete_type>/<int:athlete_id>/', 
         coach.coach_athlete_details, 
         name='coach_athlete_details'),
    
    # 1. PlaceholderAthlete felvitel
    path('coach/add_unregistered_athlete/', coach.add_unregistered_athlete, name='add_unregistered_athlete'),
            # ÚJ IMPORT/EXPORT URL-ek Exelhez
    path('coach/athlete/template/export/', coach.export_placeholder_template, name='export_placeholder_template'),
    path('coach/athlete/import/', coach.import_placeholder_athletes, name='import_placeholder_athletes'),

    # 2. Edzéshívás
    path('coach/create_training_session/', coach.create_training_session, name='create_training_session'),

    # 3. Jelenlét (Exporthoz is használható lesz)
    path('coach/manage_attendance/<int:session_id>/', coach.manage_attendance, name='manage_attendance'),
    path('coach/import_attendance/<int:session_id>/', coach.import_attendance_excel, name='import_attendance_excel'),
    path('coach/attendance/record/<int:schedule_pk>/<str:session_date>/', coach.record_attendance, name='record_attendance'),
    # 3.1 Jelenléti ív export)
    path('attendance/export/select/<int:club_pk>/<int:sport_pk>/', 
     coach.attendance_export_form, name='attendance_export_form'),
    path('export/attendance/<int:club_pk>/<int:sport_pk>/<str:start_date_str>/<str:end_date_str>/', 
     coach.export_attendance_report, name='export_attendance_report'), 
    
    # 4. Fizikai felmérés rögzítése
    path('coach/add_physical_assessment/', coach.add_physical_assessment, name='add_physical_assessment'),

    # Edzésrend és Szünetek Kezelése
    path('coach/schedules/', coach.manage_schedules, name='manage_schedules'),
    path('coach/schedules/add/', coach.add_schedule, name='add_schedule'),
    path('coach/schedules/<int:pk>/edit/', coach.edit_schedule, name='edit_schedule'), # Még nincs megírva, de kelleni fog
    path('coach/schedules/<int:pk>/delete/', coach.delete_schedule, name='delete_schedule'), # Még nincs megírva, de kelleni fog
    
    # Szünetek
    path('coach/absences/add/', coach.add_absence, name='add_absence'),
    path('coach/absences/<int:pk>/edit/', coach.edit_absence, name='edit_absence'), # Még nincs megírva
    path('coach/absences/<int:pk>/delete/', coach.delete_absence, name='delete_absence'), # Még nincs megírva


]