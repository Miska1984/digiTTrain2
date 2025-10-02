# /app/assessment/forms.py

from django import forms
from .models import PlaceholderAthlete, PhysicalAssessment
from users.models import Club, Sport, UserRole # Szükség van a Club és Sport modellekre

class PlaceholderAthleteForm(forms.ModelForm):
    """
    Form a nem regisztrált sportoló felvitelére, 
    szűrt Club és Sport mezőkkel az edző szerepkörei alapján.
    """
    class Meta:
        model = PlaceholderAthlete
        fields = ['first_name', 'last_name', 'birth_date', 'club', 'sport']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'club': forms.Select(attrs={'class': 'form-select'}),
            'sport': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'first_name': 'Keresztnév',
            'last_name': 'Vezetéknév',
            'birth_date': 'Születési dátum',
            'club': 'Egyesület',
            'sport': 'Sportág',
        }

    def __init__(self, *args, **kwargs):
        # Kiemeljük az 'coach_user' argumentumot, amit majd a nézet ad át
        coach_user = kwargs.pop('coach_user', None)
        super().__init__(*args, **kwargs)

        if coach_user:
            # Lekérdezzük a coach összes jóváhagyott Edzői szerepkörét
            active_roles = UserRole.objects.filter(
                user=coach_user,
                role__name='Edző',
                status='approved'
            ).select_related('club', 'sport')

            # Kigyűjtjük az Edzőhöz tartozó egyedi Club és Sport ID-ket
            allowed_club_ids = active_roles.values_list('club_id', flat=True).distinct()
            allowed_sport_ids = active_roles.values_list('sport_id', flat=True).distinct()

            # Szűrjük a Club és Sport mezőket
            self.fields['club'].queryset = Club.objects.filter(id__in=allowed_club_ids).order_by('name')
            self.fields['sport'].queryset = Sport.objects.filter(id__in=allowed_sport_ids).order_by('name')
        
        # Opcionálisan beállíthatunk alapértelmezett választást, ha csak egy klub/sport van
        if self.fields['club'].queryset.count() == 1:
            self.fields['club'].initial = self.fields['club'].queryset.first().id
        if self.fields['sport'].queryset.count() == 1:
            self.fields['sport'].initial = self.fields['sport'].queryset.first().id

class PlaceholderAthleteImportForm(forms.Form):
    """
    Form a tömeges sportoló importálás Club/Sportág kiválasztásához és fájlfeltöltéshez.
    """
    file = forms.FileField(label="Excel fájl (.xlsx)", help_text="A sportolói adatokkal kitöltött sablon.")
    club = forms.ChoiceField(label="Cél Egyesület", required=True)
    sport = forms.ChoiceField(label="Cél Sportág", required=True)
    
    def __init__(self, *args, coach_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        if coach_user:
            active_roles = UserRole.objects.filter(
                user=coach_user, 
                role__name='Edző', 
                status='approved'
            ).select_related('club', 'sport')
            
            unique_clubs = {role.club.id: role.club.name for role in active_roles if role.club}
            unique_sports = {role.sport.id: role.sport.name for role in active_roles if role.sport}

            self.fields['club'].choices = [(id, name) for id, name in unique_clubs.items()]
            self.fields['sport'].choices = [(id, name) for id, name in unique_sports.items()]
            
            if len(self.fields['club'].choices) == 1:
                self.fields['club'].initial = self.fields['club'].choices[0][0]
            if len(self.fields['sport'].choices) == 1:
                self.fields['sport'].initial = self.fields['sport'].choices[0][0]
                
    def clean(self):
        cleaned_data = super().clean()
        club_id = cleaned_data.get('club')
        sport_id = cleaned_data.get('sport')
        
        # A ChoiceField ID-t modell objektummá alakítjuk a view számára
        if club_id:
            cleaned_data['club'] = Club.objects.get(id=club_id)
        if sport_id:
            cleaned_data['sport'] = Sport.objects.get(id=sport_id)
            
        return cleaned_data

class PhysicalAssessmentForm(forms.ModelForm):
    """
    Form egy fizikai felmérés (PhysicalAssessment) rögzítésére.
    Megjegyzés: A coach mezőt automatikusan töltjük ki a nézetben.
    """
    # Ez a mező segíti az Edzőt, hogy kiválassza, kinek rögzít adatot
    # Mivel a User és a PlaceholderAthlete is szerepelhet, ezt utólag kezeljük a nézetben.
    
    # Helyette egy "választó mezőt" használunk a sportolók listájára:
    
    # A sportoló azonosítása (ezt a nézetben injektáljuk)
    athlete_selector = forms.ChoiceField(
        choices=[], 
        label="Sportoló kiválasztása",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = PhysicalAssessment
        # A coach, athlete_user, és athlete_placeholder mezőket a nézet tölti ki
        fields = ['assessment_date', 'assessment_type', 'result_value', 'notes'] 
        widgets = {
            'assessment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'assessment_type': forms.Select(attrs={'class': 'form-select'}),
            'result_value': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'assessment_date': 'Dátum',
            'assessment_type': 'Felmérés Típusa',
            'result_value': 'Eredmény',
            'notes': 'Megjegyzések',
        }