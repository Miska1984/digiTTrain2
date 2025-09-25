# data_sharing/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from users.models import UserRole, User
from .models import BiometricSharingPermission
from django.conf import settings
from django.urls import reverse
from .utils import build_sharing_matrix, get_model_display_name


@csrf_exempt
def toggle_permission(request):
    if request.method == 'POST':
        data_owner_id = request.POST.get('data_owner_id')
        target_user_id = request.POST.get('target_user_id')
        app_name = request.POST.get('app_name')
        table_name = request.POST.get('table_name')

        try:
            data_owner = User.objects.get(id=data_owner_id)
            target_user = User.objects.get(id=target_user_id)
            
            permission, created = BiometricSharingPermission.objects.get_or_create(
                user=data_owner,
                target_user=target_user,
                app_name=app_name,
                table_name=table_name
            )
            
            permission.enabled = not permission.enabled
            permission.save()

            return JsonResponse({'success': True, 'enabled': permission.enabled})

        except (User.DoesNotExist, BiometricSharingPermission.DoesNotExist) as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)


@login_required
def data_sharing_center(request):
    user = request.user
    
    shareable_roles = UserRole.objects.filter(
        Q(user=user, role__name="Sportoló", status="approved") |
        Q(parent=user, role__name="Sportoló", status="approved")
    ).select_related('club', 'sport', 'user__profile', 'coach')

    if not shareable_roles.exists():
        messages.warning(request, "Nincs jóváhagyott sportoló szerepkör, ezért nem tudsz adatokat megosztani.")
        context = {'matrices_data': []}
        return render(request, 'data_sharing/sharing_center.html', context)

    matrices_data = []

    for role in shareable_roles:
        target_users = []
        data_owner = role.user
        
        # 1. Edző
        if role.coach:
            target_users.append({
                "user": role.coach,
                "role_type": "coach",
                "role_display": "Edző"
            })

        # 2. Egyesületi vezető
        if role.club:
            try:
                leader_role = UserRole.objects.get(
                    club=role.club,
                    role__name="Egyesületi vezető",
                    status="approved"
                )
                target_users.append({
                    "user": leader_role.user,
                    "role_type": "leader",
                    "role_display": "Egyesületi vezető"
                })
            except UserRole.DoesNotExist:
                pass
        
        # 3. Mátrix építése utils-ból
        matrix_rows = build_sharing_matrix(data_owner, target_users)

        matrices_data.append({
            'sport_role': role,
            'data_owner': data_owner,
            'target_users': target_users,
            'matrix_rows': matrix_rows,
            'is_parent_managing': (role.parent == user),
        })

    context = {
        'matrices_data': matrices_data,
        'page_title': 'Adatmegosztási Központ'
    }
    
    return render(request, 'data_sharing/sharing_center.html', context)


@login_required
def shared_data_view(request):
    """
    Megjeleníti azokat az adatokat, amiket mások megosztottak vele
    """
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
            'display_name': get_model_display_name(perm.app_name, perm.table_name)
        })
    
    context = {
        'shared_data_by_user': shared_data_by_user
    }
    
    return render(request, 'data_sharing/shared_data_view.html', context)
