from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.http import HttpResponseForbidden
from users.models import UserRole, User
from .models import BiometricSharingPermission
from biometric_data.models import WeightData
from django.apps import apps
from django.conf import settings


# Segédfüggvény a modell nevének lekérésére
def _get_model_display_name(app_name, table_name):
    try:
        model = apps.get_model(app_label=app_name, model_name=table_name)
        return model._meta.verbose_name
    except LookupError:
        return table_name

@csrf_exempt
def toggle_permission(request):
    if request.method == 'POST':
        data_owner_id = request.POST.get('data_owner_id')
        target_user_id = request.POST.get('target_user_id')
        app_name = request.POST.get('app_name')
        table_name = request.POST.get('table_name')

        try:
            raw_owner = User.objects.get(id=data_owner_id)
            target_user = User.objects.get(id=target_user_id)

            # Ha a felhasználó kiskorú sportoló, akkor mindig a sportoló a data_owner
            if not raw_owner.is_adult:
                sport_role = raw_owner.user_roles.filter(role__name="Sportoló", status="approved").first()
                if sport_role:
                    data_owner = sport_role.user
                else:
                    data_owner = raw_owner
            else:
                data_owner = raw_owner

            permission, created = BiometricSharingPermission.objects.get_or_create(
                user=data_owner,  # mindig a sportoló
                target_user=target_user,
                app_name=app_name,
                table_name=table_name
            )

            permission.enabled = not permission.enabled
            permission.save()

            return JsonResponse({'success': True, 'enabled': permission.enabled})

        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'}, status=400)

    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)

def _get_full_name(user):
    """Teljes név a Profile-ból, ha nincs akkor username"""
    if hasattr(user, "profile"):
        full_name = f"{user.profile.first_name} {user.profile.last_name}".strip()
        if full_name:
            return full_name
    return user.username

@login_required
def data_sharing_center(request):
    user = request.user
    shareable_roles = UserRole.objects.filter(
        Q(user=user, role__name="Sportoló", status="approved") |
        Q(parent=user, role__name="Sportoló", status="approved")
    ).select_related('club', 'sport', 'user__profile', 'coach', 'parent')

    if not shareable_roles.exists():
        messages.warning(request, "Nincs jóváhagyott sportoló szerepkör, ezért nem tudsz adatokat megosztani.")
        return render(request, 'data_sharing/sharing_center.html', {"matrices_data": []})

    matrices_data = []

    for role in shareable_roles:
        data_owner = role.user
        target_users = []

        # --- Felnőtt sportoló ---
        if data_owner.is_adult:
            if role.coach:
                target_users.append({
                    "user": role.coach,
                    "role_type": "coach",
                    "role_display": "Edző",
                    "display_name": _get_full_name(role.coach),
                })
            if role.club:
                leaders = UserRole.objects.filter(
                    club=role.club,
                    role__name="Egyesületi vezető",
                    status="approved"
                ).select_related("user__profile")
                for leader_role in leaders:
                    target_users.append({
                        "user": leader_role.user,
                        "role_type": "leader",
                        "role_display": "Egyesületi vezető",
                        "display_name": _get_full_name(leader_role.user),
                    })

        # --- Kiskorú sportoló ---
        else:
            if role.parent:
                target_users.append({
                    "user": role.parent,
                    "role_type": "parent",
                    "role_display": "Szülő",
                    "display_name": _get_full_name(role.parent),
                })
                if request.user == role.parent:
                    if role.coach:
                        target_users.append({
                            "user": role.coach,
                            "role_type": "coach",
                            "role_display": "Edző (szülő által)",
                            "display_name": _get_full_name(role.coach),
                        })
                    if role.club:
                        leaders = UserRole.objects.filter(
                            club=role.club,
                            role__name="Egyesületi vezető",
                            status="approved"
                        ).select_related("user__profile")
                        for leader_role in leaders:
                            target_users.append({
                                "user": leader_role.user,
                                "role_type": "leader",
                                "role_display": "Egyesületi vezető (szülő által)",
                                "display_name": _get_full_name(leader_role.user),
                            })

        # --- Mátrix sorok összeállítása ---
        shareable_models = getattr(settings, 'SHAREABLE_DATA_MODELS', {})
        matrix_rows = []
        for app_name, table_names in shareable_models.items():
            for table_name in table_names:
                row_data = {
                    'app_name': app_name,
                    'table_name': table_name,
                    'display_name': _get_model_display_name(app_name, table_name),
                    'permissions': {}
                }
                for target in target_users:
                    permission = BiometricSharingPermission.objects.filter(
                        user=data_owner,
                        target_user=target['user'],
                        app_name=app_name,
                        table_name=table_name
                    ).first()
                    row_data['permissions'][str(target['user'].id)] = permission.enabled if permission else False
                matrix_rows.append(row_data)

        matrices_data.append({
            'sport_role': role,
            'data_owner': data_owner,
            'target_users': target_users,
            'matrix_rows': matrix_rows,
            'is_parent_managing': (role.parent == user),
            'child_name': _get_full_name(role.user) if role.parent == user else None,
        })

    context = {
        'matrices_data': matrices_data,
        'page_title': 'Adatmegosztási Központ',
        'is_parent': shareable_roles.filter(parent=user).exists(),
    }
    return render(request, 'data_sharing/sharing_center.html', context)


@login_required
def shared_data_view(request):
    user = request.user
    
    permissions = BiometricSharingPermission.objects.filter(
        target_user=user,
        enabled=True
    ).select_related('user').order_by('user__username', 'app_name', 'table_name')
    
    shared_data_by_user = {}
    for perm in permissions:
        username = perm.user.username
        if username not in shared_data_by_user:
            shared_data_by_user[username] = {
                'user': perm.user,
                'shared_tables': []
            }
        
        shared_data_by_user[username]['shared_tables'].append({
            'app_name': perm.app_name,
            'table_name': perm.table_name,
            'display_name': _get_model_display_name(perm.app_name, perm.table_name)
        })
    
    return render(request, 'data_sharing/shared_data_view.html', {
        'shared_data_by_user': shared_data_by_user
    })

   