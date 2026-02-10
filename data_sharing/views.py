# data_sharing/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from users.models import UserRole, User
from .models import DataSharingPermission  # FRISSÍTVE
from django.conf import settings
from django.urls import reverse
from .utils import build_sharing_matrix, get_model_display_name

@login_required
@csrf_exempt
def toggle_permission(request):
    if request.method == 'POST':
        try:
            print(f"DEBUG POST DATA: {request.POST}")    

            data_owner_id = request.POST.get('data_owner_id')
            target_user_id = request.POST.get('target_user_id')
            target_role_id = request.POST.get('target_role_id')
            app_name = request.POST.get('app_name')
            table_name = request.POST.get('table_name')

            # Csak azokat a mezőket várjuk el kötelezően, amik tényleg mindig kellenek
            # A target_role_id lehet '0' vagy üres szülők esetén
            if not all([data_owner_id, target_user_id, app_name, table_name]):
                return JsonResponse({'success': False, 'error': 'Hiányzó alapadatok.'}, status=400)

            data_owner = User.objects.get(id=data_owner_id)
            target_user = User.objects.get(id=target_user_id)
            
            # --- ROLE KEZELÉSE ---
            target_role = None
            if target_role_id and target_role_id != '0':
                try:
                    target_role = UserRole.objects.get(id=target_role_id)
                except UserRole.DoesNotExist:
                    target_role = None

            # Engedély lekérése vagy létrehozása
            permission, created = DataSharingPermission.objects.get_or_create(
                athlete=data_owner,
                target_person=target_user,
                target_role=target_role, # Itt most már lehet None!
                app_name=app_name,
                table_name=table_name
            )

            # --- JOGOSULTSÁG ELLENŐRZÉSE ---
            is_owner = (request.user == data_owner)
            is_parent = UserRole.objects.filter(
                user=data_owner, 
                parent=request.user, 
                status='approved'
            ).exists()

            if is_owner:
                permission.athlete_consent = not permission.athlete_consent
            elif is_parent:
                permission.parent_consent = not permission.parent_consent
            else:
                return JsonResponse({'success': False, 'error': 'Nincs jogosultsága.'}, status=403)

            # Mentés (a modell is_permission_active logikája alapján frissül)
            permission.save() 
            
            # A biztonság kedvéért hívjuk meg az utils-t a válaszhoz
            from .utils import is_permission_active

            return JsonResponse({
                'success': True, 
                'enabled': is_permission_active(permission),
                'athlete_consent': permission.athlete_consent,
                'parent_consent': permission.parent_consent,
                'is_minor': not getattr(data_owner, 'is_adult', True),
            })

        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User nem található.'}, status=404)
        except Exception as e:
            print(f"SERVER ERROR: {str(e)}") # Ez segít neked a logban
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

@login_required
def data_sharing_center(request):
    user = request.user
    matrices_data = []

    # 1. Kik az adat tulajdonosok, akiket ez a felhasználó kezelhet?
    # Saját maga és a gyerekei
    managed_athletes = []
    
    # Saját maga (ha sportoló)
    my_athlete_roles = UserRole.objects.filter(user=user, role__name='Sportoló', status='approved')
    for r in my_athlete_roles:
        managed_athletes.append({'user': user, 'role': r, 'is_child': False})
        
    # Gyerekei
    children_roles = UserRole.objects.filter(parent=user, role__name='Sportoló', status='approved')
    for r in children_roles:
        managed_athletes.append({'user': r.user, 'role': r, 'is_child': True})

    # 2. Mátrix generálása minden sportolóhoz
    for item in managed_athletes:
        owner_user = item['user']
        owner_role = item['role'] # A sportoló aktuális tagsága (klub/sportág)
        
        # Keressük azokat az edzőket/vezetőket, akik "látják" ezt a sportolót
        # Azonos klub, azonos sportág (edzőknek) VAGY azonos klub (vezetőknek)
        potential_targets = UserRole.objects.filter(
            club=owner_role.club,
            status='approved'
        ).filter(
            Q(role__name='Egyesületi vezető') | 
            Q(role__name='Edző', sport=owner_role.sport)
        ).exclude(user=user).select_related('user__profile', 'role', 'club', 'sport')

        target_list = []

        # 2. Speciális célpont: A SZÜLŐ (ha kiskorúról van szó)
        # Ha a sportolónak van beállított szülője a UserRole-ban
        if owner_role.parent:
            parent_user = owner_role.parent
            # Megkeressük a szülő "Szülő" szerepkörét (ha van ilyen rögzítve)
            parent_role = UserRole.objects.filter(user=parent_user, role__name='Szülő').first()
            
            target_list.append({
                'user_id': parent_user.id,
                'role_id': parent_role.id if parent_role else 0, # Ha nincs külön sor, 0 vagy None
                'name': f"{parent_user.get_full_name()} (Szülő)",
                'role_name': 'Szülő',
                'club_name': owner_role.club.name,
                'sport_name': '-'
            })

        # 3. Többi célpont hozzáadása
        for t_role in potential_targets:
            target_list.append({
                'user_id': t_role.user.id,
                'role_id': t_role.id,
                'name': t_role.user.get_full_name() or t_role.user.username,
                'role_name': t_role.role.name,
                'club_name': t_role.club.name,
                'sport_name': t_role.sport.name if t_role.sport else "Minden sportág"
            })

        if target_list:
            # FIGYELEM: A build_sharing_matrix-nek át kell adni a target_list-et!
            matrix_rows = build_sharing_matrix(owner_user, target_list)
            
            matrices_data.append({
                'data_owner': owner_user,
                'owner_name': owner_user.get_full_name() or owner_user.username,
                'matrix_rows': matrix_rows,
                'is_parent_managing': item['is_child'],
                'is_minor': not owner_user.is_adult,
            })

    context = {
        'matrices_data': matrices_data,
        'page_title': 'Adatmegosztási Központ',
    }
    return render(request, 'data_sharing/sharing_center.html', context)

@login_required
def shared_data_view(request):
    """
    Nézet az edzőknek/vezetőknek: kik osztottak meg velük adatot.
    """
    user = request.user
    # FRISSÍTVE: target_person és athlete
    permissions = DataSharingPermission.objects.filter(
        target_person=user,
        athlete_consent=True # Csak ha van sportolói beleegyezés
    ).select_related('athlete').order_by('athlete__username', 'app_name', 'table_name')
    
    shared_data_by_user = {}
    for perm in permissions:
        username = perm.athlete.username
        if username not in shared_data_by_user:
            shared_data_by_user[username] = {
                'user': perm.athlete,
                'shared_tables': []
            }
        
        shared_data_by_user[username]['shared_tables'].append({
            'app_name': perm.app_name,
            'table_name': perm.table_name,
            'display_name': get_model_display_name(perm.app_name, perm.table_name)
        })
    
    context = {
        'shared_data_by_user': shared_data_by_user,
        'app_context': 'shared_data_view',
    }
    return render(request, 'data_sharing/shared_data_view.html', context)