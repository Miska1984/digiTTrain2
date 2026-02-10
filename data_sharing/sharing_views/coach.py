# /app/data_sharing/sharing_views/coach.py 

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q, F  
from django.http import Http404, HttpResponse, FileResponse
from django.db import transaction, IntegrityError, models
from django import forms
from users.models import UserRole, User, Club, Sport
from users.utils import role_required, _check_user_role 
from biometric_data.models import WeightData, HRVandSleepData, RunningPerformance, WorkoutFeedback
from assessment.models import PlaceholderAthlete, PhysicalAssessment
from assessment.forms import PlaceholderAthleteForm, PlaceholderAthleteImportForm
from training_log.models import TrainingSession, Attendance, TrainingSchedule, AbsenceSchedule
from training_log.forms import TrainingScheduleForm, AbsenceScheduleForm, TrainingSessionForm
from training_log.utils import get_attendance_summary, TIME_PERIODS, calculate_next_training_sessions
from data_sharing.models import DataSharingPermission
from datetime import date, datetime, time
from users.models import User, UserRole, ParentChild
from users.utils import get_coach_clubs_and_sports
import logging
import pandas as pd
import io 
import calendar
import json
from django.core.serializers.json import DjangoJSONEncoder
from biometric_data.analytics import (
    generate_weight_feedback, 
    generate_hrv_sleep_feedback
)
from diagnostics_jobs.models import DiagnosticJob
from ml_engine.models import UserFeatureSnapshot

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
    coach = request.user
    
    # 1. Lekérjük az edzőhöz tartozó jóváhagyott sportolókat
    athlete_roles = UserRole.objects.filter(
        coach=coach,
        status='approved'
    ).exclude(role__name__in=['Szülő', 'Edző', 'Egyesületi vezető']).select_related('user__profile', 'club', 'sport')

    athletes_data = []
    for role in athlete_roles:
        athlete = role.user
        is_adult = athlete.is_adult
        
        # 2. Engedélyek lekérése - EGYSZERŰSÍTVE
        # Nem szűrünk a target_role-ra, mert a személy (target_person) a lényeg
        permissions_qs = DataSharingPermission.objects.filter(
            athlete=athlete,
            target_person=coach,
            athlete_consent=True
        )
        
        # Ha kiskorú, kell a szülői beleegyezés is
        if not is_adult:
            permissions_qs = permissions_qs.filter(parent_consent=True)
            
        # Alakítsuk listává a táblaneveket az ikonokhoz
        permissions = list(permissions_qs.values_list('table_name', flat=True))
        
        # 3. Adatok lekérése a dashboardhoz
        last_weight = WeightData.objects.filter(user=athlete).order_by('-workout_date').first()
        
        attendance_stats = None
        if 'Attendance' in permissions:
            from training_log.utils import get_attendance_summary
            attendance_stats = get_attendance_summary(athlete, days=30)
        
        ditta_score = None
        if 'UserFeatureSnapshot' in permissions:
            ditta_score = UserFeatureSnapshot.objects.filter(user=athlete).order_by('-generated_at').first()

        athletes_data.append({
            'athlete_object': athlete,
            'profile_data': athlete.profile,
            'athlete_club': role.club,
            'athlete_sport': role.sport,
            'role_id': role.id, 
            'athlete_id': athlete.id,
            'athlete_type': 'adult' if is_adult else 'junior', 
            'last_weight': last_weight,
            'permissions': permissions,
            'attendance_stats': attendance_stats,
            'ditta_score': ditta_score,
        })
            
    context = {
        'page_title': 'Sportolóim Áttekintője',
        'athletes_data': athletes_data,
    }
    return render(request, 'data_sharing/coach/coach_dashboard.html', context)

@login_required
def coach_athlete_details(request, athlete_id, role_id):
    """
    Részletes nézet egy sportoló adatairól az edző számára.
    """
    coach = request.user
    athlete = get_object_or_404(User, id=athlete_id)
    role = get_object_or_404(UserRole, id=role_id, coach=coach)

    # Engedélyek ellenőrzése (athlete_consent + ha kiskorú, akkor parent_consent)
    permissions_qs = DataSharingPermission.objects.filter(
        athlete=athlete,
        target_person=coach,
        athlete_consent=True
    )

    if not athlete.is_adult:
        permissions_qs = permissions_qs.filter(parent_consent=True)
    
    # Nézzük meg, maradt-e bármilyen engedélyünk
    if not permissions_qs.exists():
        # Itt dob vissza, ha valami nem stimmel
        from django.contrib import messages
        messages.warning(request, f"Nincs érvényes, jóváhagyott engedélyed {athlete.get_full_name()} adataihoz.")
        return redirect('data_sharing:coach_dashboard')

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

    return render(request, 'data_sharing/coach/athlete_details.html', context)

# --- Edzés rendezési nézetek---

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

class AttendanceExportForm(forms.Form):
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), label="Kezdő dátum")
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), label="Befejező dátum")

def get_attendance_status(attendance):
    """Jelenléti rekord alapján visszaadja az Excel kódokat."""
    if not attendance or not attendance.is_present:
        if attendance:
            if attendance.is_injured:
                return "S"  # Sérült
            if attendance.is_guest:
                return "V"  # Vendég
        return "H"  # Hiányzik
    if attendance.is_guest:
        return "V"
    if attendance.is_injured:
        return "S"
    return "J"  # Jelen

@login_required
@role_required("Edző")
def export_attendance_report(request, club_pk, sport_pk, start_date_str, end_date_str):
    coach = request.user

    # --- 1. Klub / Sport ---
    club = get_object_or_404(Club, pk=club_pk)
    sport = get_object_or_404(Sport, pk=sport_pk)

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except ValueError:
        messages.error(request, "Érvénytelen dátumformátum (YYYY-MM-DD).")
        return redirect("data_sharing:coach_dashboard")

    # --- 2. Jogosultság ---
    is_coach_of_group = coach.user_roles.filter(
        role__name="Edző", status="approved", club_id=club_pk, sport_id=sport_pk
    ).exists()
    if not is_coach_of_group:
        messages.error(request, "Nincs jogosultságod ehhez a jelentéshez.")
        return redirect("data_sharing:coach_dashboard")

    # --- 3. Edzésszessionök ---
    sessions = (
        TrainingSession.objects.filter(
            session_date__range=(start_date, end_date),
            coach__user_roles__club_id=club_pk,
            coach__user_roles__sport_id=sport_pk,
            coach__user_roles__role__name="Edző",
            coach__user_roles__status="approved",
        )
        .order_by("session_date", "start_time")
        .distinct()
    )
    sessions_list = list(sessions)
    total_sessions = len(sessions_list)
    if not sessions_list:
        messages.error(request, "A feltételeknek megfelelő edzések nem találhatók a megadott időszakban.")
        return redirect("data_sharing:attendance_export_form", club_pk=club_pk, sport_pk=sport_pk)

    # --- 4. Jelenléti rekordok ---
    attendance_records = Attendance.objects.filter(session__in=sessions).select_related(
        "registered_athlete__profile", "placeholder_athlete", "session"
    )

    # --- 5. Sportolók (User + Placeholder) ---
    athlete_map = {}
    registered_athletes = (
        User.objects.filter(
            user_roles__role__name="Sportoló",
            user_roles__status="approved",
            user_roles__club_id=club_pk,
            user_roles__sport_id=sport_pk,
        )
        .select_related("profile")
        .distinct()
    )
    for athlete in registered_athletes:
        athlete_map[f"r_{athlete.id}"] = {
            "id": athlete.id,
            "type": "registered",
            "name": f"{athlete.profile.first_name} {athlete.profile.last_name} ",
            "birth_year": athlete.profile.date_of_birth.year if athlete.profile.date_of_birth else "N/A",
        }

    placeholder_athletes = PlaceholderAthlete.objects.filter(club_id=club_pk, sport_id=sport_pk)
    for ph in placeholder_athletes:
        athlete_map[f"p_{ph.id}"] = {
            "id": ph.id,
            "type": "placeholder",
            "name": f"{ph.first_name} {ph.last_name} (PH)",
            "birth_year": ph.birth_date.year if ph.birth_date else "N/A",
        }

    athlete_list = sorted(athlete_map.values(), key=lambda x: x["name"])

    # --- 6. Táblázat adatok ---
    session_cols = [f"{s.session_date.strftime('%m-%d')} {s.start_time.strftime('%H:%M')}" for s in sessions_list]
    columns = ["Név", "Születési Év"] + session_cols + ["Összes Edzés", "Jelen (J)", "Sérült (S)", "Vendég (V)", "Hiányzott (H)"]

    data = []
    for athlete_data in athlete_list:
        row = {"Név": athlete_data["name"], "Születési Év": athlete_data["birth_year"]}
        total_present = total_injured = total_guest = 0

        if athlete_data["type"] == "registered":
            athlete_attendance = {
                att.session_id: att for att in attendance_records if att.registered_athlete_id == athlete_data["id"]
            }
        else:
            athlete_attendance = {
                att.session_id: att for att in attendance_records if att.placeholder_athlete_id == athlete_data["id"]
            }

        for session in sessions_list:
            att = athlete_attendance.get(session.id)
            status_code = get_attendance_status(att)
            if status_code == "J":
                total_present += 1
            elif status_code == "S":
                total_injured += 1
            elif status_code == "V":
                total_guest += 1
            row[f"{session.session_date.strftime('%m-%d')} {session.start_time.strftime('%H:%M')}"] = status_code

        total_attended = total_present + total_injured + total_guest
        total_absent = total_sessions - total_attended
        row["Összes Edzés"] = total_sessions
        row["Jelen (J)"] = f"{total_present} alk."
        row["Sérült (S)"] = f"{total_injured} alk."
        row["Vendég (V)"] = f"{total_guest} alk."
        row["Hiányzott (H)"] = f"{total_absent} alk."
        data.append(row)

    df = pd.DataFrame(data, columns=columns)

    # --- 7. Excel generálás ---
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        sheet_name = f"Jelenlét_{start_date.strftime('%Y%m')}-{end_date.strftime('%Y%m')}"
        df.to_excel(writer, sheet_name=sheet_name, startrow=6, index=False)

        workbook = writer.book
        worksheet = writer.sheets[sheet_name]

        # --- Fejléc formátum ---
        header_format = workbook.add_format({"bold": True, "font_size": 14, "align": "center"})
        info_format = workbook.add_format({"font_size": 10, "align": "left"})
        footer_format = workbook.add_format({"italic": True, "align": "center"})

        # Klubvezető neve
        club_leader_role = UserRole.objects.filter(
            role__name="Egyesületi vezető", club=club, status="approved"
        ).select_related("user__profile").first()
        leader_name = f"{club_leader_role.user.profile.first_name} {club_leader_role.user.profile.last_name}" if club_leader_role else "Nincs megadva"

        # Edzők neve
        coaches_qs = UserRole.objects.filter(
            role__name="Edző", status="approved", club_id=club_pk, sport_id=sport_pk
        ).select_related("user__profile")
        coach_names = ", ".join([f"{c.user.profile.first_name} {c.user.profile.last_name}" for c in coaches_qs])

        # Fejléc írása
        worksheet.merge_range("A1:D1", f"Egyesület: {club.name} / {sport.name}", header_format)
        worksheet.write("A2", "Cím:", info_format)
        worksheet.write("B2", club.address, info_format)
        worksheet.write("A3", "Vezető:", info_format)
        worksheet.write("B3", leader_name, info_format)
        worksheet.write("A4", "Edző(k):", info_format)
        worksheet.write("B4", coach_names if coach_names else coach.get_full_name(), info_format)

        # Időszak
        worksheet.merge_range("A6:F6", f"Jelentési időszak: {start_date_str} - {end_date_str}", header_format)

        # --- Lábléc ---
        footer_row = len(df) + 9
        worksheet.merge_range(footer_row, 0, footer_row, len(columns) - 1, "Készült a digiTTrain2025 programmal.", footer_format)
        worksheet.merge_range(footer_row + 1, 0, footer_row + 1, len(columns) - 1, "DigiTTrain Logó Helye", footer_format)

    output.seek(0)

    # --- 8. FileResponse ---
    file_name = f"Jelenléti_ív_{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}_{club.short_name}.xlsx"
    return FileResponse(output, as_attachment=True, filename=file_name)

@login_required
@role_required('Edző')
def attendance_export_form(request, club_pk, sport_pk):
    # Feltételezve, hogy a Club és Sport modellek importálva vannak
    club = get_object_or_404(Club, pk=club_pk)
    sport = get_object_or_404(Sport, pk=sport_pk)

    if request.method == 'POST':
        form = AttendanceExportForm(request.POST)
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            
            # Átirányítás az exportáló nézetre (ami a következő lépésben frissül)
            return redirect('data_sharing:export_attendance_report', 
                            club_pk=club_pk, 
                            sport_pk=sport_pk, 
                            start_date_str=start_date.strftime('%Y-%m-%d'), 
                            end_date_str=end_date.strftime('%Y-%m-%d'))
    else:
        # Alapértelmezett dátumok beállítása (pl. az aktuális hónap)
        today = date.today()
        default_start = today.replace(day=1)
        default_end = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
        form = AttendanceExportForm(initial={'start_date': default_start, 'end_date': default_end})
        
    context = {
        'form': form,
        'club': club,
        'sport': sport,
        'page_title': f"Jelenléti ív exportálása - {club.short_name} {sport.name}",
        'club_pk': club_pk,
        'sport_pk': sport_pk,
    }
    return render(request, 'data_sharing/coach/attendance_export_form.html', context)

@login_required
@role_required('Edző')
def add_physical_assessment(request):
    """
    Form edzői felmérések (PhysicalAssessment) rögzítéséhez.
    """
    # Ide jön majd a Django Form kezelése: PhysicalAssessmentForm
    context = {
        'page_title': "Fizikai Felmérés Rögzítése", 
        'app_context': 'physical_assessment_list',
    }
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
        'app_context': 'manage_schedules',
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
        'page_title': "Új Edzésrend Felvitele",
        'app_context': 'manage_schedules',
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
        'schedule': schedule, 
        'app_context': 'manage_schedules',
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
@role_required('Edző')
@transaction.atomic
def record_attendance(request, schedule_pk, session_date):
    user = request.user
    
    # 1. Edzésrend és jogosultság ellenőrzése
    schedule = get_object_or_404(TrainingSchedule.objects.select_related('club', 'sport'), pk=schedule_pk)
    
    is_coach_of_schedule_group = user.user_roles.filter(
        role__name='Edző', 
        status='approved', 
        club=schedule.club, 
        sport=schedule.sport 
    ).exists()
    
    if not is_coach_of_schedule_group:
        logger.warning(f"Jogosultsági hiba: Edző ({user.username}) megpróbálta elérni a {schedule.club.name}/{schedule.sport.name} edzését.")
        raise Http404("Nincs jogosultságod ehhez az edzésrendhez.")

    try:
        session_date_obj = datetime.strptime(session_date, '%Y-%m-%d').date()
    except ValueError:
        raise Http404("Érvénytelen edzés dátum.")
        
    # 2. Edzés (Session) lekérdezése vagy létrehozása
    existing_session_query = TrainingSession.objects.filter(
        session_date=session_date_obj,
        start_time=schedule.start_time,
        schedule=schedule
    )
    
    session_is_new = False # Segédváltozó az előző betöltéséhez
    
    if existing_session_query.exists():
        session = existing_session_query.first() 
        session.coach = user 
        session.save()
    else:
        session_is_new = True # Jelezzük, hogy most hozzuk létre
        duration = (datetime.combine(date.today(), schedule.end_time) - datetime.combine(date.today(), schedule.start_time)).total_seconds() / 60
        session = TrainingSession.objects.create(
            coach=user,
            schedule=schedule,
            session_date=session_date_obj,
            start_time=schedule.start_time,
            duration_minutes=int(duration),
            location=schedule.name,
        )

    # --- ÚJ: ELŐZŐ EDZÉS ADATAINAK BETÖLTÉSE ---
    # Ha a session új, vagy még teljesen üres (minden 0), megpróbáljuk betölteni a legutóbbit
    if session_is_new or (session.warmup_duration == 0 and session.technical_duration == 0):
        last_session = TrainingSession.objects.filter(
            schedule=schedule,
            session_date__lt=session_date_obj
        ).order_by('-session_date', '-id').first()

        if last_session:
            # Csak azokat az értékeket másoljuk át, amik a felosztáshoz kellenek
            session.warmup_duration = last_session.warmup_duration
            session.is_warmup_playful = last_session.is_warmup_playful
            session.technical_duration = last_session.technical_duration
            session.tactical_duration = last_session.tactical_duration
            session.game_duration = last_session.game_duration
            session.cooldown_duration = last_session.cooldown_duration
            session.toy_duration = last_session.toy_duration
            # Fontos: itt még NEM hívunk session.save()-et, hogy ne szemeteljük tele az adatbázist, 
            # ha az edző csak benéz az oldalra, de nem ment semmit.
    # --- ÚJ RÉSZ VÉGE ---

    # --- Form inicializálása ---
    from training_log.forms import TrainingSessionForm
    if request.method == 'POST':
        session_form = TrainingSessionForm(request.POST, instance=session)
    else:
        session_form = TrainingSessionForm(instance=session)

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
        
    # 4. POST kérés: Mentés
    if request.method == 'POST':
        # Fontos: Újra inicializáljuk a formot a POST adatokkal
        session_form = TrainingSessionForm(request.POST, instance=session)
        
        if session_form.is_valid():
            # Itt történik az adatbázisba írás (warmup_duration stb.)
            session = session_form.save() 
            logger.info(f"Szakmai felosztás mentve: {session.id}")
        else:
            # Ha ide belép, látni fogod a terminálban a hibát
            print("FORM HIBA:", session_form.errors)

        # Jelenlét mentése (a sportolók listája)
        for athlete_data in athlete_list:
            athlete_id = athlete_data['id']
            athlete_type = athlete_data['type']
            unique_key = f"{athlete_type}_{athlete_id}"
            
            is_present = request.POST.get(f'is_present_{unique_key}') == '1'
            is_injured = request.POST.get(f'is_injured_{unique_key}') == '1'
            is_guest = request.POST.get(f'is_guest_{unique_key}') == '1'
            
            if athlete_type == 'registered':
                filter_kwargs = {'session': session, 'registered_athlete_id': athlete_id}
            else:
                filter_kwargs = {'session': session, 'placeholder_athlete_id': athlete_id}

            Attendance.objects.update_or_create(
                **filter_kwargs,
                defaults={
                    'is_present': is_present,
                    'is_injured': is_injured,
                    'is_guest': is_guest,
                }
            )

        messages.success(request, "Sikeres mentés!")
        return redirect('data_sharing:manage_schedules')

    # 5. GET kérés: Renderelés
    context = {
        'schedule': schedule,
        'session_date': session_date_obj,
        'session': session,
        'session_form': session_form, # <--- Átadjuk a sablonnak!
        'athlete_list': athlete_list,
        'page_title': f"Jelenléti Ív: {schedule.name}",
        'can_edit': True,
        'app_context': 'attendance_sheet',

    }
    
    return render(request, 'data_sharing/coach/record_attendance.html', context)