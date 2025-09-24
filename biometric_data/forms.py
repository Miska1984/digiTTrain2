from django import forms
from .models import WeightData, HRVandSleepData, WorkoutFeedback, RunningPerformance
# from datetime import date  <- Ez a sor sem kell, mert a views.py kezeli a dátumot

class WeightDataForm(forms.ModelForm):
    """
    Űrlap a testsúly adatok rögzítésére.
    """
    class Meta:
        model = WeightData
        fields = [
            'morning_weight',
            'pre_workout_weight',
            'post_workout_weight',
            'fluid_intake',
            'body_fat_percentage',
            'muscle_percentage',
            'bone_mass_kg'
        ]
        widgets = {
            'morning_weight': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500', 'step': '0.1', 'placeholder': 'Reggeli súly (kg)'}),
            'pre_workout_weight': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500', 'step': '0.1', 'placeholder': 'Edzés előtti súly (kg)'}),
            'post_workout_weight': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500', 'step': '0.1', 'placeholder': 'Edzés utáni súly (kg)'}),
            'fluid_intake': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500', 'step': '0.1', 'placeholder': 'Folyadékbevitel (liter)'}),
            'body_fat_percentage': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500', 'step': '0.1', 'placeholder': 'Testzsír (%)'}),
            'muscle_percentage': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500', 'step': '0.1', 'placeholder': 'Izomtömeg (%)'}),
            'bone_mass_kg': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500', 'step': '0.1', 'placeholder': 'Csonttömeg (kg)'}),
        }

class HRVandSleepDataForm(forms.ModelForm):
    class Meta:
        model = HRVandSleepData
        exclude = ['user', 'recorded_at']
        widgets = {
            'hrv': forms.NumberInput(attrs={'step': '0.01', 'placeholder': 'HRV (ms)'}),
            'sleep_quality': forms.NumberInput(attrs={'min': 1, 'max': 10, 'placeholder': 'Alvásminőség (1-10)'}),
        }

class WorkoutFeedbackForm(forms.ModelForm):
    class Meta:
        model = WorkoutFeedback
        exclude = ['user', 'workout_date']
        widgets = {
            'right_grip_strength': forms.NumberInput(attrs={'step': '0.01', 'placeholder': 'Jobb marokerő (kg)'}),
            'left_grip_strength': forms.NumberInput(attrs={'step': '0.01', 'placeholder': 'Bal marokerő (kg)'}),
            'workout_intensity': forms.NumberInput(attrs={'min': 1, 'max': 10, 'placeholder': 'Edzésintenzitás (1-10)'}),
        }

class RunningPerformanceForm(forms.ModelForm):
    class Meta:
        model = RunningPerformance
        exclude = ['user', 'run_date']
        widgets = {
            'run_distance_km': forms.NumberInput(attrs={'step': '0.01', 'placeholder': 'Távolság (km)'}),
            'run_duration': forms.TextInput(attrs={'placeholder': 'pl. 00:25:30 (óra:perc:másodperc)'}),
            'run_min_hr': forms.NumberInput(attrs={'placeholder': 'Min. pulzus (bpm)'}),
            'run_max_hr': forms.NumberInput(attrs={'placeholder': 'Max. pulzus (bpm)'}),
            'run_avg_hr': forms.NumberInput(attrs={'placeholder': 'Átl. pulzus (bpm)'}),
        }