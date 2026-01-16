from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, Http404
from django.utils import timezone
from users.models import UserRole, Role, Club, Sport
from users.forms import CoachRoleForm
from ml_engine.ai_coach_service import DittaCoachService

ditta_service = DittaCoachService()


@login_required
def create_coach(request):
    """
    Új edzői szerepkör létrehozása.
    Amennyiben a felhasználó a klub egyesületi vezetője, a szerepkör automatikusan jóváhagyásra kerül.
    """
    if request.method == "POST":
        form = CoachRoleForm(request.POST)
        if form.is_valid():
            user_role = form.save(commit=False)
            user_role.user = request.user
            user_role.role = Role.objects.get(name="Edző")

            # Ellenőrizzük, hogy a felhasználó az adott klub egyesületi vezetője-e
            is_club_leader = UserRole.objects.filter(
                user=request.user, 
                club=user_role.club, 
                role__name="Egyesületi vezető",
                status="approved"
            ).exists()

            if is_club_leader:
                # Ha a felhasználó egyesületi vezető, azonnali jóváhagyás
                user_role.status = "approved"
                user_role.approved_by = request.user
                user_role.approved_at = timezone.now()
                messages.success(request, "Az edzői szerepkör automatikusan jóváhagyva lett.")
            else:
                # Más esetben jóváhagyásra várakozó státuszba kerül
                user_role.status = "pending"
                messages.success(request, "Edzői szerepkör sikeresen létrehozva, jóváhagyásra vár.")

            user_role.save()
            return redirect("users:pending_roles")
        else:
            messages.error(request, "Kérlek javítsd a hibákat a mentéshez.")
    else:
        form = CoachRoleForm()

    app_context = 'create_coach'
    welcome_message = ditta_service.get_ditta_response(request.user, app_context)

    return render(request, "users/roles/coach/create_coach.html", {
        "form": form,
        'app_context': app_context,
        'welcome_message': welcome_message,
    })

@login_required
def edit_coach_role(request, role_id):
    """
    Edző szerepkör szerkesztése, csak törlés engedélyezett
    (kivéve, ha vannak hozzárendelt sportolók)
    """
    role = get_object_or_404(UserRole, id=role_id, role__name="Edző")

    # Ellenőrizzük, hogy vannak-e hozzárendelt sportolók
    has_athletes = UserRole.objects.filter(coach=role.user, role__name="Sportoló").exists()

    if request.method == "POST":
        if "delete_role" in request.POST:
            if has_athletes:
                messages.error(request, "A szerepkör nem törölhető, mert vannak hozzárendelt sportolók.")
            else:
                role.delete()
                messages.success(request, "Az edző szerepkör törölve lett.")
                return redirect("users:pending_roles")

        # Mivel a szerkesztés nem engedélyezett, a POST kérések csak a törlést kezelik
        # Ha más is van a POST-ban, azt figyelmen kívül hagyjuk
        # A `return redirect` biztosítja, hogy sikeres törlés után elhagyja az oldalt
    
    app_context = 'create_coach'
    welcome_message = ditta_service.get_ditta_response(request.user, app_context)

    context = {
        "role": role,
        "has_athletes": has_athletes,
        'app_context': app_context,
        'welcome_message': welcome_message,
    }
    return render(request, "users/roles/coach/edit_coach.html", context)


@login_required
def get_sports_for_club(request, club_id):
    """Visszaadja az adott klubhoz tartozó sportágakat JSON formátumban."""
    try:
        club = Club.objects.get(pk=club_id)
        sports = club.sports.all().values("id", "name")
        return JsonResponse({"sports": list(sports)})
    except Club.DoesNotExist:
        return JsonResponse({"sports": []})


@login_required
def get_sports_for_club(request, club_id):
    """
    AJAX endpoint – visszaadja a klub sportágait
    """
    try:
        club = Club.objects.get(id=club_id)
    except Club.DoesNotExist:
        raise Http404("A klub nem létezik")

    sports = club.sports.all().values("id", "name")
    return JsonResponse({"sports": list(sports)})