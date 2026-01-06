# users/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model, login
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView
from formtools.wizard.views import SessionWizardView
from django.core.exceptions import ValidationError
from django.utils import timezone
import os
import json
import logging
from .forms import (
    UserRegistrationForm, ProfileForm, UserUpdateForm
)
from .models import Profile, UserRole

logger = logging.getLogger(__name__)

# Meglévő view-k (register, edit_profile stb.) - ezek változatlanok maradnak
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
    print("=" * 50)
    print("EDIT PROFILE VIEW KEZDETE")
    print("=" * 50)
    
    profile, created = Profile.objects.get_or_create(user=request.user)
    if created:
        print(f"🆕 Új profil jött létre a userhez: {request.user.username}")
    else:
        print(f"📋 Meglévő profil betöltve: {request.user.username}")

    if request.method == "POST":
        print("\n🔥 POST kérés érkezett a profil szerkesztéshez")
        print(f"🔍 Request.FILES tartalma: {list(request.FILES.keys())}")
        print(f"🔍 Request.POST tartalma: {dict(request.POST)}")
        
        # Storage backend ellenőrzése
        print(f"🔍 Aktív default_storage: {default_storage.__class__}")
        print(f"🔍 Build mode: {os.getenv('BUILD_MODE', 'false')}")
        
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileForm(request.POST, request.FILES, instance=profile)

        print(f"🔍 User form valid: {user_form.is_valid()}")
        print(f"🔍 Profile form valid: {profile_form.is_valid()}")
        
        if not user_form.is_valid():
            print(f"❌ User form hibák: {user_form.errors}")
        if not profile_form.is_valid():
            print(f"❌ Profile form hibák: {profile_form.errors}")

        if user_form.is_valid() and profile_form.is_valid():
            print("✅ Mindkét űrlap valid")
            
            # User mentése
            user = user_form.save()
            print(f"👤 User mentve: {user.username}")
            
            # Fájl ellenőrzése
            if "profile_picture" in request.FILES:
                uploaded_file = request.FILES["profile_picture"]
                print(f"📸 Feltöltött fájl: {uploaded_file.name} ({uploaded_file.size} bájt)")
                print(f"📸 Fájl típusa: {uploaded_file.content_type}")
                print(f"🔍 Fájl objektum: {type(uploaded_file)}")
            else:
                print("ℹ️ Nem érkezett új profilkép a POST-ban")

            try:
                # Profile mentése
                print("\n💾 Profile mentésének kezdete...")
                profile = profile_form.save(commit=False)
                profile.user = request.user
                
                # Ellenőrizzük a profile_picture storage beállítását
                if hasattr(profile, 'profile_picture') and profile.profile_picture:
                    print(f"🔍 Profile picture mező storage: {profile.profile_picture.storage.__class__}")
                    print(f"📂 Profile picture fájl név: {profile.profile_picture.name}")
                
                print("💾 Profile.save() hívás...")
                profile.save()
                print("✅ Profile.save() sikeres!")
                
                # Eredmény ellenőrzése
                if profile.profile_picture:
                    print(f"🔍 Mentett fájl név: {profile.profile_picture.name}")
                    
                    try:
                        file_url = profile.profile_picture.url
                        print(f"🌐 Generált URL: {file_url}")
                    except Exception as url_error:
                        print(f"❌ URL generálási hiba: {str(url_error)}")
                    
                    # Létezés ellenőrzése
                    try:
                        exists = default_storage.exists(profile.profile_picture.name)
                        print(f"🔍 Fájl létezik a storage-ban: {exists}")
                        
                        if exists:
                            try:
                                file_size = default_storage.size(profile.profile_picture.name)
                                print(f"🔍 Fájl mérete: {file_size} bájt")
                            except Exception as size_error:
                                print(f"❌ Méret lekérési hiba: {str(size_error)}")
                        else:
                            print("⚠️ FIGYELEM: A fájl nem található a storage-ban!")
                            
                    except Exception as exists_error:
                        print(f"❌ Létezés ellenőrzési hiba: {str(exists_error)}")
                else:
                    print("ℹ️ Nincs profile_picture a mentett profilban")
                
                messages.success(request, "✅ A profil sikeresen frissítve!")
                print("🎉 Sikeres mentés - redirect")
                return redirect("users:edit_profile")

            except Exception as e:
                print(f"❌ HIBA TÖRTÉNT A PROFIL MENTÉSEKOR: {str(e)}")
                print("🔍 Hiba típusa:", type(e).__name__)
                import traceback
                print("📋 Teljes stack trace:")
                traceback.print_exc()
                
                messages.error(request, f"⚠️ Hiba történt a profil mentésekor: {str(e)}")
                return redirect("users:edit_profile")
                
        else:
            print("❌ Űrlap validációs hiba")
            messages.error(request, "⚠️ Hiba történt! Ellenőrizd az űrlap adatait.")
    else:
        print("\n📤 GET kérés: űrlap inicializálása")
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileForm(instance=profile)
        
        # Jelenlegi profil állapot
        if profile.profile_picture:
            print(f"🖼️ Jelenlegi profilkép: {profile.profile_picture.name}")
            try:
                print(f"🌐 Jelenlegi URL: {profile.profile_picture.url}")
            except Exception as e:
                print(f"❌ URL lekérési hiba: {str(e)}")
        else:
            print("ℹ️ Nincs jelenlegi profilkép")

    print("=" * 50)
    print("EDIT PROFILE VIEW VÉGE")
    print("=" * 50)

    return render(request, "users/edit_profile.html", {
        "user_form": user_form,
        "profile_form": profile_form,
    })

@login_required
def role_dashboard(request):
    """
    A felhasználó szerepkör vezérlőpultját megjelenítő nézet.
    Megjeleníti a meglévő szerepköröket és a hozzáadásukhoz szükséges gombokat.
    """
    # Lekérdezzük az aktuális felhasználóhoz tartozó összes UserRole-t
    user_roles = UserRole.objects.filter(user=request.user)
    
    context = {
        'user_roles': user_roles,
    }
    
    return render(request, 'users/roles/role_dashboard.html', context)

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        