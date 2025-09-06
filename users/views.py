# users/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model, login
from .forms import UserRegistrationForm, ProfileForm, UserUpdateForm
from .models import Profile

User = get_user_model()

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) # Automatikus bejelentkezés regisztráció után
            username = form.cleaned_data.get('username')
            messages.success(request, f'Sikeres regisztráció, {username}! Most már bejelentkezve vagy.')
            return redirect('core:main_page')
    else:
        form = UserRegistrationForm()
    return render(request, 'users/register.html', {'form': form})


@login_required
def edit_profile(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    if created:
        # Ha új profil jön létre, biztosítjuk, hogy a user hozzá legyen rendelve
        profile.user = request.user
        profile.save()

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileForm(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            instance = profile_form.save()

            # Debug log - csak ha tényleg van feltöltött fájl
            if instance.profile_picture:
                print("Mentett fájl neve:", instance.profile_picture.name)
                print("Mentett fájl URL:", instance.profile_picture.url)
            else:
                print("⚠️ Nincs feltöltött kép ehhez a profilhoz.")

            messages.success(request, '✅ A profil sikeresen frissítve!')
            return redirect('users:edit_profile')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileForm(instance=profile)

    return render(request, 'users/edit_profile.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })
