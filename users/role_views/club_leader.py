from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from django import forms
from users.models import UserRole, Club, Sport, Role
from users.forms import ClubForm, UserRoleForm


@login_required
def create_club_and_leader_role(request):
    """Új klub és egyesületi vezető szerepkör létrehozása."""
    if request.method == "POST":
        club_form = ClubForm(request.POST, request.FILES)
        user_role_form = UserRoleForm(request.POST)

        if club_form.is_valid() and user_role_form.is_valid():
            sports = club_form.cleaned_data.get("sports")

            if not sports:
                messages.error(request, "Legalább egy sportágat ki kell választani.")
            else:
                try:
                    with transaction.atomic():
                        # klub mentés
                        club = club_form.save(commit=False)
                        club.creator = request.user
                        club.save()
                        club.sports.set(sports)

                        # szerepkör mentés
                        user_role = user_role_form.save(commit=False)
                        user_role.user = request.user
                        user_role.club = club
                        user_role.role = Role.objects.get(name="Egyesületi vezető")
                        
                        # ⚡ kötelező sport kiválasztása → az első klubhoz rendelt sport
                        if sports.exists():
                            user_role.sport = sports.first()

                        user_role.save()
                        
                        # ---------------------------
                        # A JAVASLAT BEILLESZTÉSI PONTJA
                        # ---------------------------
                        # A szerepkör automatikus jóváhagyása
                        if user_role.role.name == 'Egyesületi vezető':
                            user_role.status = 'approved'
                            user_role.approved_by = request.user
                            user_role.approved_at = timezone.now() # Fontos: a jóváhagyás idejét is rögzíteni kell
                            user_role.save(update_fields=['status', 'approved_by', 'approved_at'])

                    messages.success(request, "A klub és a szerepkör sikeresen létrehozva.")
                    return redirect("core:main_page")

                except Exception as e:
                    messages.error(request, f"Hiba történt a mentés során: {e}")
                    print("DEBUG ERROR:", e)  # fejlesztésnél hasznos
        else:
            print("DEBUG Club form errors:", club_form.errors)
            print("DEBUG UserRole form errors:", user_role_form.errors)
    else:
        club_form = ClubForm()
        user_role_form = UserRoleForm()

    context = {
        "club_form": club_form,
        "user_role_form": user_role_form,
    }
    return render(request, "users/roles/club_leader/create_club.html", context)

@login_required
def edit_club_leader_role(request, role_id):
    """Meglévő klub és egyesületi vezető szerepkör szerkesztése."""
    user_role = get_object_or_404(UserRole, pk=role_id, user=request.user)
    club = user_role.club

    # Azok a sportágak, ahol van edző
    locked_sport_ids = list(Sport.objects.filter(
        userrole__club=club,
        userrole__role__name="Edző"
    ).values_list('id', flat=True))

    if request.method == "POST":
        # Űrlapok inicializálása a POST adatokkal és a meglévő példánnyal
        club_form = ClubForm(request.POST, request.FILES, instance=club)
        # Itt kellene lennie egy user_role_form inicializálásnak is, de a sablonból kivetted
        
        # A törlés logikája, ha a gombot megnyomták
        if "delete_role" in request.POST:
             try:
                with transaction.atomic():
                    # Mivel a Club modell a UserRole-ra mutat,
                    # a Club törlése automatikusan törli a hozzárendelt user_role-t
                    club.delete()
                messages.success(request, "A szerepkör és a klub sikeresen törölve.")
                return redirect("core:main_page")
             except Exception as e:
                messages.error(request, f"Hiba történt a törlés során: {e}")
                # Itt is meg kell adni a contextet, ha a render-t használod
                context = {
                    "user_role": user_role,
                    "club_form": club_form,
                    "locked_sport_ids": locked_sport_ids,
                }
                return render(request, "users/roles/club_leader/edit_club.html", context)

        # Ha a mentés gombot nyomták meg
        if club_form.is_valid():
            sports = club_form.cleaned_data.get("sports")

            # locked sportokat mindig hozzáadjuk, még ha nincs bepipálva sem
            final_sports = list(sports) + locked_sport_ids
            
            try:
                with transaction.atomic():
                    club = club_form.save()
                    club.sports.set(final_sports)

                messages.success(request, "A klub adatai frissítve.")
                return redirect("core:main_page")

            except Exception as e:
                messages.error(request, f"Hiba történt a mentés során: {e}")
                print("DEBUG ERROR:", e)

    else:
        # GET kérés esetén
        club_form = ClubForm(instance=club)

    # A context szótár inicializálása a hiba elkerülése érdekében
    context = {
        "user_role": user_role,
        "club_form": club_form,
        "locked_sport_ids": locked_sport_ids,
    }
    
    return render(request, "users/roles/club_leader/edit_club.html", context)