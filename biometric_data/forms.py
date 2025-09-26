# biometric_data/forms.py
from django import forms
# A modellek importálása
from .models import WeightData, HRVandSleepData, WorkoutFeedback, RunningPerformance

# -------------------- 1. Reggeli Mérések (morning_check) --------------------

class MorningWeightDataForm(forms.ModelForm):
    """Űrlap a reggeli testsúly adatok rögzítésére."""
    morning_weight = forms.DecimalField(
        label="Reggeli Testsúly (kg)",
        max_digits=5, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'Testsúly (kg)'})
    )

    class Meta:
        model = WeightData
        fields = ['morning_weight']
        exclude = ['user', 'pre_workout_weight', 'post_workout_weight', 'fluid_intake', 'body_fat_percentage', 'muscle_percentage', 'bone_mass_kg', 'workout_date']

    def clean_morning_weight(self):
        weight = self.cleaned_data.get('morning_weight')
        return weight if weight is not None and weight != '' else None

class HRVandSleepDataForm(forms.ModelForm):
    """
    Űrlap az HRV, Alvás és Éberség adatok rögzítésére.
    A választékokat a HRVandSleepData modellből olvassa be.
    """
    class Meta:
        model = HRVandSleepData
        fields = ['hrv', 'sleep_quality', 'alertness']
        exclude = ['user', 'recorded_at']
        
        widgets = {
            'hrv': forms.NumberInput(attrs={
                'step': '0.01', 
                'placeholder': 'HRV (ms)', 
                'class': 'form-control'
            }),
            'sleep_quality': forms.Select(
                # JAVÍTVA: A choices lista a modellből származik
                choices=HRVandSleepData.SLEEP_QUALITY_CHOICES, 
                attrs={'class': 'form-select'}
            ),
            'alertness': forms.Select(
                # JAVÍTVA: A choices lista a modellből származik
                choices=HRVandSleepData.ALERTNESS_CHOICES,
                attrs={'class': 'form-select'}
            ),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A mezők opcionálissá tétele
        self.fields['hrv'].required = False 
        self.fields['sleep_quality'].required = False
        self.fields['alertness'].required = False
        
        # JAVÍTVA: Címkék beállítása a helyes 'self.fields' használatával
        self.fields['sleep_quality'].label = "Alvás Minősége"
        self.fields['alertness'].label = "Éberség / Közérzet"
    
    # Clean metódusok a Select mezők None értékének kezelésére
    def clean_sleep_quality(self):
        value = self.cleaned_data.get('sleep_quality')
        # A None-ra konvertálás biztosítja, hogy a null=True IntegerField a modelben jól kezelje
        return int(value) if value is not None and value != '' else None 
    
    def clean_alertness(self):
        value = self.cleaned_data.get('alertness')
        return int(value) if value is not None and value != '' else None 

# -------------------- 2. Edzés Utáni Mérések (after_training) --------------------

class AfterTrainingWeightForm(forms.ModelForm):
    """Űrlap az edzés előtti/utáni súlyra és folyadékbevitelre a WeightData-ból."""
    class Meta:
        model = WeightData
        fields = ['pre_workout_weight', 'post_workout_weight', 'fluid_intake']
        exclude = ['user', 'morning_weight', 'body_fat_percentage', 'muscle_percentage', 'bone_mass_kg', 'workout_date']
        widgets = {
            'pre_workout_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'Edzés előtti súly (kg)'}),
            'post_workout_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'Edzés utáni súly (kg)'}),
            'fluid_intake': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'Folyadékbevitel (liter)'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['pre_workout_weight'].required = False
        self.fields['post_workout_weight'].required = False
        self.fields['fluid_intake'].required = False
        
class AfterTrainingFeedbackForm(forms.ModelForm):
    """
    Űrlap CSAK az edzés intenzitására a WorkoutFeedback-ból. 
    Külön form, hogy ne jelenítse meg a markolóerőt.
    """
    class Meta:
        model = WorkoutFeedback
        # CSAK EZT az egy mezőt akarjuk megjeleníteni az AfterTraining oldalon
        fields = ['workout_intensity'] 
        exclude = ['user', 'right_grip_strength', 'left_grip_strength', 'workout_date']
        
        widgets = {
            # FIX: Hozzáadjuk a choices-t, ami a model INTENSITY_CHOICES listája
            'workout_intensity': forms.Select(
                choices=WorkoutFeedback.INTENSITY_CHOICES, # Használjuk a teljes listát (beleértve a None-t)
            ), 
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # FIX: Beállítjuk a labelt (amely felülírja a model verbose_name-jét)
        self.fields['workout_intensity'].label = "Edzésintenzitás"
        self.fields['workout_intensity'].required = False
        
        # Ez a form rendereli most a mezőt, a form-control class hozzáadása szükséges:
        self.fields['workout_intensity'].widget.attrs.update({'class': 'form-control'})


# -------------------- 3. Eseti Mérések (occasional_measurements) --------------------

class OccasionalWeightForm(forms.ModelForm):
    """Űrlap az eseti testösszetételi adatokra (zsír, izom, csont) a WeightData-ból."""
    class Meta:
        model = WeightData
        fields = ['body_fat_percentage', 'muscle_percentage', 'bone_mass_kg']
        exclude = ['user', 'morning_weight', 'pre_workout_weight', 'post_workout_weight', 'fluid_intake', 'workout_date']
        widgets = {
            'body_fat_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'Testzsír (%)'}),
            'muscle_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'Izomtömeg (%)'}),
            'bone_mass_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Csonttömeg (kg)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['body_fat_percentage'].required = False
        self.fields['muscle_percentage'].required = False
        self.fields['bone_mass_kg'].required = False

class OccasionalFeedbackForm(forms.ModelForm):
    """Űrlap a marokerő adatokra a WorkoutFeedback-ból."""
    class Meta:
        model = WorkoutFeedback
        fields = ['right_grip_strength', 'left_grip_strength']
        exclude = ['user', 'workout_intensity', 'workout_date']
        widgets = {
            'right_grip_strength': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Jobb marokerő (kg)'}),
            'left_grip_strength': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Bal marokerő (kg)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['right_grip_strength'].required = False
        self.fields['left_grip_strength'].required = False

class RunningPerformanceForm(forms.ModelForm):
    """Űrlap az új futóteljesítmény rögzítésére."""
    class Meta:
        model = RunningPerformance
        exclude = ['user', 'run_date']
        widgets = {
            'run_distance_km': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Távolság (km)'}),
            'run_duration': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'pl. 00:25:30 (óra:perc:másodperc)'}),
            'run_min_hr': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Min. pulzus (bpm)'}),
            'run_max_hr': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Max. pulzus (bpm)'}),
            'run_avg_hr': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Átl. pulzus (bpm)'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # FIX: A futó formban legyen KÖTELEZŐ a távolság, de a többi opcionális
        self.fields['run_distance_km'].required = True 
        self.fields['run_duration'].required = False # Opcionális
        self.fields['run_min_hr'].required = False
        self.fields['run_max_hr'].required = False
        self.fields['run_avg_hr'].required = False