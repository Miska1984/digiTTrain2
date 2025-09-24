# data_sharing/sharing_views/coach.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from users.models import UserRole, Sport, Club
from data_sharing.models import BiometricSharingPermission
from django.apps import apps
from users.utils import has_role


def _get_model_display_name(app_name, table_name):
    try:
        model = apps.get_model(app_label=app_name, model_name=table_name)
        return model._meta.verbose_name
    except LookupError:
        return table_name

@login_required
def coach_dashboard(request):
    """
    Edzői dashboard – az edzőhöz rendelt sportolók listázása.
    """
    coach = request.user
    if not has_role(coach, "Edző"):
        messages.error(request, "Nincs edzői szerepköröd.")
        return redirect("core:main_page")

    # Az edző saját szerepei (Edző)
    coach_roles = UserRole.objects.filter(
        user=coach,
        role__name="Edző",
        status="approved"
    )

    if not coach_roles.exists():
        messages.info(request, "Nincs jóváhagyott edzői szereped.")
        return render(request, "data_sharing/coach/dashboard.html", {"coach_roles": []})

    # Sportolók, akik ugyanabban a klubban és sportágban vannak, mint az edző
    athlete_roles = UserRole.objects.filter(
        role__name="Sportoló",
        status="approved",
        club__in=coach_roles.values("club"),
        sport__in=coach_roles.values("sport")
    ).select_related("user__profile", "sport", "club")

    context = {
        "athlete_roles": athlete_roles,
    }
    return render(request, "data_sharing/coach/dashboard.html", context)


@login_required
def athlete_detail(request, athlete_id):
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

    # mindig sportoló -> user
    permissions = BiometricSharingPermission.objects.filter(
        user=role.user,
        target_user=coach,
        enabled=True
    )

    shared_tables = [{
        "app_name": perm.app_name,
        "table_name": perm.table_name,
        "display_name": _get_model_display_name(perm.app_name, perm.table_name),
    } for perm in permissions]

    context = {
        "athlete": role.user,
        "role": role,
        "shared_tables": shared_tables,
    }
    return render(request, "data_sharing/coach/athlete_detail.html", context)
