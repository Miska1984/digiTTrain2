# /app/training_log/forms.py
from django import forms
from django.db import models
from django.db.models import Value, CharField, F
from django.db.models.functions import ExtractYear
from .models import AbsenceSchedule, TrainingSchedule, TrainingSession
from users.models import Club, Sport, User
from users.utils import get_coach_clubs_and_sports
from assessment.models import PlaceholderAthlete 

# --- 1. Szünetek Form ---
class AbsenceScheduleForm(forms.ModelForm):
    class Meta:
        model = AbsenceSchedule
        fields = ['name', 'category', 'start_date', 'end_date', 'club']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    # Edző szűrése a klubra (ha az edző rögzíti)
    def __init__(self, *args, coach_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if coach_user:
            clubs, _ = get_coach_clubs_and_sports(coach_user)
            self.fields['club'].queryset = clubs
            if clubs.count() == 1:
                self.fields['club'].initial = clubs.first()
                # self.fields['club'].widget = forms.HiddenInput() # Esetleg elrejthető, ha fix
        
        # Lehetőséget adunk, hogy ne legyen klubhoz rendelve (globális szünet)
        self.fields['club'].required = False

# --- 2.1. Dinamikus Szűrés az edzés tervezéshez ---
class MultipleChoiceCharField(forms.Field):
    # A Field-et a Forms-ból kell importálni, nem a models-ből, de a név alapján már jó!
    # A widget beállítása a __init__-ben a MultipleChoiceField logikájához hasonlóan kellene:
    # (A kódodban lévő változat használata feltételezi, hogy a Field az alaposztály)
    
    def __init__(self, choices=(), *args, **kwargs):
        kwargs.setdefault('widget', forms.CheckboxSelectMultiple)
        # Fontos: Ha a forms.Field az alaposztály, akkor nem kell choices=choices-t átadni a super()-nek, 
        # mert az csak a MultipleChoiceField-nél elvárt.
        # Viszont a választások beállításához a widget-en keresztül kell beavatkozni.
        # Ahogy most használod: MultipleChoiceField, az stabilabb!
        
        # Ha továbbra is forms.MultipleChoiceField-et használsz, csak a 'clean' metódust kell kikapcsolni.
        # De ha a fenti custom fieldet használod, a definíciója így kéne kinézzen:
        super().__init__(*args, **kwargs)
        self.choices = choices # A choices-t manuálisan kell beállítani
    
    def to_python(self, value):
        if not value:
            return []
        if isinstance(value, list):
            return value
        return value.split(',')
        
    def validate(self, value):
        # Ne futtassa a ChoiceField validációját, ami keresi a "M,F" stringet
        pass
        
    def prepare_value(self, value):
        # A ModelForm megpróbálja a betöltéskor stringgé alakítani, de a custom fieldben ez a módszer nem hívódik meg
        # a Form.value_from_object() miatt. Csak a to_python metódus fontos.
        if isinstance(value, list):
            return ','.join([str(v) for v in value])
        return value

# --- 2.2. Edzésrend Form ---
class TrainingScheduleForm(forms.ModelForm):
    # 1. Napok: Többszörös választás a CharField mezőre
    days_of_week = forms.MultipleChoiceField(
        choices=TrainingSchedule.DAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Napok",
        required=True
    )
    
    # 2. Születési évek: Dinamikusan feltöltött többszörös választás
    birth_years = forms.MultipleChoiceField( # Ezt töltjük fel dinamikusan
        widget=forms.CheckboxSelectMultiple,
        label="Születési évek (létszám)"
    )
    
    # 3. Nemek: Többszörös választás
    genders = forms.MultipleChoiceField(
        choices=PlaceholderAthlete.GENDER_CHOICES, # Használjuk a PlaceholderAthlete choices-ait
        widget=forms.CheckboxSelectMultiple,
        label="Nem"
    )

    class Meta:
        model = TrainingSchedule
        fields = [
            'club', 'sport', 'coach', 'name', 
            'days_of_week', 'start_time', 'end_time', 
            'birth_years', 'genders',
            'start_date', 'end_date'
        ]
        widgets = {
            'start_time': forms.TimeInput(
                attrs={'type': 'time', 'class': 'form-control'}
            ),
            'end_time': forms.TimeInput(
                attrs={'type': 'time', 'class': 'form-control'}
            ),
            'start_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'}
            ),
            'end_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'}
            ),
        }

    # Edző szűrése és dinamikus beállítások
    def __init__(self, *args, coach_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if coach_user:
            clubs, sports = get_coach_clubs_and_sports(coach_user)
            
            # --- KLUB SZŰRÉS ---
            self.fields['club'].queryset = clubs
            if clubs.count() == 1:
                self.fields['club'].initial = clubs.first()
            
            self.fields['sport'].queryset = Sport.objects.filter(clubs__in=clubs).distinct()

            # 1. Lekérdezés javítása: Csatlakozunk a Profile táblához, hogy elérjük a first_name és last_name mezőket.
            coach_qs = User.objects.filter(
                user_roles__role__name='Edző',
                user_roles__club__in=clubs,
                user_roles__sport__in=sports,
                user_roles__status='approved'
            ).select_related('profile').distinct() # <-- Fontos a .select_related('profile')!
            
            self.fields['coach'].queryset = coach_qs

            # 2. ModelChoiceField viselkedésének felülírása: Kiírjuk a teljes nevet.
            # Ezt a ModelChoiceField objektumra vonatkozóan tesszük meg:
            self.fields['coach'].label_from_instance = lambda obj: (
                f"{obj.profile.first_name} {obj.profile.last_name}" 
                if hasattr(obj, 'profile') and obj.profile.last_name
                else obj.username
            )

            # 4. DINAMIKUS SZÜLETÉSI ÉV FELTÖLTÉS
            # Csak azokat a születési éveket kérjük le, amelyek a Club/Sport/Edzőhöz tartoznak
            placeholder_data = PlaceholderAthlete.objects.filter(
                club__in=clubs,
                sport__in=sports
            ).annotate(
                # Kiszámoljuk az évet a birth_date mezőből
                birth_year_calculated=ExtractYear('birth_date') 
            ).values('birth_year_calculated').annotate(
                count=models.Count('birth_year_calculated')
            ).order_by('-birth_year_calculated') # Év alapján rendezünk

            # Átalakítás choices formátumra: (2010, '2010 (5 fő)')
            year_choices = [
                # JAVÍTVA: birth_year helyett birth_year_calculated használata
                (str(item['birth_year_calculated']), f"{item['birth_year_calculated']} ({item['count']} fő)")
                for item in placeholder_data
            ]
            self.fields['birth_years'].choices = year_choices
            self.fields['start_time'].help_text = "Adja meg az edzés kezdetének időpontját (pl. 16:30)."

            # A) NEM REGISZTRÁLT SPORTOLÓK (PlaceholderAthlete)
            placeholder_qs = PlaceholderAthlete.objects.filter(
                club__in=clubs,
                sport__in=sports
            ).annotate(
                birth_year=ExtractYear('birth_date'),
                # Megjelöljük a forrást
                source=Value('non-reg', output_field=CharField()) 
            ).values('birth_year', 'source').annotate(
                count=models.Count('birth_year')
            ).order_by('-birth_year')


            # B) REGISZTRÁLT SPORTOLÓK (User - Profile/UserRole)
            # Feltételezve, hogy a 'birth_date' a User Profile-ban van tárolva.
            # Ha a birth_date a fő User modellben van, akkor a .select_related('profile') nem kell!
            athlete_qs = User.objects.filter(
                user_roles__role__name='Sportoló',
                user_roles__club__in=clubs,
                user_roles__sport__in=sports,
                user_roles__status='approved', # Csak jóváhagyott szerepkört veszünk figyelembe
                
            ).select_related(
                # Explicit kérés, hogy a QuerySet kapcsolódjon a Profile-hoz
                'profile' 
            ).annotate(
                # KÖZVETLEN ExtractYear használata a kapcsolaton keresztül:
                # Ha a Profile létezik, kinyeri az évet. Ha nem, NULL lesz.
                birth_year=ExtractYear('profile__date_of_birth'), # <-- FIGYELEM: date_of_birth a Profile-ban!
                # Megjelöljük a forrást
                source=Value('reg', output_field=CharField()) 
            ).exclude(
                # Kizárjuk azokat a User-eket, akiknek nincs Profile bejegyzésük, VAGY nincs születési dátumuk
                birth_year__isnull=True
            ).values('birth_year', 'source').annotate(
                count=models.Count('birth_year')
            ).order_by('-birth_year')

            # C) ADATOK EGYESÍTÉSE ÉS ÁTALAKÍTÁSA
            # A két queryset uniója (összevonása)
            combined_data = placeholder_qs.union(athlete_qs).order_by('-birth_year')
            
            # Csoportosítás év szerint a végső Choices lista létrehozásához
            grouped_years = {}
            for item in combined_data:
                year = item['birth_year']
                source = item['source']
                count = item['count']
                
                if year not in grouped_years:
                    grouped_years[year] = {'reg': 0, 'non-reg': 0}
                
                grouped_years[year][source] = count

            # Choices formátum létrehozása: (2010, '2010 (reg. 3fő; nem reg. 5fő)')
            year_choices = []
            for year in sorted(grouped_years.keys(), reverse=True):
                reg_count = grouped_years[year]['reg']
                non_reg_count = grouped_years[year]['non-reg']
                
                label = f"{year} (reg. {reg_count}fő; nem reg. {non_reg_count}fő)"
                year_choices.append((str(year), label))

            self.fields['birth_years'].choices = year_choices            

            # ... (további logika) ...
            
    # Mentési logika felülírása a CharField miatt
    def clean(self):
        cleaned_data = super().clean()
        
        # MultipleChoiceField adatainak konvertálása vesszővel elválasztott stringgé
        if 'days_of_week' in cleaned_data:
            # days_of_week is MultipleChoiceField, de a modellben CharField
            # A Django alapszintű validációja még futhat rajta!
            cleaned_data['days_of_week'] = ','.join([str(d) for d in cleaned_data['days_of_week']])
        
        if 'birth_years' in cleaned_data:
            # birth_years is MultipleChoiceField, de a modellben CharField
            cleaned_data['birth_years'] = ','.join(cleaned_data['birth_years'])
        
        if 'genders' in cleaned_data:
            # genders is MultipleChoiceField, de a modellben CharField
            # Ha az eredeti hiba a clean hívása előtt keletkezik, a mi logikánk már késő.
            # DE ha a form field maga nem stringként menti az adatot a clean() előtt, akkor ez segít:
            cleaned_data['genders'] = ','.join(cleaned_data['genders'])
            
        return cleaned_data

class TrainingSessionForm(forms.ModelForm):
    """
    Form az edzés konkrét adatainak és szakmai felbontásának rögzítéséhez.
    """
    class Meta:
        model = TrainingSession
        fields = [
            'session_date', 'start_time', 'duration_minutes', 'location',
            'toy_duration', 'warmup_duration', 'is_warmup_playful',
            'technical_duration', 'tactical_duration', 'game_duration', 'cooldown_duration'
        ]
        widgets = {
            'session_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Helyszín neve...'}),
            
            # Rejtett mezők, mert a JS csúszkák fogják állítani az értéküket
            'toy_duration': forms.HiddenInput(),
            'warmup_duration': forms.HiddenInput(),
            'technical_duration': forms.HiddenInput(),
            'tactical_duration': forms.HiddenInput(),
            'game_duration': forms.HiddenInput(),
            'cooldown_duration': forms.HiddenInput(),
            
            # A Checkbox stílusozása
            'is_warmup_playful': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ha szükséges, itt is lehet dinamikusan szűrni vagy alapértelmezett értékeket adni
