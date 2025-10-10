from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from users.models import User, UserRole
from biometric_data.models import WeightData, HRVandSleepData, RunningPerformance, WorkoutFeedback
from training_log.models import Attendance
from assessment.models import PhysicalAssessment


@login_required
def parent_dashboard(request):
    """
    Szülői műszerfal. Listázza az összes kiskorú gyermeket, akiknek a szülője a bejelentkezett felhasználó.
    """
    parent = request.user
    
    # --- 1. Keresse meg a szülőhöz rendelt jóváhagyott Sportoló szerepköröket ---
    # A UserRole a Sportoló maga, akinek a parent mezője megegyezik a bejelentkezett szülővel.
    children_roles = UserRole.objects.filter(
        parent=parent,
        role__name='Sportoló',
        status='approved'
    ).select_related('user__profile', 'club', 'sport').order_by('user__profile__last_name')
    
    # --- 2. Adatok gyűjtése a dashboard kártyákhoz ---
    children_data = []
    
    for role in children_roles:
        athlete = role.user
        
        # Mivel a jogosultságot már ellenőriztük a szűrőben,
        # csak az alapvető kártyaadatokat kérjük le.
        
        # Biometrikus adat (opcionális, de jó, ha a dashboardon látszik valami)
        try:
            from biometric_data.models import WeightData
            last_weight = WeightData.objects.filter(user=athlete).order_by('-workout_date').first()
        except ImportError:
            last_weight = None # Hiba esetén (ha az import nem létezik)

        # Ellenőrzés, hogy kiskorú-e, bár a logikailag helyesen csak kiskorút kellene látnia.
        # Ha a szülő a saját felnőtt gyermekét akarja látni, akkor más jogosultság kell.
        if not athlete.is_adult:
            children_data.append({
                'athlete_object': athlete,
                'profile_data': athlete.profile,
                'athlete_club': role.club,
                'athlete_sport': role.sport,
                'last_weight': last_weight,
            })
            
    context = {
        'page_title': 'Gyermekeim Áttekintője',
        'children_data': children_data,
    }
    
    return render(request, 'data_sharing/parent/parent_dashboard.html', context)

@login_required
def parent_athlete_details(request, athlete_id):
    """
    Szülői nézet – Kiskorú sportoló (User) részletes adatainak megjelenítése.
    A szülőnek alapértelmezetten látnia kell minden biometrikus adatot.
    """
    parent = request.user

    # --- 1. Sportoló lekérése ---
    athlete = get_object_or_404(User, id=athlete_id)
    
    # ⚠️ Placeholder sportolóknak nincs szülői nézete a regisztráció hiánya miatt,
    # így itt csak regisztrált 'User' sportolókkal foglalkozunk.
    if athlete.is_adult:
        raise PermissionDenied("Csak kiskorú gyermekek adatai tekinthetők meg szülői felületről.")
        
    # --- 2. Jogosultság ellenőrzés (a sportoló a bejelentkezett szülő gyermeke-e) ---
    is_parent_of_athlete = UserRole.objects.filter(
        user=athlete,
        role__name='Sportoló',
        parent=parent, # A szülő mezőnek meg kell egyeznie a bejelentkezett felhasználóval
        status='approved'
    ).exists()

    if not is_parent_of_athlete:
        raise PermissionDenied("Nincs jogosultsága megtekinteni ezt a sportolót.")

    # --- 3. Adatok lekérése (MINDIG láthatók) ---
    
    # Biometrikus adatok
    last_weight = WeightData.objects.filter(user=athlete).order_by('-workout_date').first()
    last_hrv_sleep = HRVandSleepData.objects.filter(user=athlete).order_by('-recorded_at').first()
    running_performance = RunningPerformance.objects.filter(user=athlete).order_by('-run_date')
    
    # Edzésnapló, visszajelzés és súlyadatok (Enhanced Logs)
    athlete_logs = Attendance.objects.filter(
        registered_athlete=athlete
    ).select_related('session').order_by('-session__session_date')[:10]

    intensity_map = dict(WorkoutFeedback.INTENSITY_CHOICES[1:])
    enhanced_logs = []

    for log in athlete_logs:
        # Lekérjük a visszajelzéseket és a súlyadatokat (ezek a biometrikus adatok részét képezik)
        feedback = WorkoutFeedback.objects.filter(
            user=athlete, workout_date=log.session.session_date
        ).first()

        weight_entry = WeightData.objects.filter(
            user=athlete, workout_date=log.session.session_date
        ).first()

        log.feedback_data = None # Alapérték
        
        if feedback or weight_entry:
            pre = weight_entry.pre_workout_weight if weight_entry else None
            post = weight_entry.post_workout_weight if weight_entry else None
            loss_kg = None
            loss_pct = None
            
            if pre and post:
                try:
                    # Mivel ezek DecimalField-ek, konvertálás Decimal/float-ra a számításhoz
                    pre_f = float(pre)
                    post_f = float(post)
                    loss_kg = pre_f - post_f
                    loss_pct = (loss_kg / pre_f) * 100 if pre_f > 0 else None
                except (ValueError, TypeError):
                    pass # Hiba esetén hagyjuk None-t

            log.feedback_data = {
                'intensity': feedback.workout_intensity if feedback else None,
                'intensity_label': intensity_map.get(feedback.workout_intensity) if feedback else None,
                'pre_weight': pre,
                'post_weight': post,
                'fluid': weight_entry.fluid_intake if weight_entry else None,
                'loss_kg': round(loss_kg, 2) if loss_kg is not None else None,
                'loss_pct': round(loss_pct, 1) if loss_pct is not None else None,
            }

        enhanced_logs.append(log)

    # Fizikai felmérések
    assessments = PhysicalAssessment.objects.filter(
        athlete_user=athlete
    ).order_by('-assessment_date')

    # Klub és sport infó
    role = UserRole.objects.filter(
        user=athlete, role__name='Sportoló', status='approved'
    ).select_related('club', 'sport').first()

    athlete_club = role.club if role else None
    athlete_sport = role.sport if role else None
    
    # --- 4. Kontextus ---
    athlete_display_name = f"{athlete.profile.first_name} {athlete.profile.last_name}"
    
    context = {
        'page_title': f"{athlete_display_name} - Gyermek adatai",
        'athlete_display_name': athlete_display_name,
        'athlete_object': athlete,
        'profile_data': athlete.profile,
        'last_weight': last_weight,
        'last_hrv_sleep': last_hrv_sleep,
        'running_performance': running_performance,
        'training_logs': enhanced_logs, # Használjuk a kibővített naplót
        'assessments': assessments,
        'athlete_club': athlete_club,
        'athlete_sport': athlete_sport,
        'can_view_biometrics': True, # Mindig True a szülőnek
    }

    return render(request, 'data_sharing/parent/athlete_details.html', context)