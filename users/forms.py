# digiTTrain/users/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import Profile

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
    class Meta:
        model = Profile
        # Itt kell szerepelnie a 'profile_picture' mezőnek
        # Ha a `fields` lista expliciten van megadva, akkor minden mezőt fel kell sorolni.
        # Ha `fields = '__all__'` vagy nem adod meg, akkor minden mezőt tartalmaz.
        fields = ['first_name', 'last_name', 'date_of_birth', 'gender', 'profile_picture']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            # Ha a 'profile_picture' mezőnél szeretnél egyedi widgetet, itt megadhatod.
            # Például:
            # 'profile_picture': forms.ClearableFileInput(attrs={'multiple': False}),
        }