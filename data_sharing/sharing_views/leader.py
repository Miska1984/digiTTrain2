# data_sharing/sharing_views/leader.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from users.models import UserRole, Sport
from data_sharing.models import BiometricSharingPermission
from users.utils import has_role
from data_sharing.utils import get_model_display_name


@login_required
def leader_dashboard(request):
    """
    Egyesületi vezető dashboard – csak vezetői szerepkörrel.
    """
    leader = request.user
    if not has_role(leader, "Egyesületi vezető"):
        messages.error(request, "Hozzáférés megtagadva, nincs egyesületi vezetői szerepköröd.")
        return redirect("core:main_page")

    leader_roles = UserRole.objects.filter(user=leader, role__name="Egyesületi vezető", status="approved")
    club = leader_roles.first().club
    sports = club.sports.all()

    context = {"club": club, "sports": sports}
    return render(request, "data_sharing/leader/dashboard.html", context)


@login_required
def sport_detail(request, sport_id):
    """
    Egy adott sportág részletes adatai – csak vezető nézheti meg.
    """
    leader = request.user
    if not has_role(leader, "Egyesületi vezető"):
        messages.error(request, "Hozzáférés megtagadva, nincs egyesületi vezetői szerepköröd.")
        return redirect("core:main_page")

    leader_role = get_object_or_404(UserRole, user=leader, role__name="Egyesületi vezető", status="approved")
    club = leader_role.club
    sport = get_object_or_404(Sport, id=sport_id, clubs=club)

    athlete_roles = UserRole.objects.filter(
        club=club,
        sport=sport,
        role__name="Sportoló",
        status="approved"
    ).select_related("user__profile")

    athletes_with_data = []
    for role in athlete_roles:
        permissions = BiometricSharingPermission.objects.filter(
            user=role.user,
            target_user=leader,
            enabled=True
        )
        shared_tables = [{
            "app_name": perm.app_name,
            "table_name": perm.table_name,
            "display_name": get_model_display_name(perm.app_name, perm.table_name),
        } for perm in permissions]

        athletes_with_data.append({
            "athlete": role.user,
            "role": role,
            "shared_tables": shared_tables,
        })

    context = {"club": club, "sport": sport, "athletes_with_data": athletes_with_data}
    return render(request, "data_sharing/leader/sport_detail.html", context)
