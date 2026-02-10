# /app/data_sharing/sharing_views/parent.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from datetime import timedelta
import json

# Modellek importálása
from biometric_data.models import HRVandSleepData, WeightData, WorkoutFeedback
from users.models import User, UserRole
from data_sharing.models import DataSharingPermission  # FRISSÍTVE: Új modellnév
from training_log.models import Attendance
from assessment.models import PhysicalAssessment
from training_log.utils import get_attendance_summary
from ml_engine.models import UserFeatureSnapshot, UserPredictionResult
from diagnostics_jobs.models import DiagnosticJob

# A saját utils fájljaid importálása
from biometric_data.utils import (
    get_last_entry_info, 
    get_weight_data_and_feedback, 
    get_hrv_regeneration_index, 
    get_latest_fatigue_status
)

from biometric_data.analytics import (
    generate_weight_feedback, 
    generate_hrv_sleep_feedback, 
    generate_timing_feedback, 
    generate_running_feedback
)

@login_required
def parent_dashboard(request):
    """
    Szülői műszerfal. Listázza az összes kiskorú gyermeket és az elérhető adataikat.
    """
    parent = request.user
    
    # 1. Gyerekek lekérése
    children_roles = UserRole.objects.filter(
        parent=parent,
        role__name='Sportoló',
        status='approved'
    ).select_related('user__profile', 'club', 'sport').order_by('user__profile__last_name')
    
    children_data = []
    
    for role in children_roles:
        athlete = role.user
        
        # 2. Engedélyek szűrése (Nincs 'enabled' mező, ezért Q objektumokat használunk)
        # Feltétel: (Sportoló engedélyezte ÉS Szülő engedélyezte)
        permissions_qs = DataSharingPermission.objects.filter(
            athlete=athlete, 
            target_person=parent,
            athlete_consent=True,
            parent_consent=True
        )
        permissions = list(permissions_qs.values_list('table_name', flat=True))

        # 3. Alapadatok begyűjtése a dashboardhoz
        last_weight = WeightData.objects.filter(user=athlete).order_by('-workout_date').first()
        
        attendance_stats = None
        if 'Attendance' in permissions:
            attendance_stats = get_attendance_summary(athlete, days=30)

        ditta_score = None
        if 'UserFeatureSnapshot' in permissions:
            ditta_score = UserFeatureSnapshot.objects.filter(user=athlete).order_by('-generated_at').first()

        # Csak kiskorúakat listázunk (vagy akit a szülő felügyel)
        children_data.append({
            'athlete_object': athlete,
            'profile_data': athlete.profile,
            'athlete_club': role.club,
            'athlete_sport': role.sport,
            'last_weight': last_weight,
            'permissions': permissions,
            'attendance_stats': attendance_stats,
            'ditta_score': ditta_score,
        })
            
    context = {
        'page_title': 'Gyermekeim Áttekintője',
        'children_data': children_data,
    }
    
    return render(request, 'data_sharing/parent/parent_dashboard.html', context)


@login_required
def parent_athlete_details(request, athlete_id):
    """
    Részletes nézet egy adott gyermek adatairól.
    """
    parent = request.user
    athlete = get_object_or_404(User, id=athlete_id)

    # Jogosultság ellenőrzése: a szülő tényleg szülője-e a gyereknek?
    is_authorized_parent = UserRole.objects.filter(user=athlete, parent=parent).exists()
    if not is_authorized_parent:
        return render(request, '403.html', {'message': 'Nincs jogosultsága a sportoló adataihoz.'})

    # Engedélyek lekérése (Szigorú: mindkét fél beleegyezése kell)
    permissions_qs = DataSharingPermission.objects.filter(
        athlete=athlete, 
        target_person=parent,
        athlete_consent=True,
        parent_consent=True
    )
    permissions = list(permissions_qs.values_list('table_name', flat=True))

    context = {
        'athlete': athlete,
        'permissions': permissions,
        'athlete_display_name': f"{athlete.profile.first_name} {athlete.profile.last_name}",
    }

    # --- Adatok betöltése csak ha van engedély ---
    # --- SÚLY ADATOK ---
    if 'WeightData' in permissions:
        weight_qs = WeightData.objects.filter(user=athlete).order_by('-workout_date')
        context['weight_feedback'] = generate_weight_feedback(weight_qs)
        entries = weight_qs[:30][::-1]
        context['weight_chart_data_json'] = json.dumps({
            "labels": [e.workout_date.strftime("%Y-%m-%d") for e in entries],
            "weights": [float(e.morning_weight) for e in entries],
            "body_fat_data": [float(e.body_fat_percentage or 0) for e in entries],
            "muscle_data": [float(e.muscle_percentage or 0) for e in entries],
        })

    # --- HRV ÉS ALVÁS ---
    if 'HRVandSleepData' in permissions:
        hrv_qs = HRVandSleepData.objects.filter(user=athlete).order_by('-recorded_at')
        context['hrv_sleep_feedback'] = generate_hrv_sleep_feedback(hrv_qs)
        entries = hrv_qs[:30][::-1]
        context['hrv_sleep_chart_data_json'] = json.dumps({
            "labels": [e.recorded_at.strftime("%Y-%m-%d") for e in entries],
            "hrv_data": [float(e.hrv or 0) for e in entries],
            "sleep_quality_data": [float(e.sleep_quality or 0) for e in entries],
            "alertness_data": [float(e.alertness or 0) for e in entries],
        })

    # --- EDZÉS VISSZAJELZÉS / MAROKERŐ ---
    if 'WorkoutFeedback' in permissions:
        workout_qs = WorkoutFeedback.objects.filter(user=athlete).order_by('-workout_date')
        entries = workout_qs[:30][::-1]
        
        labels, right_grip, left_grip, intensity_data = [], [], [], []
        for e in entries:
            labels.append(e.workout_date.strftime("%Y-%m-%d"))
            i_val = getattr(e, 'intensity_rpe', getattr(e, 'intensity', getattr(e, 'rpe', 0)))
            intensity_data.append(float(i_val) if i_val else 0)
            rg = getattr(e, 'right_grip_strength', getattr(e, 'grip_strength_right', 0))
            lg = getattr(e, 'left_grip_strength', getattr(e, 'grip_strength_left', 0))
            right_grip.append(float(rg) if rg else 0)
            left_grip.append(float(lg) if lg else 0)

        context['grip_intensity_chart_data_json'] = json.dumps({
            "labels": labels,
            "right_grip_data": right_grip,
            "left_grip_data": left_grip,
            "intensity_data": intensity_data,
        })

    # --- JELENLÉT ---
    if 'Attendance' in permissions:
        attendance_stats = get_attendance_summary(athlete, days=30)
        context['attendance_stats'] = attendance_stats
        logs = Attendance.objects.filter(registered_athlete=athlete).select_related('session__schedule').order_by('-session__session_date')[:10]
        context['attendance_logs'] = logs

    # --- AI SCORE ---
    if 'UserFeatureSnapshot' in permissions:
        ditta_score = UserFeatureSnapshot.objects.filter(user=athlete).order_by('-generated_at').first()
        context['ditta_score'] = ditta_score

    # --- DIAGNOSZTIKA ---
    if 'DiagnosticJob' in permissions:
        diagnostic_jobs = DiagnosticJob.objects.filter(user=athlete, status='COMPLETED').order_by('-created_at')[:5]
        context['diagnostic_jobs'] = diagnostic_jobs

    return render(request, 'data_sharing/parent/athlete_details.html', context)