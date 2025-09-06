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
        profile.user = request.user
        profile.save()

    if request.method == "POST":
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileForm(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            # ✅ commit=False, hogy belenyúlhassunk
            instance = profile_form.save(commit=False)

            # Debug – van-e fájl ténylegesen feltöltve?
            uploaded_file = request.FILES.get("profile_picture")
            if uploaded_file:
                print(f"📸 Feltöltött fájl a POST-ban: {uploaded_file.name}")
            else:
                print("⚠️ Nincs fájl a request.FILES-ben!")

            # Mentés a storage-ba
            instance.user = request.user
            instance.save()  # <-- itt kell tényleg elindulnia a feltöltésnek

            # Debug: nézzük meg a mentett példányt
            if instance.profile_picture:
                print(f"✅ Mentett fájl neve: {instance.profile_picture.name}")
                try:
                    print(f"🌍 Mentett fájl URL: {instance.profile_picture.url}")
                except Exception as e:
                    print(f"⚠️ Nem tudtam lekérni az URL-t: {e}")
            else:
                print("⚠️ A profilpéldányban nincs kép!")

            user_form.save()
            messages.success(request, "✅ A profil sikeresen frissítve!")
            return redirect("users:edit_profile")
        else:
            print("❌ Form hiba:", user_form.errors, profile_form.errors)
            messages.error(request, "⚠️ Hiba történt! Ellenőrizd az űrlap adatait.")
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileForm(instance=profile)

    return render(request, "users/edit_profile.html", {
        "user_form": user_form,
        "profile_form": profile_form,
    })