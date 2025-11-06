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
    
    # 1. Lekérdezi a bemeneti ID-ket
    club_id = request.GET.get("club_id")
    sport_id = request.GET.get("sport_id")

    # Ha hiányzik valamelyik ID, térjünk vissza azonnal
    if not club_id or not sport_id:
        return JsonResponse({'coaches': []})
    
    # 2. Keresd meg a Role ID-t
    try:
        # A Role név alapján keressük meg az objektumot.
        coach_role = Role.objects.get(name="Edző")
    except Role.DoesNotExist:
        return JsonResponse({'coaches': []})

    # 3. Futtassa a szigorú szűrést
    coaches = User.objects.filter(
        # Szerepkör: Edző (Role ID 2)
        user_roles__role=coach_role, 
        # Club ID 1
        user_roles__club_id=club_id,
        # Sport ID 2
        user_roles__sport_id=sport_id,
        # Státusz: Jóváhagyott
        user_roles__status="approved",
    ).distinct().select_related('profile')

    # 4. JSON adatok előkészítése
    coaches_data = []
    for coach in coaches:
        full_name = coach.username
        # Teljes név generálása
        if hasattr(coach, 'profile') and coach.profile.first_name and coach.profile.last_name:
            full_name = f"{coach.profile.first_name} {coach.profile.last_name}"
        
        coaches_data.append({
            'id': coach.id,
            'name': full_name,
        })

    # 5. Válasz visszaadása
    return JsonResponse({'coaches': coaches_data})

