# data_sharing/sharing_views/leader.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.core.serializers.json import DjangoJSONEncoder
from datetime import date
import json
from biometric_data.models import WeightData, HRVandSleepData, RunningPerformance, WorkoutFeedback
from users.models import UserRole, User 
from users.utils import _check_user_role 
from assessment.models import PlaceholderAthlete, PhysicalAssessment
from data_sharing.models import DataSharingPermission
from training_log.models import Attendance
from training_log.utils import get_attendance_summary
from diagnostics_jobs.models import DiagnosticJob
from ml_engine.models import UserFeatureSnapshot
from biometric_data.analytics import (
    generate_weight_feedback, 
    generate_hrv_sleep_feedback
)

def calculate_age(born):
    if not born: return 'N/A'
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

def has_biometric_permission(data_owner, data_viewer, table_names):
    """
    Ellenőrzi, hogy a data_viewer rendelkezik-e engedéllyel a data_owner 
    megadott tábláinak (table_names) legalább egyikéhez.
    """
    if not data_owner or not data_viewer:
        return False

    # 1. Lekérjük a megtekintő (edző/vezető) összes aktív szerepkörét
    viewer_roles = UserRole.objects.filter(
        user=data_viewer, 
        status='approved'
    )

    # 2. Lekérjük az összes vonatkozó engedélyt ezekhez a szerepkörökhöz
    permissions = DataSharingPermission.objects.filter(
        athlete=data_owner,
        target_person=data_viewer,
        target_role__in=viewer_roles,
        table_name__in=table_names
    )

    if not permissions.exists():
        return False

    # 3. Életkor alapú ellenőrzés
    is_adult = getattr(data_owner, 'is_adult', True) # Alapértelmezett True, ha nincs ilyen property

    for perm in permissions:
        if is_adult:
            # Felnőttnél elég a sportoló beleegyezése
            if perm.athlete_consent:
                return True
        else:
            # Kiskorúnál mindkettő kell
            if perm.athlete_consent and perm.parent_consent:
                return True

    return False

@login_required
def leader_dashboard(request):
    leader = request.user
    
    # 1. Megkeressük az összes olyan klubot, ahol "Egyesületi vezető" vagy
    # Fontos: a státusznak 'approved'-nek kell lennie
    leader_roles = UserRole.objects.filter(
        user=leader, 
        role__name="Egyesületi vezető",
        status="approved"
    )
    
    # Kigyűjtjük a klubok ID-it
    club_ids = list(leader_roles.values_list('club_id', flat=True))
    
    print(f"DEBUG: Leader ID: {leader.id}, Klubjai: {club_ids}")

    # 2. Megkeressük az összes sportolót, aki ezekbe a klubokba tartozik
    # Itt a szerepkör neve a kódod alapján: "Sportoló"
    all_club_athletes = User.objects.filter(
        user_roles__club_id__in=club_ids,
        user_roles__role__name="Sportoló",
        user_roles__status="approved"
    ).distinct()
    
    print(f"DEBUG: Klubban talált jóváhagyott sportolók: {all_club_athletes.count()}")

    athletes_data = []
    for athlete in all_club_athletes:
        # 1. Megnézzük, van-e engedély (de nem ugrunk ki, ha nincs!)
        permissions_qs = DataSharingPermission.objects.filter(
            athlete=athlete,
            target_person=leader,
            athlete_consent=True
        )
        
        if not athlete.is_adult:
            permissions_qs = permissions_qs.filter(parent_consent=True)

        # Itt a változtatás: kikerül az 'if permissions_qs.exists():' blokkból a hozzáadás
        permissions = list(permissions_qs.values_list('table_name', flat=True)) if permissions_qs.exists() else []
        has_any_permission = len(permissions) > 0

        ath_role = athlete.user_roles.filter(role__name__icontains='Sportoló').first()
        
        athletes_data.append({
            'athlete_object': athlete,
            'profile_data': {
                'first_name': athlete.profile.first_name if hasattr(athlete, 'profile') else athlete.first_name,
                'last_name': athlete.profile.last_name if hasattr(athlete, 'profile') else athlete.last_name,
            },
            'athlete_club': ath_role.club if ath_role else None,
            'athlete_sport': ath_role.sport if ath_role else None,
            'permissions': permissions,
            'has_permission': has_any_permission,  # Új flag a HTML-nek
            'role_id': leader_roles.first().id if leader_roles.exists() else None
        })

    return render(request, 'data_sharing/leader/leader_dashboard.html', {
        'athletes_data': athletes_data
    })

@login_required
def leader_athlete_details(request, athlete_id, role_id):
    """
    Részletes nézet egy sportoló adatairól az Egyesületi vezető számára.
    """
    leader = request.user  # Coach helyett leader
    athlete = get_object_or_404(User, id=athlete_id)
    
    # JAVÍTÁS: A role_id-nak a BELÉPETT LEADER szerepkörének kell lennie
    # Ellenőrizzük, hogy a role valóban a leaderé-e és jóvá van-e hagyva
    role = get_object_or_404(UserRole, id=role_id, user=leader, status='approved')

    # Engedélyek ellenőrzése
    permissions_qs = DataSharingPermission.objects.filter(
        athlete=athlete,
        target_person=leader, # leader nézzük
        athlete_consent=True
    )

    if not athlete.is_adult:
        permissions_qs = permissions_qs.filter(parent_consent=True)
    
    if not permissions_qs.exists():
        from django.contrib import messages
        messages.warning(request, f"Nincs érvényes, jóváhagyott engedélyed {athlete.get_full_name()} adataihoz.")
        return redirect('data_sharing:leader_dashboard')

    # Ha idáig eljut a kód, akkor VAN engedély.
    # Most szedjük ki a táblaneveket a listába:
    permissions = list(permissions_qs.values_list('table_name', flat=True))

    if not getattr(athlete, 'is_adult', True):
        permissions_qs = permissions_qs.filter(parent_consent=True)
        
    permissions = list(permissions_qs.values_list('table_name', flat=True))

    if not permissions:
        from django.contrib import messages
        messages.error(request, "Nincs jogosultságod a sportoló adataihoz.")
        return redirect('data_sharing:coach_dashboard')

    context = {
        'athlete': athlete,
        'role': role,
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
    
    return render(request, 'data_sharing/leader/athlete_details.html', context)