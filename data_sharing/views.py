# data_sharing/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.apps import apps

from .models import BiometricSharingPermission
from users.models import UserRole


@login_required
def sharing_center(request):
    """
    Megosztási központ - itt állíthatja be a felhasználó, hogy kivel oszt meg adatokat
    """
    user = request.user
    
    # Lekérjük a felhasználó összes sportoló szerepkörét
    user_sport_roles = UserRole.objects.filter(
        user=user,
        role__name="Sportoló",
        status="approved"
    ).select_related('club', 'sport', 'coach', 'parent')
    
    # Ha nincs sportoló szerepköre, ellenőrizzük hogy szülő-e
    if not user_sport_roles.exists():
        # Szülő esetén a gyerekek sportoló szerepköreit kérjük le
        child_sport_roles = UserRole.objects.filter(
            parent=user,
            role__name="Sportoló", 
            status="approved"
        ).select_related('club', 'sport', 'coach', 'user')
        
        if child_sport_roles.exists():
            # Szülő esetén a gyerekek szerepköreit dolgozzuk fel
            matrices_data = []
            
            for child_role in child_sport_roles:
                matrix_data = _build_sharing_matrix(child_role.user, child_role)
                matrix_data['is_parent_managing'] = True
                matrix_data['child_name'] = child_role.user.username
                matrices_data.append(matrix_data)
                
            context = {
                'matrices_data': matrices_data,
                'is_parent': True,
            }
            return render(request, 'data_sharing/sharing_center.html', context)
    
    # Sportoló esetén saját szerepkörök feldolgozása
    matrices_data = []
    
    for sport_role in user_sport_roles:
        matrix_data = _build_sharing_matrix(user, sport_role)
        matrix_data['is_parent_managing'] = False
        matrices_data.append(matrix_data)
    
    if not matrices_data:
        messages.warning(request, "Nincs aktív sportoló szerepköröd, ezért nem tudsz adatokat megosztani.")
        return redirect('core:main_page')
    
    context = {
        'matrices_data': matrices_data,
        'is_parent': False,
    }
    
    return render(request, 'data_sharing/sharing_center.html', context)


def _build_sharing_matrix(data_owner, sport_role):
    """
    Egy sportoló szerepkörhöz építi fel a megosztási mátrixot
    """
    # Célfelhasználók (akikkel megoszthat)
    target_users = []
    
    # Edző hozzáadása (ha van)
    if sport_role.coach:
        target_users.append({
            'user': sport_role.coach,
            'role_type': 'coach',
            'role_display': 'Edző'
        })
    
    # Egyesületi vezető hozzáadása
    try:
        leader_role = UserRole.objects.get(
            club=sport_role.club,
            role__name="Egyesületi vezető",
            status="approved"
        )
        target_users.append({
            'user': leader_role.user,
            'role_type': 'leader',
            'role_display': 'Egyesületi vezető'
        })
    except UserRole.DoesNotExist:
        pass
    
    # Megosztható táblák lekérése a settings-ből
    shareable_models = getattr(settings, 'SHAREABLE_DATA_MODELS', {})
    
    # Mátrix adatok összeállítása
    matrix_rows = []
    
    for app_name, table_names in shareable_models.items():
        for table_name in table_names:
            row_data = {
                'app_name': app_name,
                'table_name': table_name,
                'display_name': _get_model_display_name(app_name, table_name),
                'permissions': {}
            }
            
            # Minden célfelhasználóhoz lekérni az engedélyt
            for target in target_users:
                try:
                    permission = BiometricSharingPermission.objects.get(
                        user=data_owner,
                        target_user=target['user'],
                        app_name=app_name,
                        table_name=table_name
                    )
                    row_data['permissions'][target['user'].id] = permission.enabled
                except BiometricSharingPermission.DoesNotExist:
                    row_data['permissions'][target['user'].id] = False
            
            matrix_rows.append(row_data)
    
    return {
        'sport_role': sport_role,
        'data_owner': data_owner,
        'target_users': target_users,
        'matrix_rows': matrix_rows
    }


def _get_model_display_name(app_name, table_name):
    """
    Visszaadja a model felhasználóbarát nevét
    """
    try:
        model = apps.get_model(app_name, table_name)
        return model._meta.verbose_name or table_name
    except:
        return table_name


@login_required
@require_http_methods(["POST"])
def toggle_permission(request):
    """
    AJAX endpoint a megosztási engedély be/kikapcsolásához
    """
    try:
        data_owner_id = request.POST.get('data_owner_id')
        target_user_id = request.POST.get('target_user_id')
        app_name = request.POST.get('app_name')
        table_name = request.POST.get('table_name')
        
        # Jogosultság ellenőrzés
        if not _can_manage_permissions(request.user, data_owner_id):
            return JsonResponse({'success': False, 'error': 'Nincs jogosultsága'})
        
        # Permission lekérése vagy létrehozása
        permission, created = BiometricSharingPermission.objects.get_or_create(
            user_id=data_owner_id,
            target_user_id=target_user_id,
            app_name=app_name,
            table_name=table_name,
            defaults={'enabled': True}
        )
        
        if not created:
            # Ha már létezett, akkor átváltjuk
            new_status = permission.toggle()
        else:
            new_status = True
        
        return JsonResponse({
            'success': True, 
            'enabled': new_status
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': str(e)
        })


def _can_manage_permissions(user, data_owner_id):
    """
    Ellenőrzi, hogy a user jogosult-e kezelni a data_owner engedélyeit
    """
    data_owner_id = int(data_owner_id)
    
    # Saját adatok mindig kezelhetők
    if user.id == data_owner_id:
        return True
    
    # Szülő kezelheti a gyerek adatait
    if UserRole.objects.filter(
        user_id=data_owner_id,
        parent=user,
        role__name="Sportoló",
        status="approved"
    ).exists():
        return True
    
    return False


@login_required
def shared_data_view(request):
    """
    Megjeleníti azokat az adatokat, amiket mások megosztottak vele
    """
    user = request.user
    
    # Lekérjük az összes engedélyt, ahol a user a target_user
    permissions = BiometricSharingPermission.objects.filter(
        target_user=user,
        enabled=True
    ).select_related('user').order_by('user__username', 'app_name', 'table_name')
    
    # Csoportosítás felhasználó szerint
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
    
    context = {
        'shared_data_by_user': shared_data_by_user
    }
    
    return render(request, 'data_sharing/shared_data_view.html', context)