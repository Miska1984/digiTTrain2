# data_sharing/sharing_views/leader.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from datetime import date

from users.models import UserRole, User 
from users.utils import _check_user_role 
from assessment.models import PlaceholderAthlete, PhysicalAssessment


def calculate_age(born):
    """Kiszámítja a kort a születési dátumból."""
    if not born:
        return 'N/A'
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


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
    }
    
    return render(request, "data_sharing/leader/dashboard.html", context) 


