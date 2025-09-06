from django import forms
from .models import WeightData
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