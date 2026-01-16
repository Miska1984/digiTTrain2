# data_sharing/sharing_views/leader.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from datetime import date
from biometric_data.models import WeightData, HRVandSleepData, RunningPerformance, WorkoutFeedback
from users.models import UserRole, User 
from users.utils import _check_user_role 
from assessment.models import PlaceholderAthlete, PhysicalAssessment
from data_sharing.models import BiometricSharingPermission
from training_log.models import Attendance

def calculate_age(born):
    """Kiszámítja a kort a születési dátumból."""
    if not born:
        return 'N/A'
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

def _has_permission(data_owner, data_viewer, permitted_tables):
    """Ellenőrzi, hogy van-e engedély bármelyik releváns táblára"""
    for table in permitted_tables:
        if BiometricSharingPermission.is_data_shared(
            data_owner=data_owner,
            data_viewer=data_viewer,
            app_name="biometric_data",
            table_name=table,
        ):
            return True
    return False

@login_required
def leader_dashboard(request):
    """
    Egyesületi vezető dashboard – kilistázza a vezető klubjaihoz tartozó ÖSSZES sportolót.
    """
    leader = request.user
    
    if not _check_user_role(leader, "Egyesületi vezető"):
        messages.error(request, "Hozzáférés megtagadva, nincs egyesületi vezetői szerepköröd.")
        return redirect("core:main_page")

    athlete_cards = []

    # A. Lekérdezzük a Vezető aktív klub ID-it
    leader_roles = UserRole.objects.filter(
        user=leader, 
        role__name="Egyesületi vezető", 
        status="approved"
    )
    allowed_club_ids = leader_roles.values_list('club_id', flat=True).distinct()

    if not allowed_club_ids:
        # Ha nincs aktív klub, üres listával térünk vissza
        context = {'athlete_cards': athlete_cards, 'page_title': "Vezetői Dashboard - Nincs aktív szerepkör"}
        return render(request, "data_sharing/leader/dashboard.html", context)

    # --- 1. Regisztrált Sportolók (User modellek) lekérdezése ---
    # Szűrünk azokra a sportolói szerepekre, amelyek a Vezető által engedélyezett klubokhoz tartoznak
    registered_roles = UserRole.objects.filter(
        club_id__in=allowed_club_ids,
        role__name='Sportoló',
        status='approved'
    ).select_related('user__profile', 'sport', 'club')

    for role in registered_roles: 
        athlete = role.user
        profile = athlete.profile
        # Kétféle mező is lehet, ha korábban birth_date volt, most date_of_birth
        age = calculate_age(profile.date_of_birth) if profile.date_of_birth else 'N/A'
        
        # Jelenlét adatok (most fix 0, amíg a pandas/numpy hiba fennáll)
        # attendance_30d = get_attendance_summary(athlete, 30)
        attendance_30d = {'attendance_rate': 0, 'sessions_attended': 0} 

        athlete_cards.append({
            'type': 'user',
            'id': athlete.id,
            'full_name': f"{profile.first_name} {profile.last_name}",
            'is_registered': True,
            'age': age,
            'club_name': role.club.short_name if role.club else 'N/A',
            'sport_name': role.sport.name if role.sport else 'N/A', # Vezető látja a sportágat
            'attendance_rate_30d': attendance_30d.get('attendance_rate', 0),
            'last_assessment_date': PhysicalAssessment.objects.filter(athlete_user=athlete).order_by('-assessment_date').values_list('assessment_date', flat=True).first(),
        })

    # --- 2. Nem Regisztrált Sportolók (PlaceholderAthlete modellek) lekérdezése ---
    # Szűrünk minden Placeholder sportolóra, akik a Vezető klubjaihoz tartoznak
    placeholder_athletes = PlaceholderAthlete.objects.filter(
        club_id__in=allowed_club_ids,
        registered_user__isnull=True
    ).select_related('club', 'sport').order_by('last_name')
    
    for ph_athlete in placeholder_athletes: 
        age = calculate_age(ph_athlete.birth_date) if ph_athlete.birth_date else 'N/A'
        
        # Jelenlét adatok (fix 0)
        # attendance_30d = get_attendance_summary(ph_athlete, 30)
        
        athlete_cards.append({
            'type': 'placeholder',
            'id': ph_athlete.id,
            'full_name': f"{ph_athlete.first_name} {ph_athlete.last_name}",
            'is_registered': False,
            'age': age,
            'club_name': ph_athlete.club.short_name if ph_athlete.club else 'N/A',
            'sport_name': ph_athlete.sport.name if ph_athlete.sport else 'N/A',
            'attendance_rate_30d': 0,
            'last_assessment_date': PhysicalAssessment.objects.filter(athlete_placeholder=ph_athlete).order_by('-assessment_date').values_list('assessment_date', flat=True).first(),
        })

    # Név szerinti rendezés
    athlete_cards = sorted(athlete_cards, key=lambda x: x['full_name'])

    context = {
        'athlete_cards': athlete_cards, 
        'page_title': "Egyesületi Vezetői Dashboard - Sportolói Áttekintés",
        'app_context': 'leader_dashboard',
    }
    
    return render(request, "data_sharing/leader/dashboard.html", context) 

@login_required
def leader_athlete_details(request, athlete_type, athlete_id):
    """
    Vezetői nézet – Sportoló részletes adatainak megjelenítése.
    Integrálva a biometrikus adatok megosztási logikájával.
    """
    leader = request.user
    print(f"👔 [DEBUG] leader_athlete_details hívva athlete_type='{athlete_type}' athlete_id={athlete_id}")
    
    # 1. Vezetői jogosultság ellenőrzése
    leader_roles = UserRole.objects.filter(
        user=leader, 
        role__name="Egyesületi vezető", 
        status="approved"
    ).select_related('club')

    if not leader_roles.exists():
        raise PermissionDenied("Nincs jogosultsága ehhez a művelethez.")

    managed_club_ids = [role.club.id for role in leader_roles]
    print(f"📋 [DEBUG] Kezelt klub ID-k: {managed_club_ids}")
    
    athlete = None
    role = None
    profile_data = None
    is_placeholder = False
    
    # 2. Sportoló (vagy Placeholder) lekérése
    if athlete_type == 'user':
        athlete = get_object_or_404(User, id=athlete_id)
        is_placeholder = False
        print(f"👤 [DEBUG] Regisztrált sportoló: {athlete.username}")
        
        role = UserRole.objects.filter(
            user=athlete, 
            role__name='Sportoló', 
            status='approved', 
            club__id__in=managed_club_ids
        ).select_related('club', 'sport', 'parent').first()
        
        if not role:
            raise PermissionDenied("A sportoló nem tartozik az Ön által kezelt klubhoz.")
        
        profile_data = athlete.profile
        athlete_club = role.club
        athlete_sport = role.sport
        
    elif athlete_type == 'placeholder':
        athlete = get_object_or_404(PlaceholderAthlete, id=athlete_id)
        is_placeholder = True
        print(f"📝 [DEBUG] Placeholder sportoló: {athlete.first_name} {athlete.last_name}")
        
        if athlete.club_id not in managed_club_ids:
             raise PermissionDenied("Az ideiglenes sportoló nem tartozik az Ön által kezelt klubhoz.")
             
        profile_data = athlete 
        athlete_club = athlete.club
        athlete_sport = athlete.sport
        
    else:
        raise PermissionDenied("Érvénytelen sportoló típus.")

    # 3. Adatok lekérése
    athlete_display_name = f"{profile_data.first_name} {profile_data.last_name}"
    print(f"🏃 [DEBUG] Sportoló neve: {athlete_display_name}")
    
    # Alapértelmezett értékek
    last_weight = None
    last_hrv_sleep = None
    running_performance = None
    enhanced_logs = []
    can_view_biometrics = False
    feedback_visible = False
    
    # Felmérések
    if is_placeholder:
        assessments = PhysicalAssessment.objects.filter(
            athlete_placeholder=athlete
        ).order_by('-assessment_date')
    else:
        assessments = PhysicalAssessment.objects.filter(
            athlete_user=athlete
        ).order_by('-assessment_date')
    
    # ==========================================
    # REGISZTRÁLT USER ESETÉN: Biometrikus adatok
    # ==========================================
    if not is_placeholder:
        print("🔍 [DEBUG] Regisztrált user - biometrikus engedély ellenőrzése...")
        
        # --- Engedélyezett táblák ---
        permitted_tables = [
            "ALL",
            "WeightData",
            "HRVandSleepData",
            "RunningPerformance",
            "WorkoutFeedback",
        ]
        
        # --- Ki az engedélyező? ---
        data_owner_for_permission = athlete
        
        # Felnőtt sportoló esetén: saját döntés
        if athlete.is_adult:
            print(f"👨 [DEBUG] Felnőtt sportoló - közvetlen engedély keresése")
            can_view_biometrics = _has_permission(data_owner_for_permission, leader, permitted_tables)
            print(f"🔐 [DEBUG] Felnőtt engedély: {can_view_biometrics}")
        
        # Kiskorú sportoló esetén: szülő engedélye szükséges
        else:
            print("👶 [DEBUG] Kiskorú sportoló, szülő engedélyét keresem a UserRole-ban...")
            
            athlete_role = UserRole.objects.filter(
                user=athlete,
                role__name='Sportoló',
                status='approved',
                parent__isnull=False
            ).select_related('parent').first()
            
            parent = None
            
            if athlete_role:
                print(f"✅ [DEBUG] Jóváhagyott sportoló szerepkör megtalálva (Role ID: {athlete_role.id})")
                
                if athlete_role.approved_by_parent:
                    parent = athlete_role.parent
                    print(f"✅ [DEBUG] Szülő jóváhagyás MEGVAN! Szülő: {parent.username} (ID: {parent.id})")
                else:
                    print("⚠️ [DEBUG] Nincs jóváhagyás a szülőtől (approved_by_parent=False)")
            else:
                print("⚠️ [DEBUG] Nincs jóváhagyott Sportoló szerepkör, amihez szülő lenne rendelve.")
            
            # Engedély ellenőrzése a SZÜLŐ → VEZETŐ útvonalon
            if parent:
                can_view_biometrics = _has_permission(parent, leader, permitted_tables)
                print(f"👨‍👩‍👦 [DEBUG] Szülő által engedélyezett (szülőn keresztül): {can_view_biometrics}")
            else:
                print(f"⚠️ [DEBUG] Nincs jóváhagyott szülő kapcsolat! athlete_id={athlete.id}. Can_view_biometrics=False")
                can_view_biometrics = False
        
        print(f"🔐 [DEBUG] VÉGSŐ can_view_biometrics={can_view_biometrics}")
        
        # --- Adatlekérés, ha van engedély ---
        if can_view_biometrics:
            print("✅ [DEBUG] Biometrikus adatok lekérése...")
            last_weight = WeightData.objects.filter(user=athlete).order_by('-workout_date').first()
            last_hrv_sleep = HRVandSleepData.objects.filter(user=athlete).order_by('-recorded_at').first()
            running_performance = RunningPerformance.objects.filter(user=athlete).order_by('-run_date')
            feedback_visible = True
            print(f"📊 [DEBUG] last_weight: {last_weight}, last_hrv_sleep: {last_hrv_sleep}")
        else:
            print("❌ [DEBUG] Nincs biometrikus engedély - adatok elrejtve")
            feedback_visible = False

        # --- Edzésnapló feldolgozás (FEEDBACK + SÚLY) ---
        print("📝 [DEBUG] Edzésnapló feldolgozása...")
        athlete_logs = Attendance.objects.filter(
            registered_athlete=athlete
        ).select_related('session').order_by('-session__session_date')[:10]

        intensity_map = dict(WorkoutFeedback.INTENSITY_CHOICES[1:])
        
        for log in athlete_logs:
            feedback = WorkoutFeedback.objects.filter(
                user=athlete, 
                workout_date=log.session.session_date
            ).first()

            weight_entry = WeightData.objects.filter(
                user=athlete, 
                workout_date=log.session.session_date
            ).first()

            if feedback or weight_entry:
                pre = weight_entry.pre_workout_weight if weight_entry else None
                post = weight_entry.post_workout_weight if weight_entry else None
                fluid = weight_entry.fluid_intake if weight_entry else None

                if pre and post:
                    loss_kg = float(pre) - float(post)
                    loss_pct = (loss_kg / float(pre)) * 100 if float(pre) > 0 else None
                else:
                    loss_kg = None
                    loss_pct = None

                log.feedback_data = {
                    'intensity': feedback.workout_intensity if feedback else None,
                    'intensity_label': intensity_map.get(feedback.workout_intensity) if feedback else None,
                    'pre_weight': pre,
                    'post_weight': post,
                    'fluid': fluid,
                    'loss_kg': round(loss_kg, 2) if loss_kg else None,
                    'loss_pct': round(loss_pct, 1) if loss_pct else None,
                }
                print(f"📌 [DEBUG] Log {log.session.session_date}: feedback={feedback is not None}, weight={weight_entry is not None}")
            else:
                log.feedback_data = None

            enhanced_logs.append(log)
        
        print(f"📋 [DEBUG] {len(enhanced_logs)} edzésnapló feldolgozva")
            
    # ==========================================
    # PLACEHOLDER ESETÉN: Csak edzésnapló
    # ==========================================
    elif is_placeholder:
        print("📝 [DEBUG] Placeholder - csak edzésnapló...")
        athlete_logs = Attendance.objects.filter(
            placeholder_athlete=athlete
        ).select_related('session').order_by('-session__session_date')[:10]
        enhanced_logs = list(athlete_logs)
    
    # 4. Kontextus
    context = {
        'page_title': f"{athlete_display_name} - Vezetői Részletek",
        'athlete_display_name': athlete_display_name,
        'profile_data': profile_data, 
        'athlete_object': athlete, 
        'athlete_type': athlete_type,
        'is_placeholder': is_placeholder,

        # Biometrikus adatok
        'last_weight': last_weight,
        'last_hrv_sleep': last_hrv_sleep,
        'running_performance': running_performance,
        'can_view_biometrics': can_view_biometrics,
        'feedback_visible': feedback_visible,  # ⬅️ MOST MÁR BENT VAN!
        
        # Egyéb fülek
        'training_logs': enhanced_logs, 
        'assessments': assessments,
        'athlete_club': athlete_club,
        'athlete_sport': athlete_sport,
    }
    
    print(f"🎯 [DEBUG] Kontextus létrehozva - can_view_biometrics={can_view_biometrics}, feedback_visible={feedback_visible}")
    print(f"📦 [DEBUG] training_logs darabszám: {len(enhanced_logs)}")

    return render(request, 'data_sharing/leader/athlete_details.html', context)