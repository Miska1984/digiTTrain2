# diagnostics_jobs/forms.py
from django import forms
from django.core.exceptions import ValidationError
from .models import UserAnthropometryProfile

# ===================================================================
# 🎯 ANTROPOMETRIAI HATÁRÉRTÉKEK (cm-ben)
# ===================================================================
MEASUREMENT_RANGES = {
    'height_cm': (140, 230),           # Teljes magasság
    'weight_kg': (40, 200),            # Testsúly
    'trunk_height_cm': (40, 90),       # Törzshossz
    'shoulder_width_cm': (30, 60),     # Vállszélesség
    'pelvis_width_cm': (20, 45),       # Medenceszélesség
    'left_upper_arm_cm': (20, 45),     # Felkar
    'right_upper_arm_cm': (20, 45),
    'left_forearm_cm': (18, 40),       # Alkar
    'right_forearm_cm': (18, 40),
    'left_thigh_cm': (30, 65),         # Comb
    'right_thigh_cm': (30, 65),
    'left_shin_cm': (30, 60),          # Lábszár
    'right_shin_cm': (30, 60),
}

# Szimmetriai tolerancia (%)
SYMMETRY_TOLERANCE = 15  # 15% eltérés még elfogadható


class AnthropometryProfileForm(forms.ModelForm):
    """
    A felhasználó antropometriai adatainak szerkesztésére szolgáló űrlap.
    Ezeket a mezőket a felhasználó kézzel módosíthatja.
    """

    class Meta:
        model = UserAnthropometryProfile
        fields = [
            "height_cm",
            "weight_kg",
            "trunk_height_cm",
            "shoulder_width_cm",
            "pelvis_width_cm",
            "left_upper_arm_cm",
            "right_upper_arm_cm",
            "left_forearm_cm",
            "right_forearm_cm",
            "left_thigh_cm",
            "right_thigh_cm",
            "left_shin_cm",
            "right_shin_cm",
            "manual_thigh_cm", 
            "manual_shin_cm", 
        ]
        widgets = {
            "height_cm": forms.NumberInput(attrs={"step": "0.1", "min": "100", "max": "250", "class": "form-control"}),
            "weight_kg": forms.NumberInput(attrs={"step": "0.1", "min": "30", "max": "200", "class": "form-control"}),
            "trunk_height_cm": forms.NumberInput(attrs={"step": "0.1", "min": "10", "max": "120", "class": "form-control"}),
            "shoulder_width_cm": forms.NumberInput(attrs={"step": "0.1", "min": "20", "max": "70", "class": "form-control"}),
            "pelvis_width_cm": forms.NumberInput(attrs={"step": "0.1", "min": "20", "max": "60", "class": "form-control"}),
            "left_upper_arm_cm": forms.NumberInput(attrs={"step": "0.1", "min": "15", "max": "50", "class": "form-control"}),
            "right_upper_arm_cm": forms.NumberInput(attrs={"step": "0.1", "min": "15", "max": "50", "class": "form-control"}),
            "left_forearm_cm": forms.NumberInput(attrs={"step": "0.1", "min": "15", "max": "50", "class": "form-control"}),
            "right_forearm_cm": forms.NumberInput(attrs={"step": "0.1", "min": "15", "max": "50", "class": "form-control"}),
            "left_thigh_cm": forms.NumberInput(attrs={"step": "0.1", "min": "25", "max": "80", "class": "form-control"}),
            "right_thigh_cm": forms.NumberInput(attrs={"step": "0.1", "min": "25", "max": "80", "class": "form-control"}),
            "left_shin_cm": forms.NumberInput(attrs={"step": "0.1", "min": "20", "max": "70", "class": "form-control"}),
            "right_shin_cm": forms.NumberInput(attrs={"step": "0.1", "min": "20", "max": "70", "class": "form-control"}),
            "manual_thigh_cm": forms.NumberInput(attrs={
            "step": "0.1", "min": "25", "max": "80", "class": "form-control",
                "placeholder": "Pl.: 41.0"
            }),
            "manual_shin_cm": forms.NumberInput(attrs={
                "step": "0.1", "min": "25", "max": "70", "class": "form-control",
                "placeholder": "Pl.: 38.5"
            }),
        }

    def clean(self):
        cleaned_data = super().clean()

        height = cleaned_data.get("height_cm")
        weight = cleaned_data.get("weight_kg")
        thigh = cleaned_data.get("manual_thigh_cm")
        shin = cleaned_data.get("manual_shin_cm")

        if height and (height < 100 or height > 250):
            self.add_error("height_cm", "A testmagasság 100–250 cm között lehet.")
        if weight and (weight < 30 or weight > 200):
            self.add_error("weight_kg", "A testsúly 30–200 kg között lehet.")
        if thigh and (thigh < 25 or thigh > 80):
            self.add_error("manual_thigh_cm", "A combhossz 25–80 cm között lehet.")
        if shin and (shin < 20 or shin > 70):
            self.add_error("manual_shin_cm", "A lábszárhossz 20–70 cm között lehet.")
        
        return cleaned_data


# ================================================================
# 📸 Antropometriai Kalibráció Form (fotófeltöltéshez)
# ================================================================
class AnthropometryCalibrationForm(forms.Form):
    """
    A két fotós antropometriai kalibrációhoz használt űrlap.
    A felhasználónak meg kell adnia a valós magasságát (m), valamint
    a comb- és lábszár hosszát (cm).
    """

    user_stated_height_m = forms.FloatField(
        label="Valós testmagasság (m)",
        min_value=1.4,
        max_value=2.3,
        required=True,
        help_text="Pl.: 1.78 — Ez az érték a kalibráció alapja lesz.",
        widget=forms.NumberInput(attrs={
            "step": "0.01",
            "class": "form-control",
            "placeholder": "Pl.: 1.75",
        }),
    )

    user_stated_thigh_cm = forms.FloatField(
        label="Comb hossz (cm)",
        min_value=30,
        max_value=70,
        required=True,
        help_text="Pl.: 45.0 — A csípőtől a térdig mért távolság.",
        widget=forms.NumberInput(attrs={
            "step": "0.1",
            "class": "form-control",
            "placeholder": "Pl.: 45.0",
        }),
    )

    user_stated_shin_cm = forms.FloatField(
        label="Lábszár hossz (cm)",
        min_value=25,
        max_value=65,
        required=True,
        help_text="Pl.: 40.0 — A térdtől a bokáig mért távolság.",
        widget=forms.NumberInput(attrs={
            "step": "0.1",
            "class": "form-control",
            "placeholder": "Pl.: 40.0",
        }),
    )

    front_photo = forms.ImageField(
        label="Szemből készült fotó",
        required=True,
        help_text="JPEG vagy PNG formátum, max. 10 MB.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png"}),
    )

    side_photo = forms.ImageField(
        label="Oldalról készült fotó",
        required=True,
        help_text="JPEG vagy PNG formátum, max. 10 MB.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png"}),
    )

    # --- Validálás ---
    def clean_front_photo(self):
        photo = self.cleaned_data.get("front_photo")
        if photo and photo.size > 10 * 1024 * 1024:
            raise forms.ValidationError("A fotó mérete maximum 10 MB lehet!")
        return photo

    def clean_side_photo(self):
        photo = self.cleaned_data.get("side_photo")
        if photo and photo.size > 10 * 1024 * 1024:
            raise forms.ValidationError("A fotó mérete maximum 10 MB lehet!")
        return photo