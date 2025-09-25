# data_sharing/sharing_views/coach.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from users.models import UserRole
from data_sharing.models import BiometricSharingPermission
from users.utils import has_role
from data_sharing.utils import get_model_display_name


@login_required
def coach_dashboard(request):
    """
    Edzői dashboard – csak edző szerepkörrel.
    """
    coach = request.user
    if not has_role(coach, "Edző"):
        messages.error(request, "Hozzáférés megtagadva, nincs edzői szerepköröd.")
        return redirect("core:main_page")

    coach_roles = UserRole.objects.filter(
        coach=coach,
        role__name="Sportoló",
        status="approved"
    ).select_related("user__profile", "sport", "club")

    context = {"coach_roles": coach_roles}
    return render(request, "data_sharing/coach/dashboard.html", context)


@login_required
def athlete_detail(request, athlete_id):
    """
    Egy adott sportoló részletes adatai – csak edző nézheti meg.
    """
    coach = request.user
    if not has_role(coach, "Edző"):
        messages.error(request, "Hozzáférés megtagadva, nincs edzői szerepköröd.")
        return redirect("core:main_page")

    role = get_object_or_404(
        UserRole,
        user__id=athlete_id,
        coach=coach,
        role__name="Sportoló",
        status="approved"
    )

    permissions = BiometricSharingPermission.objects.filter(
        user=role.user,
        target_user=coach,
        enabled=True
    )
    shared_tables = [{
        "app_name": perm.app_name,
        "table_name": perm.table_name,
        "display_name": get_model_display_name(perm.app_name, perm.table_name),
    } for perm in permissions]

    context = {
        "athlete": role.user,
        "role": role,
        "shared_tables": shared_tables,
    }
    return render(request, "data_sharing/coach/athlete_detail.html", context)
