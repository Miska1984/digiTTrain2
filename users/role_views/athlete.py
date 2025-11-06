# users/role_views/athlete.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import date

from users.models import UserRole, Club, Sport, Role
from users.forms import AthleteRoleForm, UnderageAthleteRoleForm


def is_underage(user):
    """Ellenőrzi, hogy a felhasználó 18 év alatti-e."""
    if not hasattr(user, "profile") or not user.profile.date_of_birth:
        return False
    
    today = timezone.now().date()
    age = today.year - user.profile.date_of_birth.year - (
        (today.month, today.day) < (user.profile.date_of_birth.month, user.profile.date_of_birth.day)
    )
    return age < 18

@login_required
def create_athlete(request):
    kiskoru = is_underage(request.user)

    if request.method == "POST":
        if kiskoru:
            form = UnderageAthleteRoleForm(request.POST)
        else:
            form = AthleteRoleForm(request.POST)

        if form.is_valid():
            cleaned_data = form.cleaned_data
            
            # Ellenőrizzük, hogy létezik-e már ilyen kérés
            existing_role_query = {
                'user': request.user,
                'role': Role.objects.get(name="Sportoló"),
                'club': cleaned_data['club'],
                'sport': cleaned_data['sport'],
                'coach': cleaned_data['coach'],
            }
            if kiskoru:
                existing_role_query['parent'] = cleaned_data['parent']
            else:
                existing_role_query['parent'] = None
            
            # get_or_create használata a duplikáció elkerülésére
            athlete_role, created = UserRole.objects.get_or_create(
                **existing_role_query,
                defaults={
                    'status': 'pending',
                    'notes': cleaned_data.get('notes')
                }
            )

            if created:
                messages.success(request, "Sportoló szerepkör igénylés sikeresen beküldve!")
            else:
                messages.info(request, "Ez a szerepkör igénylés már létezik és függőben van.")

            return redirect("users:pending_roles")
    else:
        if kiskoru:
            form = UnderageAthleteRoleForm()
        else:
            form = AthleteRoleForm()

    return render(request, "users/roles/athlete/create_athlete.html", {
        "form": form,
        "kiskoru": kiskoru
    })

@login_required
def edit_athlete(request, role_id):
    """
    Meglévő Sportoló szerepkör szerkesztése és törlése.
    A felhasználó csak a saját sportoló szerepkörét törölheti.
    """
    athlete_role = get_object_or_404(
        UserRole,
        id=role_id,
        user=request.user,
        role__name="Sportoló",
    )

    if request.method == "POST":
        if "delete_role" in request.POST:
            athlete_role.delete()
            messages.success(request, "A sportoló szerepkör sikeresen törölve lett.")
            return redirect("core:main_page")

    context = {
        "role": athlete_role,
    }
    return render(request, "users/roles/athlete/edit_athlete.html", context)

# ======================
# AJAX ENDPOINTOK
# ======================

@login_required
def get_sports_by_club(request):
    """Adott klubhoz tartozó sportágak AJAX lekérdése"""
    club_id = request.GET.get("club_id")
    
    print(f"🔍 get_sports_by_club hívva - club_id: {club_id}")  # DEBUG
    
    if not club_id:
        print("❌ Hiányzó club_id!")
        return JsonResponse({"error": "Hiányzó club_id"}, status=400)

    try:
        # JAVÍTÁS: A Club modellen keresztül kérdezzük le a sportágakat
        club = Club.objects.get(id=club_id)
        sports = club.sports.all().values("id", "name")
        sports_list = list(sports)
        
        print(f"✅ Talált sportágak ({len(sports_list)} db): {sports_list}")  # DEBUG
        
        return JsonResponse(sports_list, safe=False)
    
    except Club.DoesNotExist:
        print(f"❌ Klub nem található: {club_id}")
        return JsonResponse({"error": "Klub nem található"}, status=404)
    
    except Exception as e:
        print(f"❌ Hiba a sportágak lekérdezésekor: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def get_coaches_by_club_and_sport(request):
    """Adott klub + sport alapján az edzők AJAX lekérdése"""
    club_id = request.GET.get("club_id")
    sport_id = request.GET.get("sport_id")

    print(f"🔍 get_coaches_by_club_and_sport hívva - club_id: {club_id}, sport_id: {sport_id}")  # DEBUG

    if not club_id or not sport_id:
        print("❌ Hiányzó paraméterek!")
        return JsonResponse({"error": "Hiányzó paraméterek"}, status=400)

    try:
        coaches = UserRole.objects.filter(
            club_id=club_id,
            sport_id=sport_id,
            role__name="Edző",
            status="approved"
        ).select_related("user__profile")

        coach_list = []
        for coach in coaches:
            coach_list.append({
                "id": coach.user.id,
                "name": f"{coach.user.profile.first_name} {coach.user.profile.last_name}"
            })

        print(f"✅ Talált edzők ({len(coach_list)} db): {coach_list}")  # DEBUG
        
        return JsonResponse(coach_list, safe=False)
    
    except Exception as e:
        print(f"❌ Hiba az edzők lekérdezésekor: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)

@login_required
def get_parents_by_club_sport_and_coach(request):
    """Adott klub + sport + edző alapján a szülők AJAX lekérdése"""
    club_id = request.GET.get("club_id")
    sport_id = request.GET.get("sport_id")
    coach_id = request.GET.get("coach_id")

    print(f"🔍 get_parents_by_club_sport_and_coach hívva - club_id: {club_id}, sport_id: {sport_id}, coach_id: {coach_id}")  # DEBUG

    if not club_id or not sport_id or not coach_id:
        print("❌ Hiányzó paraméterek!")
        return JsonResponse({"error": "Hiányzó paraméterek"}, status=400)

    try:
        parents = UserRole.objects.filter(
            club_id=club_id,
            sport_id=sport_id,
            coach_id=coach_id,
            role__name="Szülő",
            status="approved"
        ).select_related("user__profile")

        parent_list = []
        for parent in parents:
            parent_list.append({
                "id": parent.user.id,
                "name": f"{parent.user.profile.first_name} {parent.user.profile.last_name}"
            })

        print(f"✅ Talált szülők ({len(parent_list)} db): {parent_list}")  # DEBUG
        
        return JsonResponse(parent_list, safe=False)
    
    except Exception as e:
        print(f"❌ Hiba a szülők lekérdezésekor: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)