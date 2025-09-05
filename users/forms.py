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
    # Itt módosítjuk a mező nevét, hogy megegyezzen a modellel
    profile_picture = forms.ImageField(required=False)

    class Meta:
        model = Profile
        fields = ['first_name', 'last_name', 'date_of_birth', 'gender', 'profile_picture']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }
