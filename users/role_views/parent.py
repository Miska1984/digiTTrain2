# users/role_views/parent.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q
from django.urls import reverse 

from users.models import UserRole, Role, Club, Sport, User, ParentChild
from users.forms import ParentRoleForm

@login_required
def create_parent(request):
    """Szülői szerepkör létrehozása"""
    role = get_object_or_404(Role, name="Szülő")

    if request.method == "POST":
        form = ParentRoleForm(request.POST)
        if form.is_valid():
            club = form.cleaned_data.get('club')
            sport = form.cleaned_data.get('sport')
            coach = form.cleaned_data.get('coach')
            notes = form.cleaned_data.get('notes')

            if not club or not sport or not coach:
                if not club:
                    form.add_error('club', 'Kérjük, válassza ki a klubot.')
                if not sport:
                    form.add_error('sport', 'Kérjük, válassza ki a sportágat.')
                if not coach:
                    form.add_error('coach', 'Kérjük, válassza ki az edzőt.')

                messages.error(request, "Hiányzó adatok! Kérjük, válasszon klubot, sportágat és edzőt.")
                return render(request, "users/roles/parent/create_parent.html", {"form": form})

            UserRole.objects.create(
                user=request.user,
                role=role,
                club=club,
                sport=sport,
                coach=coach,
                notes=notes,
                status="pending"
            )
            messages.success(request, "Szülői szerepkör igény elküldve, jóváhagyásra vár.")
            return redirect(reverse("core:main_page")) # Itt van a változás!
        
    else:
        form = ParentRoleForm()

    return render(request, "users/roles/parent/create_parent.html", {"form": form})



@login_required
def edit_parent(request, role_id):
    parent_role = get_object_or_404(UserRole, id=role_id, user=request.user, role__name="Szülő")

    # A ParentChild modellt használjuk a szülőhöz rendelt sportolók ellenőrzésére.
    has_children = ParentChild.objects.filter(parent=request.user).exists()

    if request.method == "POST":
        if "delete_role" in request.POST:
            if has_children:
                messages.error(request, "A szülői szerepkör nem törölhető, mert vannak hozzárendelt sportolók.")
            else:
                parent_role.delete()
                messages.success(request, "A szülői szerepkör törölve lett.")
                return redirect("core:main_page")
    
    context = {
        "role": parent_role,
        "has_children": has_children,
    }
    return render(request, "users/roles/parent/edit_parent.html", context)


# ---------- AJAX ENDPOINTOK ----------

@login_required
def get_sports_by_club(request):
    """Adott klubhoz tartozó sportágak visszaadása"""
    club_id = request.GET.get("club_id")
    sports = Sport.objects.filter(clubs__id=club_id).distinct()
    data = [{"id": s.id, "name": s.name} for s in sports]
    return JsonResponse({"sports": data})


@login_required
def get_coaches_by_club_and_sport(request):
    """Adott klub + sport alapján visszaadja az edzőket"""
    club_id = request.GET.get("club_id")
    sport_id = request.GET.get("sport_id")

    coaches = User.objects.filter(
        user_roles__role__name="Edző",
        user_roles__club_id=club_id,
        user_roles__sport_id=sport_id,
        user_roles__status="approved",
    ).distinct().select_related('profile')

    coaches_data = []
    for coach in coaches:
        full_name = coach.username
        # Ha van kereszt- és vezetéknév, használd azt a teljes név helyett
        if hasattr(coach, 'profile') and coach.profile.first_name and coach.profile.last_name:
            full_name = f"{coach.profile.first_name} {coach.profile.last_name}"
        
        coaches_data.append({
            'id': coach.id,
            'name': full_name,  # Ezt a nevet fogja a JavaScript használni
        })

    return JsonResponse({'coaches': coaches_data})
