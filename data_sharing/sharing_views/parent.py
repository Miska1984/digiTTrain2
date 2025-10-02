# /app/data_sharing/sharing_views/parent.py (JAVÍTVA: 'full_name' hiba)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from users.models import UserRole, User 
from users.utils import role_required, _check_user_role
from django.urls import reverse
from datetime import timedelta, date
from django.utils import timezone
import json 
from decimal import Decimal 
from data_sharing.models import BiometricSharingPermission 

# Feltételezett import a biometrikus adatokhoz használt segédfüggvényekre
try:
    from biometric_data.utils import (
        get_last_entry_info, 
        get_weight_data_and_feedback, 
        get_hrv_regeneration_index, 
        get_latest_fatigue_status
    )
except ImportError:
    # Ez a hibakezelés segít, ha a utils fájl még hiányzik
    print("FIGYELMEZTETÉS: A biometric_data.utils segédfüggvények importálása sikertelen. Ellenőrizze a utils.py fájlt.")


def calculate_age(born):
    """Kiszámítja a kort a születési dátumból."""
    if not born:
        return 'N/A'
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


@login_required
def parent_dashboard(request):
    """
    Szülői áttekintő lista (parent_list.html) az összes gyermekről.
    """
    parent = request.user
    if not _check_user_role(parent, "Szülő"):
        messages.error(request, "Nincs szülői szerepköröd.")
        return redirect("core:main_page")

    # Gyermekek lekérdezése
    children_roles = UserRole.objects.filter(
        parent=parent,
        role__name="Sportoló",
        status="approved"
    ).select_related(
        "user__profile",        
        "coach__profile",       
        "club",                 
        "sport"                 
    )

    children_data = []
    
    for role in children_roles:
        athlete = role.user
        profile = athlete.profile

        age = calculate_age(profile.birth_date) if hasattr(profile, 'birth_date') and profile.birth_date else 'N/A'
        
        dashboard_url = reverse('data_sharing:shared_parent_athlete_dashboard', kwargs={'athlete_id': athlete.id})
        
        # JAVÍTÁS: A coach nevét last_name és first_name mezőkből építjük fel!
        coach_name = f"{role.coach.profile.last_name} {role.coach.profile.first_name}" \
                     if role.coach and hasattr(role.coach, 'profile') else 'Nincs edző'
        
        # Edző fotó (feltételezve, hogy a profile_picture létezik)
        coach_photo = role.coach.profile.profile_picture.url \
                      if role.coach and hasattr(role.coach, 'profile') and role.coach.profile.profile_picture else '/static/images/default.jpg'
        
        club_logo = role.club.logo.url if role.club and role.club.logo else '/static/images/default_club.jpg'
        club_short_name = role.club.short_name if role.club else 'Nincs klub'
        
        children_data.append({
            "athlete": athlete,
            "profile": profile,
            # Az sportoló neve is last_name és first_name mezőkből épül
            "full_name": f"{profile.last_name} {profile.first_name}", 
            "age": age,
            "gender": profile.get_gender_display() if hasattr(profile, 'get_gender_display') else 'N/A',
            
            "coach_name": coach_name,
            "coach_photo": coach_photo,
            
            "club_logo": club_logo,
            "club_short_name": club_short_name,
            "sport_name": role.sport.name if role.sport else 'N/A',
            
            "dashboard_url": dashboard_url,
        })

    context = {
        "children_data": children_data,
        "page_title": "Gyermekek Áttekintő Listája"
    }
    
    return render(request, "data_sharing/parent/parent_list.html", context)


@login_required
def view_shared_athlete_data_for_parent(request, athlete_id):
    """
    Részletes szülői dashboard (shared_parent_athlete_dashboard.html).
    Trendekre és összefoglaló jelzésekre fókuszál.
    """
    parent = request.user
    athlete = get_object_or_404(User, id=athlete_id)
    
    # 1. Jogosultság ellenőrzés
    
    # a) Ellenőrizzük a UserRole kapcsolatot
    role_exists = UserRole.objects.filter(user=athlete, parent=parent, status="approved").exists()
    
    # b) Ellenőrizzük, hogy legalább egy biometrikus adat meg van-e osztva!
    # Ha nincs EGYETLEN ENGEDÉLYEZETT megosztás sem a sportolótól a szülő felé:
    sharing_enabled = BiometricSharingPermission.objects.filter(
        user=athlete,          # A sportoló az adatok tulajdonosa
        target_user=parent,    # A szülő a célfelhasználó
        enabled=True           # Engedélyezve van
    ).exists()
    
    if not role_exists or not sharing_enabled:
        messages.error(request, "Hozzáférés megtagadva. Nincs engedélyezett adatmegosztás ehhez a sportolóhoz.")
        return redirect('data_sharing:parent_dashboard')

    # 2. Időtartomány kezelése
    # ... (A korábbi időtartomány logika marad)
    period_param = request.GET.get('period', '1M')
    
    if period_param == '3M':
        days = 90
    elif period_param == '1M':
        days = 30
    elif period_param == '14D':
        days = 14
    elif period_param == '7D':
        days = 7
    else:
        days = 30
        
    start_date = timezone.localdate() - timedelta(days=days)
    # ... (További logika, context előkészítés, return render)
    
    # 3. Adatlekérdezés a segédfüggvényekkel
    try:
        last_entries_data, missing_data_messages = get_last_entry_info(athlete)
        weight_chart_data, weight_trend_feedback = get_weight_data_and_feedback(athlete, start_date)
        hrv_index = get_hrv_regeneration_index(athlete, start_date)
        fatigue_status = get_latest_fatigue_status(athlete)
        
    except NameError as e:
        messages.error(request, f"Adatfeldolgozási hiba. Hiányzó segédfüggvények: {e}")
        return redirect('data_sharing:parent_dashboard')

    context = {
        'athlete': athlete,
        'profile': athlete.profile,
        'period': period_param,
        'start_date': start_date,
        'last_entries': last_entries_data,
        'missing_data_messages': missing_data_messages, 
        
        'weight_chart_json': json.dumps(weight_chart_data), 
        'weight_trend_feedback': weight_trend_feedback,
        
        'hrv_index': hrv_index,
        'fatigue_status': fatigue_status,
        
        'period_options': {'3M': '3 Hónap', '1M': '1 Hónap', '14D': '14 Nap', '7D': '7 Nap'}, 
        'page_title': f"{athlete.profile.last_name} Adatnézet (Szülő)",
    }
    
    return render(request, "data_sharing/parent/shared_parent_athlete_dashboard.html", context)