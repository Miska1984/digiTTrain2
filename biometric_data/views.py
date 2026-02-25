# biometric_data/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from datetime import date
import json
from .forms import (
    MorningWeightDataForm, HRVandSleepDataForm, 
    AfterTrainingWeightForm, AfterTrainingFeedbackForm,
    OccasionalWeightForm, OccasionalFeedbackForm, RunningPerformanceForm 
)
from .models import WeightData, HRVandSleepData, WorkoutFeedback, RunningPerformance
from django.db.models import Avg, Max, Min, Q
from users.models import UserRole
from datetime import date, timedelta
from django.utils import timezone
from django.utils.timezone import now
from django.shortcuts import get_object_or_404

# *** ÚJ IMPORT *** A logikát most már az analytics.py-ból vesszük!
from .analytics import (
    generate_weight_feedback, 
    generate_timing_feedback, 
    generate_hrv_sleep_feedback,
    generate_running_feedback
)
from ml_engine.ai_coach_service import DittaCoachService
ditta_service = DittaCoachService()

# -------------------- 1. Reggeli Mérések (morning_check) --------------------
@login_required
def morning_check(request):
    today = date.today()
    weight_instance = WeightData.objects.filter(user=request.user, workout_date=today).first()
    hrv_instance = HRVandSleepData.objects.filter(user=request.user, recorded_at=today).first()

    if weight_instance or hrv_instance:
        title = 'Reggeli Mérések Módosítása'
        action_message = 'módosítva'
    else:
        title = 'Reggeli Mérések Felvétele'
        action_message = 'rögzítve'

    if request.method == 'POST':
        weight_form = MorningWeightDataForm(request.POST, instance=weight_instance)
        hrv_form = HRVandSleepDataForm(request.POST, instance=hrv_instance)
        
        if weight_form.is_valid() and hrv_form.is_valid():
            is_weight_filled = any(weight_form.cleaned_data.values())
            is_hrv_filled = any(hrv_form.cleaned_data.values())

            if is_weight_filled or is_hrv_filled:
                if is_weight_filled:
                    w_data = weight_form.save(commit=False)
                    w_data.user = request.user
                    w_data.save()
                
                if is_hrv_filled:
                    h_data = hrv_form.save(commit=False)
                    h_data.user = request.user
                    h_data.save()
                
                # --- DITTA ANALÍZIS A MENTÉS UTÁN ---
                analysis_query = "Most rögzítettem ezeket: "
                if is_weight_filled: analysis_query += f"Súly: {weight_form.cleaned_data['morning_weight']} kg. "
                if is_hrv_filled: analysis_query += f"HRV: {hrv_form.cleaned_data['hrv']}, Alvás: {hrv_form.cleaned_data['sleep_quality']}/10."
                
                # Kérünk egy azonnali reakciót Dittától
                ditta_feedback = ditta_service.get_ditta_response(request.user, 'biometrics_morning_check', analysis_query)
                messages.success(request, ditta_feedback) # Ditta válasza megy a success üzenetbe!
                
                return redirect('biometric_data:athlete_dashboard') # Dashboardra vigyük, ott látja a grafikonokat is
            else:
                messages.error(request, 'Kérlek tölts ki legalább egy mezőt!')

    else:
        weight_form = MorningWeightDataForm(instance=weight_instance)
        hrv_form = HRVandSleepDataForm(instance=hrv_instance)
    
    # Alap üzenet, ha csak megnyitja az oldalt
    app_context = 'biometrics_morning_check'
    welcome_message = ditta_service.get_ditta_response(request.user, app_context)

    context = {
        'weight_form': weight_form,
        'hrv_form': hrv_form,
        'title': title,
        'app_context': app_context,
        'welcome_message': welcome_message, # Ez jelenik meg a robot ikon mellett
    }
    return render(request, 'biometric_data/morning_check.html', context)

# -------------------- 2. Edzés Utáni Mérések (after_training) --------------------
@login_required
def after_training(request):
    today = date.today()
    
    weight_instance = WeightData.objects.filter(user=request.user, workout_date=today).first()
    feedback_instance = WorkoutFeedback.objects.filter(user=request.user, workout_date=today).first()

    if weight_instance or feedback_instance:
        title = 'Edzés Utáni Mérések Módosítása'
        action_message = 'módosítva'
    else:
        title = 'Edzés Utáni Mérések Felvétele'
        action_message = 'rögzítve'

    if request.method == 'POST':
        weight_form = AfterTrainingWeightForm(request.POST, instance=weight_instance)
        feedback_form = AfterTrainingFeedbackForm(request.POST, instance=feedback_instance)
        
        is_weight_valid = weight_form.is_valid()
        is_feedback_valid = feedback_form.is_valid()

        is_weight_filled = any(v is not None for k, v in weight_form.cleaned_data.items()) if is_weight_valid else False
        is_feedback_filled = any(v is not None for k, v in feedback_form.cleaned_data.items()) if is_feedback_valid else False
        
        if not (is_weight_filled or is_feedback_filled):
            messages.error(request, 'Kérlek tölts ki legalább egy mezőt!')

        elif is_weight_valid and is_feedback_valid:
            
            if is_weight_filled:
                weight_data = weight_form.save(commit=False)
                weight_data.user = request.user
                weight_data.save()
            
            if is_feedback_filled:
                feedback_data = feedback_form.save(commit=False)
                feedback_data.user = request.user
                feedback_data.save()
            
            messages.success(request, f'Az edzés utáni adatok sikeresen {action_message} lettek!')
            return redirect('core:main_page')
        else:
            messages.error(request, 'Hiba történt az adatok rögzítése során. Kérlek ellenőrizd a mezőket!')
            
    else:
        weight_form = AfterTrainingWeightForm(instance=weight_instance)
        feedback_form = AfterTrainingFeedbackForm(instance=feedback_instance)
    
    app_context = 'after_training'
    welcome_message = ditta_service.get_ditta_response(request.user, app_context)

    context = {
        'weight_form': weight_form,
        'feedback_form': feedback_form,
        'title': title, 
        'app_context': app_context,
        'welcome_message': welcome_message,
    }
    return render(request, 'biometric_data/after_training.html', context)

# -------------------- 3. Eseti Mérések (occasional_measurements) --------------------
@login_required
def occasional_measurements(request):
    today = date.today()
    
    weight_instance = WeightData.objects.filter(user=request.user, workout_date=today).first()
    feedback_instance = WorkoutFeedback.objects.filter(user=request.user, workout_date=today).first()

    title = 'Eseti Mérések Rögzítése (Testösszetétel, Marokerő)'
    action_message = 'rögzítve'

    if request.method == 'POST':
        weight_form = OccasionalWeightForm(request.POST, instance=weight_instance)
        feedback_form = OccasionalFeedbackForm(request.POST, instance=feedback_instance)
        
        is_weight_valid = weight_form.is_valid()
        is_feedback_valid = feedback_form.is_valid()

        is_weight_filled = any(weight_form.cleaned_data.values()) if is_weight_valid else False
        is_feedback_filled = any(feedback_form.cleaned_data.values()) if is_feedback_valid else False
        
        if not (is_weight_filled or is_feedback_filled):
            messages.error(request, 'Kérlek tölts ki legalább egy mezőt a rögzítéshez!')
        
        elif is_weight_valid and is_feedback_valid:
            
            if is_weight_filled:
                weight_data = weight_form.save(commit=False)
                weight_data.user = request.user
                weight_data.save()
            
            if is_feedback_filled:
                feedback_data = feedback_form.save(commit=False)
                feedback_data.user = request.user
                feedback_data.save()
            
            messages.success(request, f'Az eseti adatok sikeresen {action_message} lettek!')
            return redirect('core:main_page')
        else:
            messages.error(request, 'Hiba történt az adatok rögzítése során. Kérlek ellenőrizd a mezőket!')
            
    else:
        weight_form = OccasionalWeightForm(instance=weight_instance)
        feedback_form = OccasionalFeedbackForm(instance=feedback_instance)
    
    app_context = 'occasional_measurements'
    welcome_message = ditta_service.get_ditta_response(request.user, app_context)

    context = {
        'weight_form': weight_form,
        'feedback_form': feedback_form,
        'title': title,
        'app_context': app_context,
        'welcome_message': welcome_message,
    }
    return render(request, 'biometric_data/occasional_measurements.html', context)

# -------------------- 4. Futóteljesítmény Rögzítése (add_running_performance) --------------------
@login_required
def add_running_performance(request):
    title = 'Új Futóteljesítmény Rögzítése'

    if request.method == 'POST':
        running_form = RunningPerformanceForm(request.POST) 
        
        if running_form.is_valid():
            running_data = running_form.save(commit=False)
            running_data.user = request.user
            running_data.save()
            
            messages.success(request, 'A futóteljesítmény sikeresen rögzítve!')
            return redirect('core:main_page')
        else:
            messages.error(request, 'Hiba történt a futóteljesítmény rögzítése során. Kérlek ellenőrizd a mezőket!')
            
    else:
        running_form = RunningPerformanceForm() 

    app_context = 'add_running_performance'
    welcome_message = ditta_service.get_ditta_response(request.user, app_context)

    context = {
        'running_form': running_form,
        'title': title,
        'app_context': app_context,
        'welcome_message': welcome_message,
    }
    return render(request, 'biometric_data/add_running_performance.html', context)

# -------------------- 5. Sportoló Dashboard (segéd adatok) --------------------
    # A. Testsúly visszajelzés (PLACEHOLDER)
def generate_weight_feedback(data_queryset):
    # Itt a Testsúly trend elemzés logikája
    return "<span class=\"text-success\">Testsúly adatok rendben vannak. (Még nem implementált)</span>"

    # B. Marokerő/Testösszetétel visszajelzés (14 napos ciklus) - JAVÍTVA
def generate_grip_feedback(weight_queryset, feedback_queryset):
    """Generál visszajelzést a 14 napos Testösszetétel mérés alapján (marokerő szűrés nélkül)."""
    today = date.today()
    latest_date = None

    # Csak a testsúly/testösszetétel lekérdezést használjuk (WeightData - weight_queryset).
    # Mivel a right_grip_strength hibát okoz a WorkoutFeedback-ben, ideiglenesen csak a WeightData-ra (body_fat_percentage) szűrünk.
    last_bodycomp_data = weight_queryset.filter(
        # Ezt a mezőt feltételezzük a WeightData-ban (a hibaüzenet szerint).
        Q(body_fat_percentage__isnull=False) 
    ).order_by('-workout_date').first()
    
    if last_bodycomp_data and last_bodycomp_data.workout_date:
        latest_date = last_bodycomp_data.workout_date

    # Visszajelzés üzenet generálása
    if latest_date:
        days_since = (today - latest_date).days
        days_until_target = 14 - days_since
        
        if days_since < 14:
            feedback_class = "text-success"
            message = f"Utolsó testösszetétel mérés: {days_since} napja. Új mérés **{days_until_target} nap múlva** esedékes."
        else:
            feedback_class = "text-danger"
            message = f"Utolsó testösszetétel mérés: {days_since} napja. A 14 napos ciklus lejárt! Kérlek, mielőbb rögzítsd az adataidat."
            
        return f"""
            <span class="fw-bold {feedback_class}">{message}</span>
        """
    
    # Ha nincs mérés
    return "Nincs rögzített **testösszetétel** adat. Kérlek, végezz el egy mérést a visszajelzéshez."

    # C. HRV és Alvás Grafikon adatok előkészítése
def generate_hrv_sleep_chart_data(user):
    # Utolsó 30 nap adatai
    start_date = timezone.now().date() - timedelta(days=30)
    data = HRVandSleepData.objects.filter(user=user, recorded_at__gte=start_date).order_by('recorded_at')

    labels = [d.recorded_at.strftime("%m-%d") for d in data]
    
    # Adatok előkészítése float-ként.
    # HIBA JAVÍTVA: 'hrv_ms' helyett 'hrv' mezőre hivatkozunk
    hrv_data = [float(d.hrv) if d.hrv else None for d in data] 
    
    sleep_quality_data = [d.sleep_quality for d in data] 
    alertness_data = [d.alertness for d in data] 

    chart_data = {
        'labels': labels,
        'hrv_data': hrv_data,
        'sleep_quality_data': sleep_quality_data,
        'alertness_data': alertness_data,
    }
    return chart_data


    # D. Marokerő és Intenzitás Grafikon adatok előkészítése
def generate_grip_intensity_chart_data(user):
    # Utolsó 30 nap adatai
    start_date = timezone.now().date() - timedelta(days=30)
    data = WorkoutFeedback.objects.filter(user=user, workout_date__gte=start_date).order_by('workout_date')

    labels = [d.workout_date.strftime("%m-%d") for d in data]
    
    # Marokerő (kg)
    right_grip_data = [float(d.right_grip_strength) if d.right_grip_strength else None for d in data] 
    left_grip_data = [float(d.left_grip_strength) if d.left_grip_strength else None for d in data] 
    # Intenzitás (1-10)
    intensity_data = [d.workout_intensity for d in data] 

    chart_data = {
        'labels': labels,
        'right_grip_data': right_grip_data,
        'left_grip_data': left_grip_data,
        'intensity_data': intensity_data,
    }
    return chart_data

    # Segédfüggvény a DurationField másodpercre konvertálásához (Futóteljesítményhez)
def duration_to_seconds(duration):
    if duration is not None:
        return duration.total_seconds()
    return None

    # E. Futóteljesítmény Grafikon adatok előkészítése
def generate_running_chart_data(user):
    # Utolsó 30 nap adatai
    start_date = timezone.now().date() - timedelta(days=30)
    data = RunningPerformance.objects.filter(user=user, run_date__gte=start_date).order_by('run_date')

    labels = [d.run_date.strftime("%m-%d") for d in data]
    
    pace_data = []
    for d in data:
        if d.run_distance_km and d.run_duration:
            # Tempó számítása: (teljes idő másodpercben) / (távolság km-ben) -> eredmény: másodperc/km
            pace_data.append(duration_to_seconds(d.run_duration) / float(d.run_distance_km))
        else:
            pace_data.append(None)
            
    avg_hr_data = [d.run_avg_hr for d in data]

    chart_data = {
        'labels': labels,
        'pace_data': pace_data, # Másodperc/km formátumban adjuk át a Chart.js-nek
        'avg_hr_data': avg_hr_data,
    }
    return chart_data

# -------------------- 5.1. Sportoló Dashboard (athlete_dashboard) --------------------
@login_required
def athlete_dashboard(request):
    user = request.user
    today = timezone.now().date()
    
    # 1. Adatlekérdezések (utolsó 30 nap)
    start_date_30 = today - timedelta(days=30)
    
    weight_queryset = WeightData.objects.filter(user=user, workout_date__gte=start_date_30).order_by('-workout_date')
    hrv_sleep_queryset = HRVandSleepData.objects.filter(user=user, recorded_at__gte=start_date_30).order_by('-recorded_at')
    feedback_queryset = WorkoutFeedback.objects.filter(user=user, workout_date__gte=start_date_30).order_by('-workout_date')
    running_queryset = RunningPerformance.objects.filter(user=user, run_date__gte=start_date_30).order_by('-run_date')

    # Utolsó adatok (az analitikához és időzítéshez)
    last_weight = weight_queryset.first()
    last_feedback = feedback_queryset.first()

    # 2. ANALITIKAI VISSZAJELZÉSEK GENERÁLÁSA
    # Feltételezzük, hogy ezek az 'analytics.py'-ból importálva vannak
    weight_feedback = generate_weight_feedback(weight_queryset)
    hrv_sleep_feedback = generate_hrv_sleep_feedback(hrv_sleep_queryset)
    running_feedback = generate_running_feedback(running_queryset)
    grip_timing_feedback = generate_timing_feedback(last_weight, last_feedback)
    
    
    # 3. GRAFIKON ADATOK GENERÁLÁSA
    
    # A. Testsúly grafikon adatok (30 napos trend)
    # Figyelem! A queryset-et itt újra 'workout_date' szerint rendezzük, de NÖVEKVŐ sorrendben a grafikon miatt.
    weight_data_asc = weight_queryset.order_by('workout_date')
    weight_chart_data = {
        'labels': [d.workout_date.strftime("%m-%d") for d in weight_data_asc],
        'weights': [float(d.morning_weight) for d in weight_data_asc],
        'body_fat_data': [float(d.body_fat_percentage) if d.body_fat_percentage else None for d in weight_data_asc],
        'muscle_data': [float(d.muscle_percentage) if d.muscle_percentage else None for d in weight_data_asc],
    }
    
    # B. Új adatok generálása a segédfüggvényekkel
    hrv_sleep_chart_data = generate_hrv_sleep_chart_data(user)
    grip_intensity_chart_data = generate_grip_intensity_chart_data(user)
    running_chart_data = generate_running_chart_data(user)
    
    app_context = 'biometrics_dashboard'
    ditta_query = "Kérlek, nézd át az utolsó 30 napos trendjeimet és adj egy rövid helyzetjelentést!"
    welcome_message = ditta_service.get_ditta_response(request.user, app_context, ditta_query)

    # 4. Context összeállítása
    context = {
    'title': 'Sportoló Dashboard',
    # JAVÍTOTT SOR: Közvetlen lekérdezés a UserRole modellen, elkerülve a related_name hibát
    'athlete_roles': UserRole.objects.filter(user=user, status='APPROVED'), 
    
    # Visszajelzések (HTML kód)
    'weight_feedback': weight_feedback,
    'hrv_sleep_feedback': hrv_sleep_feedback,
    'running_feedback': running_feedback,
    'grip_timing_feedback': grip_timing_feedback,
    
    # Grafikon adatok JSON-ban
    'weight_chart_data_json': json.dumps(weight_chart_data, cls=DjangoJSONEncoder),
    'hrv_sleep_chart_data_json': json.dumps(hrv_sleep_chart_data, cls=DjangoJSONEncoder),
    'grip_intensity_chart_data_json': json.dumps(grip_intensity_chart_data, cls=DjangoJSONEncoder),
    'running_chart_data_json': json.dumps(running_chart_data, cls=DjangoJSONEncoder),

    # Ditta bekötése
    'app_context': app_context,
    'welcome_message': welcome_message,
    }
    return render(request, 'biometric_data/athlete_dashboard.html', context)
