# digiTTrain/users/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import Profile, Club, Role, Sport

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

class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(label="Vezetéknév", required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(label="Keresztnév", required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    date_of_birth = forms.DateField(label="Születési dátum", required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    gender = forms.ChoiceField(label="Nem", required=False, choices=Profile.GENDER_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = Profile
        fields = ['first_name', 'last_name', 'date_of_birth', 'gender', 'profile_picture']

class ClubForm(forms.ModelForm):
    # A sports mező most a Sport modellre mutat
    sports = forms.ModelMultipleChoiceField(
        queryset=Sport.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label="Sportágak"
    )
    class Meta:
        model = Club
        fields = ['name', 'short_name', 'address', 'logo', 'sports']
        labels = {
            'name': 'Egyesület teljes neve',
            'short_name': 'Egyesület rövid neve',
            'address': 'Cím',
            'logo': 'Egyesület logója'
        }

class RoleSelectionForm(forms.Form):
    # A Role modellhez most már nem kell queryset, a choices a modellben van
    role = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        label="Válassz szerepkört",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'role-selection'})
    )

class ClubSportSelectionForm(forms.Form):
    # A sportot is választani kell a Club modelből
    club = forms.ModelChoiceField(
        queryset=Club.objects.all(),
        label="Válassz egyesületet",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    sport = forms.ModelChoiceField(
        queryset=Sport.objects.all(),
        label="Válassz sportágat",
        widget=forms.Select(attrs={'class': 'form-select'})
    )