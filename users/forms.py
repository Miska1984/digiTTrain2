# digiTTrain/users/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordResetForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q
from .models import Profile, Club, Sport, UserRole
import logging

logger = logging.getLogger(__name__)

# Mindig a settings.AUTH_USER_MODEL-t használja
User = get_user_model()

class UserRegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email']

class CustomLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['username'].widget = forms.TextInput(attrs={
            'class': 'form-control', # ✅ Ez biztosítja a Bootstrap stílust
            'placeholder': 'Felhasználónév',
        })
        
        self.fields['password'].widget = forms.PasswordInput(attrs={
            'class': 'form-control', # ✅ Ez biztosítja a Bootstrap stílust
            'placeholder': 'Jelszó',
        })

class CustomPasswordResetForm(PasswordResetForm):
    # A PasswordResetForm egyetlen mezője az 'email'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hozzáadjuk a form-control osztályt a beviteli mezőhöz
        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Adja meg email címét', # Segít a felhasználónak
            'aria-label': 'Email cím',
        })

class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(
        label="Vezetéknév", required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        label="Keresztnév", required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    date_of_birth = forms.DateField(
        label="Születési dátum",
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        input_formats=['%Y-%m-%d'],   # fontos!
    )
    gender = forms.ChoiceField(
        label="Nem", required=False,
        choices=Profile.GENDER_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Profile
        fields = ['first_name', 'last_name', 'date_of_birth', 'gender', 'profile_picture']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ha van date_of_birth, állítsuk be helyesen az initial értéket
        if self.instance and self.instance.date_of_birth:
            self.initial['date_of_birth'] = self.instance.date_of_birth.strftime('%Y-%m-%d')

class ClubForm(forms.ModelForm):
    sports = forms.ModelMultipleChoiceField(
        queryset=Sport.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Sportágak"
    )

    class Meta:
        model = Club
        fields = ['name', 'short_name', 'address', 'logo', 'sports']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'short_name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def clean_sports(self):
        sports = self.cleaned_data.get('sports')
        if not sports or len(sports) < 1:
            raise forms.ValidationError("Legalább egy sportágat ki kell választani.")
        return sports

class UserRoleForm(forms.ModelForm):
    class Meta:
        model = UserRole
        fields = ["sport", "notes"]
        widgets = {
            "sport": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sport"].required = False  # ⚡ NE legyen kötelező

class CoachRoleForm(forms.ModelForm):
    class Meta:
        model = UserRole
        fields = ["club", "sport", "notes"]
        widgets = {
            "club": forms.Select(attrs={"class": "form-select"}),
            "sport": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        # A sport_choices paraméter eltávolítása a kwargs-ből, ha létezik
        sport_choices = kwargs.pop('sport_choices', None)
        super().__init__(*args, **kwargs)

        # Csak azok a klubok, ahol van jóváhagyott vezető
        self.fields["club"].queryset = Club.objects.filter(
            userrole__role__name="Egyesületi vezető",
            userrole__status="approved"
        ).distinct()

        # Ha átadtak sport_choices paramétert, használjuk azt a queryset-hez
        if sport_choices is not None:
            self.fields['sport'].queryset = sport_choices
        else:
            # Ha nincs sport_choices paraméter (pl. create_coach nézetben),
            # akkor az alapértelmezett viselkedés marad.
            # Az ajax hívás miatt a create nézetben ezt a queryset-et nem használjuk,
            # de a kód olvashatósága és a jövőbeni bővítés miatt ez a fallback hasznos.
            self.fields['sport'].queryset = Sport.objects.all()
            
class ParentRoleForm(forms.ModelForm):
    # A mezők explicit definiálása kötelező, de most már a queryset-et nem init-ben állítjuk
    club = forms.ModelChoiceField(
        queryset=Club.objects.filter(
            userrole__role__name="Egyesületi vezető",
            userrole__status="approved"
        ).distinct(),
        label="Klub",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    sport = forms.ModelChoiceField(
        queryset=Sport.objects.all(),
        label="Sportág",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    coach = forms.ModelChoiceField(
        queryset=User.objects.all(),
        label="Edző",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        required=False,
        label="Megjegyzések"
    )

    def label_from_instance(self, obj):
        # Ha a felhasználónak van kereszt- és vezetékneve a profiljában
        if hasattr(obj, 'profile') and obj.profile.first_name and obj.profile.last_name:
            return f"{obj.profile.first_name} {obj.profile.last_name}"
        # Ha nincs, akkor a felhasználónevet adja vissza
        return obj.username

    class Meta:
        model = UserRole
        fields = ["club", "sport", "coach", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ne szűkítsd a queryset-et az init-ben, mert a POST kérés feldolgozásakor
        # az üres lesz, és nem találja meg a küldött ID-t.
        # A sport és coach mezőknek is legyen valami alapértelmezett queryset-je.
        # Ha a form POST kéréssel érkezik, szűrd a queryset-eket itt:
        if self.is_bound:
            if self.data.get('club'):
                self.fields['sport'].queryset = Sport.objects.filter(
                    clubs__id=self.data.get('club')
                ).distinct()
            if self.data.get('club') and self.data.get('sport'):
                self.fields['coach'].queryset = User.objects.filter(
                    user_roles__role__name="Edző",
                    user_roles__club_id=self.data.get('club'),
                    user_roles__sport_id=self.data.get('sport'),
                    user_roles__status="approved",
                ).distinct()

class AthleteRoleForm(forms.ModelForm):
    coach = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label="Edző",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_coach"})
    )

    class Meta:
        model = UserRole
        fields = ["club", "sport", "coach", "notes"]
        widgets = {
            "club": forms.Select(attrs={"class": "form-select", "id": "id_club"}),
            "sport": forms.Select(attrs={"class": "form-select", "id": "id_sport"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "id": "id_notes", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["club"].queryset = Club.objects.filter(
            userrole__role__name="Egyesületi vezető",
            userrole__status="approved"
        ).distinct()

        if self.is_bound:
            if self.data.get('club'):
                self.fields['sport'].queryset = Sport.objects.filter(
                    clubs__id=self.data.get('club')
                ).distinct()
            if self.data.get('club') and self.data.get('sport'):
                self.fields['coach'].queryset = User.objects.filter(
                    user_roles__role__name="Edző",
                    user_roles__club_id=self.data.get('club'),
                    user_roles__sport_id=self.data.get('sport'),
                    user_roles__status="approved",
                ).distinct()


class UnderageAthleteRoleForm(AthleteRoleForm):
    parent = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label="Szülő",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_parent"})
    )

    class Meta(AthleteRoleForm.Meta):
        fields = AthleteRoleForm.Meta.fields + ["parent"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            if self.data.get('club'):
                self.fields['sport'].queryset = Sport.objects.filter(
                    clubs__id=self.data.get('club')
                ).distinct()
            if self.data.get('club') and self.data.get('sport'):
                self.fields['coach'].queryset = User.objects.filter(
                    user_roles__role__name="Edző",
                    user_roles__club_id=self.data.get('club'),
                    user_roles__sport_id=self.data.get('sport'),
                    user_roles__status="approved",
                ).distinct()
            if self.data.get('club') and self.data.get('sport') and self.data.get('coach'):
                self.fields['parent'].queryset = User.objects.filter(
                    user_roles__role__name="Szülő",
                    user_roles__club_id=self.data.get('club'),
                    user_roles__sport_id=self.data.get('sport'),
                    user_roles__coach_id=self.data.get('coach'),
                    user_roles__status="approved",
                ).distinct()
