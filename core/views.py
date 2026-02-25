# core/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from users.models import UserRole, Role, Club, Sport
import logging
from ml_engine.ai_coach_service import DittaCoachService
from billing.models import ServicePlan

ditta_service = DittaCoachService()

logger = logging.getLogger(__name__)

def hello_world(request):
    return render(request, 'core/index.html')

def contact_view(request):
    """
    Kapcsolat oldal megjelenítése (bejelentkezés nélkül), 
    ami a base_out.html-t terjeszti ki.
    """
    return render(request, 'core/contact.html')

def privacy_policy_view(request):
    """
    Adatvédelmi Tájékoztató oldal megjelenítése (base_out.html-t használja).
    """
    return render(request, 'core/privacy_policy.html')

def imprint_terms_view(request):
    """
    Impresszum és ÁSZF oldal megjelenítése (base_out.html-t használja).
    """
    return render(request, 'core/imprint_terms.html')

def features_view(request):
    """
    A funkciók és a rendszer működésének részletes bemutatása.
    """
    context = {
        'ad_free_plans': ServicePlan.objects.filter(plan_type='AD_FREE', is_active=True).order_by('price_ft'),
        'ml_plans': ServicePlan.objects.filter(plan_type='ML_ACCESS', is_active=True).order_by('price_ft'),
        'analysis_plans': ServicePlan.objects.filter(plan_type='ANALYSIS', is_active=True).order_by('price_ft'),
    }
    return render(request, 'core/features.html', context)

def knowledge_base_view(request):
    """
    A rendszer tudományos hátterének és algoritmusainak részletes bemutatása.
    """
    context = {
        'section': 'science',
        'app_context': 'knowledge_base',
    }
    return render(request, 'core/knowledge_base.html', context)

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

    app_context = 'core'
    if pending_roles_count > 0 or pending_child_approvals_count > 0:
        app_context = 'main_page_has_pending_tasks'

    # A SZERVIZ meghívása (ez dönti el, hogy Navigator vagy Analyst kell-e)
    welcome_message = ditta_service.get_ditta_response(
        user=request.user, 
        context_app=app_context
    )

    context = {
        'user': user,
        'user_roles': user_roles,
        'pending_roles_count': pending_roles_count,
        'pending_child_approvals_count': pending_child_approvals_count, # Új változó hozzáadása
        'app_context': app_context,
        'welcome_message': welcome_message,
    }
    
    logger.info(f"Főoldalra érkezett felhasználó: {user.username}, szerepkörök száma: {len(user_roles)}, függőben lévő kérések száma: {pending_roles_count}, függőben lévő szülői jóváhagyások száma: {pending_child_approvals_count}")
    return render(request, 'core/main_page.html', context)