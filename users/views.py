# users/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model, login
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST # ÚJ

from .forms import UserRegistrationForm, ProfileForm, UserUpdateForm, ClubForm, RoleSelectionForm, ClubSportSelectionForm
from .models import Profile, Club, UserRole, Role, Sport


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
        print(f"🆕 Új profil jött létre a userhez: {request.user.username}")

    if request.method == "POST":
        print("📩 POST kérés érkezett a profil szerkesztéshez")

        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileForm(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            print("✅ Mindkét űrlap valid")

            # Először a user mentése
            user_form.save()
            print(f"👤 User mentve: {request.user.username}")

            # Majd a profil mentése (fájlokkal együtt)
            profile = profile_form.save(commit=False)
            profile.user = request.user

            if "profile_picture" in request.FILES:
                uploaded_file = request.FILES["profile_picture"]
                print(f"📸 Feltöltött fájl: {uploaded_file.name} ({uploaded_file.size} bájt)")
            else:
                print("ℹ️ Nem érkezett új profilkép a POST-ban")

            try:
                profile.save()
                print(f"💾 Profil mentve adatbázisba. Kép útvonal: {profile.profile_picture.name}")

                if profile.profile_picture:
                    print(f"🌍 Publikus URL: {profile.profile_picture.url}")
                
                messages.success(request, "✅ A profil sikeresen frissítve!")
                return redirect("users:edit_profile")

            except Exception as e:
                print(f"❌ HIBA TÖRTÉNT A FÁJL MENTÉSEKOR: {e}")
                messages.error(request, f"⚠️ Hiba történt a fájl feltöltésekor: {e}")
                return redirect("users:edit_profile")
                
        else:
            print("❌ Hiba az űrlap validációban:")
            print("   User form errors:", user_form.errors)
            print("   Profile form errors:", profile_form.errors)
            messages.error(request, "⚠️ Hiba történt! Ellenőrizd az űrlap adatait.")
    else:
        print("📤 GET kérés: űrlap inicializálása")
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileForm(instance=profile)

    return render(request, "users/edit_profile.html", {
        "user_form": user_form,
        "profile_form": profile_form,
    })


@login_required
def new_role_view(request):
    form = RoleSelectionForm()
    context = {
        'form': form
    }
    return render(request, 'users/new_role.html', context)

@login_required
@require_POST
def club_create_ajax_view(request):
    club_form = ClubForm(request.POST, request.FILES)
    if club_form.is_valid():
        club = club_form.save(commit=False)
        club.creator = request.user
        club.save()

        try:
            role = Role.objects.get(name='Egyesületi vezető')
            UserRole.objects.create(
                user=request.user,
                role=role,
                club=club,
                sport=None
            )
            return JsonResponse({'success': True, 'redirect_url': str(reverse_lazy('core:main_page'))})
        except Role.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'A "Egyesületi vezető" szerepkör nem található.'})
    else:
        html_form = render_to_string('users/forms/club_form.html', {'form': club_form}, request=request)
        return JsonResponse({'success': False, 'html_form': html_form, 'error': 'Kérjük, javítsa a hibákat.'})

@login_required
@require_POST
def club_join_ajax_view(request):
    """
    Ez a nézet kezeli a meglévő klubhoz és sportághoz való csatlakozást.
    """
    club_sport_form = ClubSportSelectionForm(request.POST)
    if club_sport_form.is_valid():
        club = club_sport_form.cleaned_data['club']
        sport = club_sport_form.cleaned_data['sport']

        # Alapértelmezett szerepkör, pl. 'Sportoló'
        try:
            role = Role.objects.get(name='Sportoló')
            UserRole.objects.create(
                user=request.user,
                role=role,
                club=club,
                sport=sport
            )
            return JsonResponse({'success': True, 'redirect_url': str(reverse_lazy('core:main_page'))})
        except Role.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'A "Sportoló" szerepkör nem található.'})
    else:
        html_form = render_to_string('users/forms/club_sport_form.html', {'form': club_sport_form}, request=request)
        return JsonResponse({'success': False, 'html_form': html_form, 'error': 'Kérjük, javítsa a hibákat.'})

@login_required
def get_next_step_form(request, role_id):
    role = get_object_or_404(Role, pk=role_id)
    
    context = {}
    if role.name == 'Egyesületi vezető':
        form = ClubForm()
        context['form'] = form
        html_form = render_to_string('users/forms/club_form.html', context, request=request)
    else:
        form = ClubSportSelectionForm()
        context['form'] = form
        html_form = render_to_string('users/forms/club_sport_form.html', context, request=request)

    return JsonResponse({'html_form': html_form})