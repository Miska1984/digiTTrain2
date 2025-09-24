# core/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from users.models import UserRole, Role, Club, Sport
import logging

logger = logging.getLogger(__name__)

def hello_world(request):
    return render(request, 'core/index.html')

@login_required
def main_page(request):
    """
    A főoldal view, ahol megjelenítjük a felhasználó szerepköreit,
    és ellenőrizzük a függőben lévő jóváhagyási feladatokat.
    """
    user = request.user
    
    # Lekérdezzük a felhasználóhoz tartozó összes szerepkört
    # Nem használunk prefetch_related-et, mivel az hibát okoz a UserRole-on.
    user_roles = UserRole.objects.filter(user=user).select_related('role', 'club', 'sport', 'coach', 'parent')

    # Lekérdezzük a bejelentkezett szülőhöz tartozó gyerekek szerepköreit
    # Külön lekérdezés a parent mező alapján, ami a User objektumhoz kapcsolódik
    child_roles = UserRole.objects.filter(parent=user).select_related('user__profile', 'role')

    # Hozzáadjuk a gyermekek listáját a szülő UserRole objektumhoz
    for role in user_roles:
        if role.role.name == "Szülő":
            role.children = child_roles
            break
            
    # A jóváhagyásra váró szerepkörök számának meghatározása
    pending_roles_count = 0
    
    # Hozd létre a lekérdezést a bejelentkezett felhasználó jóváhagyási jogosultságai alapján
    pending_query = UserRole.objects.none() # Üres QuerySet

    # Jogosultság ellenőrzése klubvezetőként
    club_leader_roles = UserRole.objects.filter(
        user=user,
        role__name="Egyesületi vezető",
        status="approved"
    )
    if club_leader_roles.exists():
        club_ids = [role.club.id for role in club_leader_roles]
        # A klubvezető az edzői, sportolói és szülői szerepköröket hagyhatja jóvá
        pending_query |= UserRole.objects.filter(
            Q(status="pending") | Q(status="pending", approved_by_parent=True),
            club__id__in=club_ids,
        )

    # Jogosultság ellenőrzése edzőként
    coach_roles = UserRole.objects.filter(
        user=user,
        role__name="Edző",
        status="approved"
    )
    if coach_roles.exists():
        # Az edző a hozzárendelt Sportoló és Szülő szerepköröket hagyhatja jóvá
        pending_query |= UserRole.objects.filter(
            status="pending",
            coach=user,
        )

    # A teljes függőben lévő lista lekérdezése és a felhasználó saját kéréseinek kizárása
    pending_roles_count = pending_query.distinct().exclude(user=user).count()

    # Új logikai rész: a szülői jóváhagyásra váró gyermekek lekérdezése
    pending_child_approvals_count = UserRole.objects.filter(
        role__name="Sportoló",
        status="pending",
        parent=user
    ).count()

    context = {
        'user': user,
        'user_roles': user_roles,
        'pending_roles_count': pending_roles_count,
        'pending_child_approvals_count': pending_child_approvals_count, # Új változó hozzáadása
    }
    
    logger.info(f"Főoldalra érkezett felhasználó: {user.username}, szerepkörök száma: {len(user_roles)}, függőben lévő kérések száma: {pending_roles_count}, függőben lévő szülői jóváhagyások száma: {pending_child_approvals_count}")
    return render(request, 'core/main_page.html', context)