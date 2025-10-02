# /app/users/utils.py

from django.contrib import messages
from django.shortcuts import redirect
from functools import wraps
from users.models import UserRole, Club, Sport

# 1. Az eredeti logikát átnevezzük belső segédfüggvénynek
def _check_user_role(user, role_name, club=None, sport=None):
    """Belső függvény a szerepkör állapotának ellenőrzésére."""
    
    # Ha a related_name "user_roles" (amit a forms.py-ban használtál):
    qs = user.user_roles.filter(role__name=role_name, status="approved")

    # Ha a related_name "userrole_children" (amit a hibaüzenet is említ)
    # qs = user.userrole_children.filter(
    #    role__name=role_name, 
    #    status="approved"
    # )
    
    if club:
        qs = qs.filter(club=club)
    if sport:
        qs = qs.filter(sport=sport)
        
    return qs.exists()

# 2. Új Dekorátor a @has_role('Edző') használathoz
def role_required(role_name, redirect_url='core:main_page'):
    """
    Paraméterezhető dekorátor, ami ellenőrzi a felhasználó szerepkörét.
    @role_required('Edző') formában használható.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login') 
            
            # Hívjuk a szerepkör ellenőrző belső függvényt
            if not _check_user_role(request.user, role_name):
                messages.error(request, f"Hozzáférés megtagadva. Csak '{role_name}' szerepkörrel rendelkező felhasználók számára elérhető.")
                return redirect(redirect_url) 
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def get_coach_clubs_and_sports(user):
    """
    Kiolvassa az adott felhasználóhoz (Edzőhöz) rendelt aktív klubokat és sportágakat.
    
    :param user: A bejelentkezett User objektum (Edző).
    :return: Egy (queryset_of_clubs, queryset_of_sports) tuple-t ad vissza.
    """
    if not user.is_authenticated:
        return Club.objects.none(), Sport.objects.none()

    active_coach_roles = UserRole.objects.filter(
        user=user,
        role__name='Edző',
        status='approved'
    ).select_related('club', 'sport')

    # Kinyerjük a Club és Sport objektumokat
    club_ids = active_coach_roles.values_list('club_id', flat=True).distinct()
    sport_ids = active_coach_roles.values_list('sport_id', flat=True).distinct()

    clubs = Club.objects.filter(id__in=club_ids)
    sports = Sport.objects.filter(id__in=sport_ids)
    
    return clubs, sports