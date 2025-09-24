# data_sharing/sharing_views/parent.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from users.models import UserRole
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
def parent_dashboard(request):
    """
    Szülői dashboard – csak szülő szerepkörrel.
    """
    parent = request.user
    if not has_role(parent, "Szülő"):
        messages.error(request, "Nincs szülői szerepköröd.")
        return redirect("core:main_page")

    child_roles = UserRole.objects.filter(
        parent=parent,
        role__name="Sportoló",
        status="approved"
    ).select_related("user__profile", "sport", "club")

    context = {
        "child_roles": child_roles,
    }
    return render(request, "data_sharing/parent/dashboard.html", context)

@login_required
def child_detail(request, child_id):
    parent = request.user
    child_role = get_object_or_404(
        UserRole,
        user__id=child_id,
        parent=parent,
        role__name="Sportoló",
        status="approved"
    )
    child = child_role.user

    permissions = BiometricSharingPermission.objects.filter(
        user=child,
        enabled=True
    ).select_related("target_user")

    shared_tables = []
    for perm in permissions:
        # célzott felhasználó szerepkörének meghatározása
        role = perm.target_user.user_roles.filter(club=child_role.club, status="approved").first()
        role_name = role.role.name if role else "Ismeretlen szerepkör"

        shared_tables.append({
            "app_name": perm.app_name,
            "table_name": perm.table_name,
            "display_name": _get_model_display_name(perm.app_name, perm.table_name),
            "shared_with": perm.target_user,
            "shared_with_role": role_name,
        })

    context = {
        "child": child,
        "role": child_role,
        "shared_tables": shared_tables,
    }
    return render(request, "data_sharing/parent/child_detail.html", context)
