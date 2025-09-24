# biometric_data/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import WeightDataForm, HRVandSleepDataForm, WorkoutFeedbackForm, RunningPerformanceForm
from .models import WeightData, HRVandSleepData, WorkoutFeedback, RunningPerformance
from datetime import date
import json # Fontos: importálni kell a json könyvtárat

@login_required # Biztosítja, hogy csak bejelentkezett felhasználók használhassák
def add_weight(request):
    if request.method == 'POST':
        form = WeightDataForm(request.POST)
        if form.is_valid():
            weight_data = form.save(commit=False)
            weight_data.user = request.user
            weight_data.save()
            return redirect('core:main_page')
    else:
        form = WeightDataForm()
    
    context = {
        'form': form,
        'title': 'Új Súlyadat Felvétele'
    }
    return render(request, 'biometric_data/add_weight.html', context)


# A súlyadatok listázásához is létrehozhatsz egy nézetet:
@login_required
def list_weight(request):
    # Lekérdezzük a bejelentkezett felhasználó testsúlyadatait.
    # A sorrendet 'workout_date' alapján állítjuk be, hogy a grafikon helyes legyen.
    user_weight_data = WeightData.objects.filter(user=request.user).order_by('workout_date')

    # Előkészítjük az adatokat a grafikonhoz
    labels = [entry.workout_date.strftime('%Y-%m-%d') for entry in user_weight_data]
    weights = [float(entry.morning_weight) for entry in user_weight_data]

    # Az izom- és testzsíradatokhoz speciális formátum kell a JavaScriptnek
    body_fat_data = [
        {'x': entry.workout_date.strftime('%Y-%m-%d'), 
         'y': float(entry.body_fat_percentage / 100 * entry.morning_weight) if entry.body_fat_percentage else None,
         'p': float(entry.body_fat_percentage) if entry.body_fat_percentage else None}
        for entry in user_weight_data
    ]
    muscle_data = [
        {'x': entry.workout_date.strftime('%Y-%m-%d'),
         'y': float(entry.muscle_percentage / 100 * entry.morning_weight) if entry.muscle_percentage else None,
         'p': float(entry.muscle_percentage) if entry.muscle_percentage else None}
        for entry in user_weight_data
    ]
    
    chart_data = {
        'labels': labels,
        'weights': weights,
        'body_fat_data': body_fat_data,
        'muscle_data': muscle_data,
    }

    # Az adatszerkezetet JSON stringgé alakítjuk, hogy a JavaScript feldolgozhassa
    chart_data_json = json.dumps(chart_data)

    context = {
        'table_data': user_weight_data,       # Átadjuk a lekérdezett adatokat a táblázatnak
        'chart_data_json': chart_data_json,   # Átadjuk a JSON stringet a grafikonnak
        'title': 'Súlykontroll Adatlapom'
    }
    return render(request, 'biometric_data/list_weight.html', context)

@login_required
def add_hrv_and_sleep(request):
    if request.method == 'POST':
        form = HRVandSleepDataForm(request.POST)
        if form.is_valid():
            data = form.save(commit=False)
            data.user = request.user
            data.save()
            return redirect('core:main_page')
    else:
        form = HRVandSleepDataForm()
    
    context = {'form': form, 'title': 'Új HRV és Alvás Adat Felvétele'}
    return render(request, 'biometric_data/add_hrv_and_sleep.html', context)

@login_required
def add_workout_feedback(request):
    if request.method == 'POST':
        form = WorkoutFeedbackForm(request.POST)
        if form.is_valid():
            data = form.save(commit=False)
            data.user = request.user
            data.save()
            return redirect('core:main_page')
    else:
        form = WorkoutFeedbackForm()
    
    context = {'form': form, 'title': 'Új Edzésvisszajelzés Felvétele'}
    return render(request, 'biometric_data/add_workout_feedback.html', context)

@login_required
def add_running_performance(request):
    if request.method == 'POST':
        form = RunningPerformanceForm(request.POST)
        if form.is_valid():
            data = form.save(commit=False)
            data.user = request.user
            data.save()
            return redirect('core:main_page')
    else:
        form = RunningPerformanceForm()
    
    context = {'form': form, 'title': 'Új Futóteljesítmény Felvétele'}
    return render(request, 'biometric_data/add_running_performance.html', context)

@login_required
def list_biometric_data(request):
    # Egyetlen nézet, ami listázza az összes biometriai adatot
    weight_data = WeightData.objects.filter(user=request.user).order_by('-workout_date')
    hrv_sleep_data = HRVandSleepData.objects.filter(user=request.user).order_by('-recorded_at')
    workout_feedback_data = WorkoutFeedback.objects.filter(user=request.user).order_by('-workout_date')
    running_performance_data = RunningPerformance.objects.filter(user=request.user).order_by('-run_date')

    context = {
        'weight_data': weight_data,
        'hrv_sleep_data': hrv_sleep_data,
        'workout_feedback_data': workout_feedback_data,
        'running_performance_data': running_performance_data,
        'title': 'Biometriai Adatok'
    }
    return render(request, 'biometric_data/list_biometric_data.html', context)
