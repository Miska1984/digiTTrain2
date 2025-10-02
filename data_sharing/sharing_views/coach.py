# /app/data_sharing/sharing_views/coach.py (TISZTÍTOTT ÉS BŐVÍTETT VERZIÓ)

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q 
from django.http import Http404, HttpResponse
from django.db import transaction, IntegrityError
from users.models import UserRole, User 
from users.utils import role_required, _check_user_role 
from data_sharing.models import BiometricSharingPermission # Még szükséges, ha az edző látja a biometrikus adatokat
from assessment.models import PlaceholderAthlete, PhysicalAssessment
from assessment.forms import PlaceholderAthleteForm, PlaceholderAthleteImportForm
from training_log.models import TrainingSession, Attendance, TrainingSchedule, AbsenceSchedule
from training_log.forms import TrainingScheduleForm, AbsenceScheduleForm 
from training_log.utils import get_attendance_summary, TIME_PERIODS, calculate_next_training_sessions
from datetime import date, datetime, time
from users.models import User
from users.utils import get_coach_clubs_and_sports
import logging
import pandas as pd
import io 

logger = logging.getLogger(__name__)

# from biometric_data.utils import calculate_rolling_avg_and_trend # Ideiglenesen kikommentelve

def calculate_age(born):
    """Kiszámítja a kort a születési dátumból."""
    if not born:
        return 'N/A'
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

# --- DASHBOARD NÉZETEK (Fókuszban a két lista) ---

@login_required
def coach_dashboard(request):
    """
    Edzői Dashboard:
    - Regisztrált sportolók (User)
    - Nem regisztrált sportolók (PlaceholderAthlete)
    """
    coach = request.user
    athlete_cards = []

    # 0. Jogosultságok kinyerése
    active_coach_roles = UserRole.objects.filter(
        user=coach,
        role__name='Edző',
        status='approved'
    )
    allowed_club_ids = active_coach_roles.values_list('club_id', flat=True).distinct()
    allowed_sport_ids = active_coach_roles.values_list('sport_id', flat=True).distinct()   

    # --- 1. Regisztrált sportolók ---
    registered_roles = UserRole.objects.filter(
        # TÖRÖLVE: coach=coach, <-- EZ A KORLÁTOZÁS VAN TÖRÖLVE!
        role__name='Sportoló',
        status='approved',
        club_id__in=allowed_club_ids,    # <-- ÚJ SZŰRÉS: Klub jogosultság
        sport_id__in=allowed_sport_ids   # <-- ÚJ SZŰRÉS: Sportág jogosultság
    ).select_related('user__profile', 'sport', 'club')

    for role in registered_roles:
        athlete = role.user
        profile = athlete.profile
        age = calculate_age(profile.date_of_birth) if profile.date_of_birth else 'N/A'

        attendance_30d = get_attendance_summary(athlete, 30)

        athlete_cards.append({
            'type': 'user',
            'id': athlete.id,
            'full_name': f"{profile.first_name} {profile.last_name}",
            'is_registered': True,
            'age': age,
            'club_name': role.club.short_name if role.club else 'N/A',
            'sport_name': role.sport.name if role.sport else 'N/A',
            'attendance_rate_30d': attendance_30d.get('attendance_rate', 0),
            'last_assessment_date': PhysicalAssessment.objects.filter(
                athlete_user=athlete
            ).order_by('-assessment_date').values_list('assessment_date', flat=True).first(),
        })

    # --- 2. Placeholder sportolók ---
    active_coach_roles = UserRole.objects.filter(
        user=coach,
        role__name='Edző',
        status='approved'
    )
    allowed_club_ids = active_coach_roles.values_list('club_id', flat=True).distinct()
    allowed_sport_ids = active_coach_roles.values_list('sport_id', flat=True).distinct()

    placeholder_athletes = PlaceholderAthlete.objects.filter(
        club_id__in=allowed_club_ids,
        sport_id__in=allowed_sport_ids,
        registered_user__isnull=True
    ).select_related('club', 'sport').order_by('last_name')

    for ph in placeholder_athletes:
        age = calculate_age(ph.birth_date) if ph.birth_date else 'N/A'

        athlete_cards.append({
            'type': 'placeholder',
            'id': ph.id,
            'full_name': f"{ph.first_name} {ph.last_name}",
            'is_registered': False,
            'age': age,
            'club_name': ph.club.short_name if ph.club else 'N/A',
            'sport_name': ph.sport.name if ph.sport else 'N/A',
            'attendance_rate_30d': 0,  # majd később bővíthető
            'last_assessment_date': PhysicalAssessment.objects.filter(
                athlete_placeholder=ph
            ).order_by('-assessment_date').values_list('assessment_date', flat=True).first(),
        })

    # Név szerinti rendezés
    athlete_cards = sorted(athlete_cards, key=lambda x: x['full_name'])

    context = {
        'athlete_cards': athlete_cards,
        'page_title': "Edzői Dashboard - Sportoló Áttekintés",
    }

    return render(request, "data_sharing/coach/dashboard.html", context)

# --- RÉSZLETES DASHBOARD NÉZET ---

@login_required
def athlete_detail(request, athlete_type, athlete_id):
    """
    Részletes dashboard regisztrált vagy nem regisztrált sportolókhoz (ez a régi athlete_dashboard_shared helyett).
    A logika megegyezik a korábban tervezettel.
    """
    # ... (A korábban tervezett athlete_detail logika ide kerül) ...
    pass # Ezt a részt ki kell töltenünk a tényleges logikával, ha erre sor kerül.

# --- ADATBEVITELI NÉZETEK (A FŐ PRIORITÁS) ---


@login_required
@role_required('Edző')
def add_unregistered_athlete(request):
    """
    Form a PlaceholderAthlete (nem regisztrált sportoló) felviteléhez.
    A Form csak az edző aktív szerepköreihez tartozó klubokat/sportokat kínálja fel.
    """
    # Átadjuk az edző felhasználói objektumát a Formnak
    coach_user = request.user
    
    if request.method == 'POST':
        # Átadjuk a coach_user-t a Formnak a szűréshez
        form = PlaceholderAthleteForm(request.POST, coach_user=coach_user)
        if form.is_valid():
            # Mivel a PlaceholderAthlete nem rendelkezik coach mezővel, csak mentjük
            new_athlete = form.save()
            
            messages.success(request, f"{new_athlete.last_name} {new_athlete.first_name} ideiglenes sportoló sikeresen felvíve!")
            return redirect('data_sharing:coach_dashboard') # Vissza a dashboardra
    else:
        # GET kérésnél is átadjuk a coach_user-t a szűréshez
        form = PlaceholderAthleteForm(coach_user=coach_user)

    context = {
        'form': form,
        'page_title': "Nem Regisztrált Sportoló Felvitele"
    }
    return render(request, "data_sharing/coach/add_unregistered_athlete.html", context)

@login_required
@role_required('Edző')
def export_placeholder_template(request):
    """
    Exportálja az üres Excel sablont a PlaceholderAthlete adatok importálásához.
    """
    # Excel oszlopfejlécek
    data = {
        'Vezetéknév (required)': [''],
        'Keresztnév (required)': [''],
        'Születési dátum (YYYY-MM-DD)': [''],
        'Nem (M - Férfi, F - Nő)': [''],
        'Megjegyzés (optional)': [''],
    }
    
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter') 
    df.to_excel(writer, index=False, sheet_name='Sportolók')
    
    # Adatérvényesítés beállítása (Nem oszlopra)
    try:
        workbook = writer.book
        worksheet = writer.sheets['Sportolók']
        worksheet.data_validation('D2:D1000', {'validate': 'list',
                                              'source': ['M', 'F']})
        writer.close()
    except Exception:
        try:
             writer.close()
        except:
             pass 
             
    output.seek(0)
    
    filename = "sportolo_import_sablon.xlsx"
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# --- NEW VIEW 2: Athlete Import ---
@login_required
@role_required('Edző')
@transaction.atomic
def import_placeholder_athletes(request):
    """
    Tömeges sportoló importálása Excel fájlból a PlaceholderAthlete modellbe.
    """
    coach_user = request.user
    
    # FIGYELEM: A PlaceholderAthleteImportForm importálva kell, hogy legyen az assessment appból!
    if request.method == 'POST':
        form = PlaceholderAthleteImportForm(request.POST, request.FILES, coach_user=coach_user)
        
        if form.is_valid():
            uploaded_file = request.FILES['file']
            target_club = form.cleaned_data['club']
            target_sport = form.cleaned_data['sport']
            
            if not uploaded_file.name.endswith('.xlsx'):
                messages.error(request, "Csak .xlsx formátumú Excel fájlok engedélyezettek.")
                return redirect('data_sharing:import_placeholder_athletes')
            
            try:
                df = pd.read_excel(uploaded_file, sheet_name='Sportolók')
            except Exception as e:
                messages.error(request, f"Hiba az Excel fájl olvasása során: Ellenőrizze a 'Sportolók' munkalap nevét és a fájl sértetlenségét. ({e})")
                return redirect('data_sharing:import_placeholder_athletes')

            # Oszlopok átnevezése
            df.rename(columns={
                'Vezetéknév (required)': 'first_name',
                'Keresztnév (required)': 'last_name',
                'Születési dátum (YYYY-MM-DD)': 'birth_date',
                'Nem (M - Férfi, F - Nő)': 'gender',
            }, inplace=True)
            
            required_cols = ['last_name', 'first_name', 'birth_date', 'gender']
            if not all(col in df.columns for col in required_cols):
                messages.error(request, "A fájl nem tartalmazza az összes szükséges oszlopot. Kérem, töltse le újra a sablont.")
                return redirect('data_sharing:import_placeholder_athletes')

            imported_count = 0
            error_rows = []
            
            # Adatok feldolgozása
            for index, row in df.iterrows():
                try:
                    # Tisztítjuk a neveket a felesleges szóköztől (.strip())
                    last_name = str(row['last_name']).strip()   # Tisztítás hozzáadva
                    first_name = str(row['first_name']).strip() # Tisztítás hozzáadva

                    # Validáció
                    if pd.isna(last_name) or pd.isna(first_name) or not last_name or not first_name: # Üres string ellenőrzés hozzáadva
                        error_rows.append(f"Sor {index+2}: Hiányzó vezetéknév vagy keresztnév.")
                        continue
                    
                    birth_date = None
                    if isinstance(row['birth_date'], (datetime, date)):
                        birth_date = row['birth_date'].date() if isinstance(row['birth_date'], datetime) else row['birth_date']
                    elif pd.isna(row['birth_date']):
                        error_rows.append(f"Sor {index+2}: Hiányzó születési dátum.")
                        continue
                    else:
                        birth_date_dt = pd.to_datetime(row['birth_date'], errors='coerce')
                        if pd.isna(birth_date_dt):
                            error_rows.append(f"Sor {index+2}: Érvénytelen születési dátum formátum.")
                            continue
                        birth_date = birth_date_dt.date()

                    gender_code = str(row['gender']).strip().upper()
                    if gender_code not in ['M', 'F']:
                         error_rows.append(f"Sor {index+2}: Érvénytelen Nem kód (csak M vagy F).")
                         continue
                    
                    # PlaceholderAthlete objektum létrehozása
                    PlaceholderAthlete.objects.create( 
                        club=target_club,
                        sport=target_sport,
                        last_name=row['last_name'],
                        first_name=row['first_name'],
                        birth_date=birth_date,
                        gender=gender_code,
                    )
                    imported_count += 1
                
                except IntegrityError:
                    error_rows.append(f"Sor {index+2}: Integritási hiba (pl. valószínűleg már létezik ez a sportoló).")
                except Exception as e:
                    error_rows.append(f"Sor {index+2}: Feldolgozási hiba ({e}).")

            # Visszajelzések
            if error_rows:
                error_message = f"Sikeresen importált sportolók száma: {imported_count}. A következő sorok hibát tartalmaztak (max. 10): \n" + "\n".join(error_rows[:10])
                messages.error(request, error_message)
            
            if imported_count > 0 and not error_rows:
                messages.success(request, f"{imported_count} sportoló sikeresen importálva!")
            
            if imported_count > 0 and error_rows:
                messages.warning(request, f"{imported_count} sportoló importálva. Néhány hiba történt a többi sor feldolgozása során.")

            if imported_count == 0 and error_rows:
                 return redirect('data_sharing:import_placeholder_athletes')
            
            return redirect('data_sharing:coach_dashboard') 
            
    else:
        # GET kéréshez: Import űrlap megjelenítése
        form = PlaceholderAthleteImportForm(coach_user=coach_user)

    context = {
        'form': form,
        'page_title': "Sportoló Importálása (Tömeges felvitel)"
    }
    return render(request, "data_sharing/coach/import_placeholder_athletes.html", context)

@login_required
@role_required('Edző')
def create_training_session(request):
    """
    Form a TrainingSession (edzéshívás) létrehozásához.
    """
    # Ide jön majd a Django Form kezelése: TrainingSessionForm
    context = {'page_title': "Új Edzéshívás Létrehozása"}
    return render(request, "data_sharing/coach/create_training_session.html", context)


@login_required
@role_required('Edző')
def manage_attendance(request, session_id):
    """
    Edzés Jelenlét manuális rögzítése/módosítása.
    """
    # Ide jön a TrainingSession lekérdezése és az Attendance Formset kezelése
    context = {'page_title': "Jelenlét Vezetése"}
    return render(request, "data_sharing/coach/manage_attendance.html", context)


@login_required
@role_required('Edző')
def import_attendance_excel(request, session_id):
    """
    Edzés Jelenlét importálása Excel (vagy CSV) fájlból.
    """
    # Itt kezeljük a fájlfeltöltést, a Pandas bevonásával az adatok feldolgozásához
    context = {'page_title': "Jelenlét Importálása (Excel)"}
    return render(request, "data_sharing/coach/import_attendance_excel.html", context)


@login_required
@role_required('Edző')
def add_physical_assessment(request):
    """
    Form edzői felmérések (PhysicalAssessment) rögzítéséhez.
    """
    # Ide jön majd a Django Form kezelése: PhysicalAssessmentForm
    context = {'page_title': "Fizikai Felmérés Rögzítése"}
    return render(request, "data_sharing/coach/add_physical_assessment.html", context)

@login_required
@role_required('Edző')
def manage_schedules(request):
    """
    Összes Edzésrend, Szünet lista. A következő 5 edzés és az elmúlt 30 nap elmulasztott alkalmai
    jelennek meg (UX javítás).
    """
    # Feltételezés: a date.today() és a Q importálva van a fájl elején.
    coach = request.user
    today = date.today() # Az aktuális dátum

    # A coach-hoz tartozó aktív klub/sport párosítások lekérdezése
    active_roles = UserRole.objects.filter(
        user=coach, 
        role__name='Edző', 
        status='approved'
    ).select_related('club', 'sport')
    
    # ----------------------------------------------------------------------
    # Edzésrend szűrés
    # ----------------------------------------------------------------------
    
    schedule_filter = Q()
    # Összeállítjuk a szűrési feltételeket: (Club ID ÉS Sport ID)
    for role in active_roles:
        if role.club and role.sport:
            schedule_filter |= Q(club_id=role.club.id, sport_id=role.sport.id)

    # Csak az engedélyezett klub/sport párosítások edzésrendjei
    schedules_qs = TrainingSchedule.objects.filter(
        schedule_filter
    ).select_related('club', 'sport', 'coach__profile').order_by('club__name', 'sport__name', 'days_of_week', 'start_time')
    
    schedules_with_sessions = []
    
    for schedule in schedules_qs:
        # Kiszámoljuk az elmúlt 30 nap edzéseit ÉS a következő 5 jövőbeli edzést (UX javítás)
        next_sessions = calculate_next_training_sessions(
            schedule.id, 
            schedule.club_id, 
            future_limit=5, # Következő 5 jövőbeli EDZÉS (nem szünet)
            past_days=30    # Utolsó 30 nap összes alkalma
        )

        for session in next_sessions:
            # Szünetek esetén nincs szükség státuszellenőrzésre
            if session.get('is_absence', False): 
                continue 
            
            session_date = session['date']
            
            # 1. Megkeressük a TrainingSession-t (A link generálásához szükség van rá, de nem kötelező a státuszhoz)
            training_session = TrainingSession.objects.filter(
                coach=schedule.coach, 
                session_date=session_date, 
                start_time=schedule.start_time 
            ).first()
            
            # 2. JELENLÉT ELLENŐRZÉSE (FIXED: Közvetlen szűrés az Attendance táblán)
            # Ez a fix garantálja, hogy a zöld pipa akkor is megjelenjen, ha a TrainingSession 
            # adatai helyesek, függetlenül a tranzakciós/creation logikától.
            has_attendance = Attendance.objects.filter(
                session__session_date=session_date,
                session__start_time=schedule.start_time,
                is_present=True
            ).exists()
            
            # 3. Hozzáadjuk a státuszokat a session dict-hez
            session['is_recorded'] = has_attendance # Zöld pipa
            
            # Sárga felkiáltójel: Akkor elmulasztott, ha a dátum már ELMÚLT ÉS NINCS rögzítve.
            session['is_missed'] = (session_date < today) and (not has_attendance) 
        
        # Edző teljes nevének formázása
        full_coach_name = (
            f"{schedule.coach.profile.first_name} {schedule.coach.profile.last_name}"
            if schedule.coach and hasattr(schedule.coach, 'profile') and schedule.coach.profile.last_name
            else schedule.coach.username if schedule.coach else "Nincs megadva"
        )
        
        schedules_with_sessions.append({
            'schedule': schedule,
            'next_sessions': next_sessions, # A kibővített listát adjuk át
            'full_coach_name': full_coach_name 
        })
    
    # ----------------------------------------------------------------------
    # Szünetek / Leállások lekérdezése (Helyreállítva!)
    # ----------------------------------------------------------------------
    # Azok a szünetek is látszódjanak, amelyek az edző bármely klubjára vonatkoznak, VAGY globálisak.
    allowed_club_ids = active_roles.values_list('club_id', flat=True).distinct()
    absences = AbsenceSchedule.objects.filter(
        Q(club__isnull=True) | Q(club_id__in=allowed_club_ids)
    ).select_related('club').order_by('start_date')

    context = {
        'schedules': schedules_with_sessions, 
        'absences': absences,
        'page_title': "Edzésrend & Szünetek Kezelése",
    }
    return render(request, "data_sharing/coach/manage_schedules.html", context)


@login_required
@role_required('Edző')
def add_schedule(request):
    """
    Edzésrend felvitele.
    """
    if request.method == 'POST':
        form = TrainingScheduleForm(request.POST, coach_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Edzésrend sikeresen rögzítve.")
            return redirect('data_sharing:manage_schedules')
    else:
        form = TrainingScheduleForm(coach_user=request.user)
        
    context = {
        'form': form,
        'page_title': "Új Edzésrend Felvitele"
    }
    return render(request, "data_sharing/coach/add_schedule.html", context)

@login_required
@role_required('Edző')
def edit_schedule(request, pk): # <-- A view PK-t vár, használjuk a belső kódban is
    # 1. Edzésrend objektum betöltése
    try:
        schedule = TrainingSchedule.objects.get(pk=pk) # <-- schedule_id helyett PK!
    except TrainingSchedule.DoesNotExist:
        # Ha az ID nem létezik
        raise Http404("Az edzésrend nem található.") # <-- Most már definiálva van
        
    # 2. JOGOSULTSÁG ELLENŐRZÉSE
    
    # Elérhető klubok és sportágak lekérése
    # Most már definiálva van
    clubs, sports = get_coach_clubs_and_sports(request.user) 
    
    is_owner = schedule.coach == request.user # Az edző a rögzítő
    is_club_coach = schedule.club in clubs and schedule.sport in sports # Az edző jogosult a klubban/sportágban
    
    if not (is_owner or is_club_coach):
         # Ha se nem a rögzítő, se nem jogosult abban a klubban/sportágban
        messages.error(request, "Nincs jogosultságod az edzésrend szerkesztéséhez.")
        # Győződj meg róla, hogy a 'data_sharing:manage_schedules' URL név a helyes!
        return redirect('data_sharing:manage_schedules') 

    # 3. Form betöltése és kezelése
    if request.method == 'POST':
        form = TrainingScheduleForm(request.POST, instance=schedule, coach_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Az edzésrend ({schedule.name}) sikeresen módosítva.")
            return redirect('data_sharing:manage_schedules')
    else:
        form = TrainingScheduleForm(instance=schedule, coach_user=request.user)

    context = {
        'form': form,
        'page_title': "Edzésrend Módosítása",
        'schedule': schedule
    }
    return render(request, "data_sharing/coach/edit_schedule.html", context) # Ezt a sablont még létre kell hozni!

@login_required
@role_required('Edző')
def delete_schedule(request, pk):
    schedule = get_object_or_404(TrainingSchedule, pk=pk)
    
    allowed_club_ids = request.user.user_roles.filter(
        role__name='Edző', 
        status='approved'
    ).values_list('club_id', flat=True)
    
    if schedule.club_id not in allowed_club_ids:
        messages.error(request, "Nincs jogosultságod ezen edzésrend törlésére.")
        return redirect('data_sharing:manage_schedules')

    if request.method == 'POST':
        schedule.delete()
        messages.success(request, f"Az edzésrend ({schedule.name}) sikeresen törölve.")
        return redirect('data_sharing:manage_schedules')

    context = {
        'page_title': "Edzésrend Törlése",
        'schedule': schedule
    }
    # Ez egy egyszerű megerősítő oldal lesz (vagy egy modal)
    return render(request, "data_sharing/coach/delete_confirmation.html", context) 

# --- Szünetek Kezelés (CRUD) ---
@login_required
@role_required('Edző')
def add_absence(request):
    """
    Szünet/Leállás felvitele.
    """
    if request.method == 'POST':
        form = AbsenceScheduleForm(request.POST, coach_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Szünet sikeresen rögzítve.")
            return redirect('data_sharing:manage_schedules')
    else:
        form = AbsenceScheduleForm(coach_user=request.user)
        
    context = {
        'form': form,
        'page_title': "Új Szünet/Leállás Felvitele"
    }
    return render(request, "data_sharing/coach/add_absence.html", context)

@login_required
@role_required('Edző')
def edit_absence(request, pk):
    absence = get_object_or_404(AbsenceSchedule, pk=pk)
    
    # Jogosultság ellenőrzés: Globális vagy a saját klubjához tartozót módosíthatja
    allowed_club_ids = request.user.user_roles.filter(
        role__name='Edző', 
        status='approved'
    ).values_list('club_id', flat=True)
    
    if absence.club is not None and absence.club_id not in allowed_club_ids:
        messages.error(request, "Nincs jogosultságod ezen szünet módosítására.")
        return redirect('data_sharing:manage_schedules')

    if request.method == 'POST':
        form = AbsenceScheduleForm(request.POST, instance=absence, coach_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"A szünet ({absence.name}) sikeresen módosítva.")
            return redirect('data_sharing:manage_schedules')
    else:
        form = AbsenceScheduleForm(instance=absence, coach_user=request.user)

    context = {
        'form': form,
        'page_title': "Szünet Módosítása",
        'absence': absence
    }
    return render(request, "data_sharing/coach/add_absence.html", context) # Az add_absence sablont újrahasznosíthatjuk!

@login_required
@role_required('Edző')
def delete_absence(request, pk):
    absence = get_object_or_404(AbsenceSchedule, pk=pk)
    
    allowed_club_ids = request.user.user_roles.filter(
        role__name='Edző', 
        status='approved'
    ).values_list('club_id', flat=True)

    if absence.club is not None and absence.club_id not in allowed_club_ids:
        messages.error(request, "Nincs jogosultságod ezen szünet törlésére.")
        return redirect('data_sharing:manage_schedules')

    if request.method == 'POST':
        absence.delete()
        messages.success(request, f"A szünet ({absence.name}) sikeresen törölve.")
        return redirect('data_sharing:manage_schedules')

    context = {
        'page_title': "Szünet Törlése",
        'absence': absence
    }
    # Ezt a sablont is létre kell hozni!
    return render(request, "data_sharing/coach/delete_confirmation.html", context)

# --- Jelenléti ív ---

@login_required
@role_required('Edző') # Csak Edző engedélyezett
@transaction.atomic
def record_attendance(request, schedule_pk, session_date):
    user = request.user # A bejelentkezett felhasználó
    
    # 1. Edzésrend és jogosultság ellenőrzése
    schedule = get_object_or_404(TrainingSchedule.objects.select_related('club', 'sport'), pk=schedule_pk)
    
    
    # Ellenőrizzük, hogy a felhasználó Edző-e az edzésrendhez tartozó KLUB/SPORTÁG pároson
    is_coach_of_schedule_group = user.user_roles.filter(
        role__name='Edző', 
        status='approved', 
        club=schedule.club, 
        sport=schedule.sport 
    ).exists()
    
    # Ha a felhasználó nem edző az adott csoportban, Nincs jogosultsága.
    if not is_coach_of_schedule_group:
        logger.warning(f"Jogosultsági hiba: Edző ({user.username}) megpróbálta elérni a {schedule.club.name}/{schedule.sport.name} edzés jelenléti ívét, amihez nincs engedélye.")
        raise Http404("Nincs jogosultságod ehhez az edzésrendhez.")

    # Mivel a követelmény az, hogy minden jogosult edző szerkeszthessen:
    can_edit = True 
       
    try:
        session_date_obj = datetime.strptime(session_date, '%Y-%m-%d').date()
    except ValueError:
        logger.error(f"Érvénytelen dátum formátum: {session_date}")
        raise Http404("Érvénytelen edzés dátum.")
        
    # Ellenőrzés: Az edzés napja megegyezik-e a schedule napjával
    day_of_week_model = session_date_obj.weekday() + 1
    if str(day_of_week_model) not in schedule.days_of_week.split(','):
        logger.warning(f"Hiba: A kiválasztott nap ({session_date}) nem tartozik a schedule ({schedule.days_of_week}) napjai közé.")
        raise Http404("A megadott napon nincs edzés az edzésrend szerint.")

    # 3. Edző lekérdezése    
    existing_session_query = TrainingSession.objects.filter(
        session_date=session_date_obj,
        start_time=schedule.start_time
        # Hozzáadhatunk szűrést a location-re/schedule.name-re is, ha az is egyedi azonosító
    )
    
    if existing_session_query.exists():
        # Ha létezik, használjuk az elsőt (a duplikációkat manuálisan törölni kell!)
        session = existing_session_query.first() 
        # Frissítjük a coach mezőt a jelenlegi edzőre (ez opcionális, de jelzi, ki szerkesztette utoljára)
        session.coach = user 
        session.save()
        created = False
    else:
        # Ha nem létezik, létrehozzuk (a jelenlegi edzővel)
        duration = (datetime.combine(date.today(), schedule.end_time) - datetime.combine(date.today(), schedule.start_time)).total_seconds() / 60
        session = TrainingSession.objects.create(
            coach=user,
            session_date=session_date_obj,
            start_time=schedule.start_time,
            duration_minutes=duration,
            location=schedule.name,
        )
        created = True

    # 3. Sportolók lekérdezése (Regisztrált és Placeholder)
    
    # Kiszámoljuk az engedélyezett születési éveket
    allowed_birth_years = [int(y.strip()) for y in schedule.birth_years.split(',') if y.strip()]
    allowed_genders = [g.strip() for g in schedule.genders.split(',') if g.strip()]
    
    current_year = date.today().year
    
    # Regisztrált sportolók lekérdezése:
    registered_athletes = User.objects.filter(
        # Szerep: Sportoló
        user_roles__role__name='Sportoló',
        user_roles__status='approved',
        # Klub és Sportág egyezés
        user_roles__club=schedule.club,
        user_roles__sport=schedule.sport,
    ).select_related('profile')

    # Sportolók szűrése év és nem szerint
    athlete_list = []
    for athlete in registered_athletes:
        
        # JAVÍTOTT KÓD
        # 1. Ellenőrizzük, hogy a date_of_birth mező nem None, és a gender be van-e állítva
        if athlete.profile.date_of_birth is not None and athlete.profile.gender:
            
            # 2. Kinyerjük a születési ÉVET a date_of_birth objektumból
            birth_year = athlete.profile.date_of_birth.year
            gender = athlete.profile.gender
            
            # Év és nem szerinti szűrés
            if birth_year in allowed_birth_years and gender in allowed_genders:
                # ... (a sportoló adatainak összeállítása, mint korábban)
                attendance = Attendance.objects.filter(session=session, registered_athlete=athlete).first()
                athlete_list.append({
                    'id': athlete.id,
                    'name': f"{athlete.profile.first_name} {athlete.profile.last_name}",
                    'type': 'registered',
                    'is_present': attendance.is_present if attendance else False,
                    'is_injured': attendance.is_injured if attendance else False, 
                    'is_guest': attendance.is_guest if attendance else False,  
                    'rpe_score': attendance.rpe_score if attendance else None,
                    'attendance_id': attendance.id if attendance else None,
                })

    # Ideiglenes sportolók (PlaceholderAthlete) lekérdezése:
        placeholder_athletes = PlaceholderAthlete.objects.filter(
            club=schedule.club,
            sport=schedule.sport,
            # birth_date__year__in=allowed_birth_years, # <-- IDEIGLENESEN KOMMENTEZZE KI EZT
            gender__in=allowed_genders,
        ).select_related('club', 'sport')
    
    for placeholder in placeholder_athletes:
        # Lekérdezzük, van-e már jelenléti rekord
        attendance = Attendance.objects.filter(session=session, placeholder_athlete=placeholder).first()
        athlete_list.append({
            'id': placeholder.id,
            'name': f" {placeholder.first_name} {placeholder.last_name}(PH)",
            'type': 'placeholder',
            'is_present': attendance.is_present if attendance else False,
            'is_injured': attendance.is_injured if attendance else False, 
            'is_guest': attendance.is_guest if attendance else False,  
            'rpe_score': attendance.rpe_score if attendance else None,
            'attendance_id': attendance.id if attendance else None,
        })
        
    # 4. POST kérés: Jelenlét mentése
    if request.method == 'POST':
        
        # Kezeljük le a jelenléti adatokat:
        for athlete_data in athlete_list:
            
            athlete_id = athlete_data['id']
            athlete_type = athlete_data['type']
            # A HTML-ben használt egyedi kulcs (pl. registered_4 vagy placeholder_1)
            unique_key = f"{athlete_type}_{athlete_id}"
            
            # A request.POST.get(...) csak akkor ad vissza '1'-et, ha a checkbox be van jelölve.
            is_present = request.POST.get(f'is_present_{unique_key}') == '1'
            is_injured = request.POST.get(f'is_injured_{unique_key}') == '1'
            is_guest = request.POST.get(f'is_guest_{unique_key}') == '1'
            
            # Sportoló objektum beszerzése és Attendance rekord kezelése
            if athlete_type == 'registered':
                athlete_obj = User.objects.get(id=athlete_id)
                filter_kwargs = {'session': session, 'registered_athlete': athlete_obj}
            
            elif athlete_type == 'placeholder':
                placeholder_obj = PlaceholderAthlete.objects.get(id=athlete_id)
                filter_kwargs = {'session': session, 'placeholder_athlete': placeholder_obj}
            
            # Minden típushoz
            defaults_kwargs = {
                'is_present': is_present,
                'is_injured': is_injured,
                'is_guest': is_guest,
                # ... egyéb default értékek ...
            }
            
            # Megkeressük vagy létrehozzuk az Attendance rekordot
            attendance, created = Attendance.objects.get_or_create(
                **filter_kwargs,
                defaults=defaults_kwargs
            )
            
            # Ha már létezett a rekord, csak frissítjük a mezőket
            if not created:
                # Frissítjük a lekérdezett állapotokat
                attendance.is_present = is_present
                attendance.is_injured = is_injured
                attendance.is_guest = is_guest
                # attendance.rpe_score = request.POST.get(f'rpe_{unique_key}') # RPE
                attendance.save()

        # Átirányítás a manage_schedules oldalra a mentés után
        return redirect('data_sharing:manage_schedules')


    # 5. GET kérés: Adatok előkészítése a sablonhoz
    context = {
        'schedule': schedule,
        'session_date': session_date_obj,
        'session': session,
        'athlete_list': athlete_list,
        'page_title': f"Jelenléti Ív: {schedule.name} ({session_date})",
        'can_edit': can_edit, # Mindig True, de bent hagyjuk a sablon miatt
    }
    
    return render(request, 'data_sharing/coach/record_attendance.html', context)