# users/role_views/base.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q 
from users.models import UserRole
from users.forms import CoachRoleForm


@login_required
def pending_roles(request):
    """Jóváhagyásra váró szerepkörök listája (feletteseknek) és a felhasználó saját, függőben lévő kérései."""

    my_pending_roles = UserRole.objects.filter(
        user=request.user,
        status="pending"
    ).select_related('club', 'sport')

    pending_roles_for_approval = UserRole.objects.none()

    user_approved_roles = UserRole.objects.filter(
        user=request.user,
        status="approved"
    ).select_related('club', 'sport')

    # 1. Klubvezetőként: jóváhagyásra váró Edző, Szülő és Sportoló szerepkörök a klubjaiban
    club_leader_roles = user_approved_roles.filter(role__name="Egyesületi vezető")
    club_ids = [role.club.id for role in club_leader_roles]
    if club_ids:
        pending_roles_for_approval |= UserRole.objects.filter(
            Q(role__name='Edző') | Q(role__name='Szülő') | Q(role__name='Sportoló'),
            status="pending",
            club__id__in=club_ids,
            coach__isnull=True # Ha van edző, az edző hagyja jóvá
        ).exclude(user=request.user)

    # 2. Edzőként: jóváhagyásra váró Sportoló és Szülő szerepkörök, ahol az edző a felelős.
    coach_roles = user_approved_roles.filter(role__name="Edző")
    if coach_roles:
        pending_roles_for_approval |= UserRole.objects.filter(
            Q(role__name='Sportoló') | Q(role__name='Szülő'),
            status='pending',
            coach=request.user,
        ).exclude(user=request.user)
    
    # 3. Szülőként: jóváhagyásra váró Sportoló szerepkörök
    parent_roles = user_approved_roles.filter(role__name="Szülő")
    if parent_roles:
        pending_roles_for_approval |= UserRole.objects.filter(
            role__name='Sportoló',
            status='pending',
            parent=request.user,
            approved_by_parent=False
        ).exclude(user=request.user)
    
    pending_roles_for_approval = pending_roles_for_approval.distinct().select_related('user__profile', 'club', 'sport', 'coach__profile')

    return render(request, "users/roles/pending_roles.html", {
        "pending_roles_for_approval": pending_roles_for_approval,
        "my_pending_roles": my_pending_roles,
    })


@login_required
def approve_role(request, role_id):
    """Szerepkör jóváhagyása"""
    role_to_approve = get_object_or_404(UserRole, id=role_id, status="pending")
    
    # A models.py-ban definiált logika alapján megkeressük, kinek kell jóváhagynia
    approver = role_to_approve.needs_approval_from

    if not approver or approver != request.user:
        messages.error(request, "Nincs jogosultsága ehhez a művelethez.")
        return redirect("users:pending_roles")

    if request.method == "POST":
        # A szülői jóváhagyás
        if role_to_approve.role.name == 'Sportoló' and role_to_approve.parent == request.user:
            role_to_approve.approved_by_parent = True
            role_to_approve.save(update_fields=['approved_by_parent'])
            messages.success(request, f"A(z) {role_to_approve.user.username} Sportoló szerepkör szülői jóváhagyása sikeresen megtörtént.")
        # Edzői vagy klubvezetői jóváhagyás
        else:
            role_to_approve.status = "approved"
            role_to_approve.approved_by = request.user
            role_to_approve.approved_at = timezone.now()
            role_to_approve.save(update_fields=['status', 'approved_by', 'approved_at'])
            messages.success(request, f"A(z) {role_to_approve.user.username} {role_to_approve.role.name} szerepköre sikeresen jóváhagyva lett.")

    return redirect("users:pending_roles")


@login_required
def reject_role(request, role_id):
    """Szerepkör elutasítása"""
    role = get_object_or_404(UserRole, id=role_id, status="pending")
    
    # A models.py-ban definiált logika alapján ellenőrizzük a jogosultságot
    approver = role.needs_approval_from

    if not approver or approver != request.user:
        messages.error(request, "Nincs jogosultsága ehhez a művelethez.")
        return redirect("users:pending_roles")

    if request.method == "POST":
        role.status = "rejected"
        role.approved_by = request.user
        role.approved_at = timezone.now()
        role.save(update_fields=['status', 'approved_by', 'approved_at'])

        messages.warning(request, f"A(z) {role.user.username} {role.role.name} szerepköre elutasítva lett.")
        return redirect("users:pending_roles")

    return redirect("users:pending_roles")

login_required
def cancel_role(request, role_id):
    """
    Függőben lévő szerepkör visszavonása a felhasználó által.
    """
    # A get_object_or_404 garantálja, hogy a szerepkör létezik, a felhasználóhoz tartozik, és függőben van
    role = get_object_or_404(
        UserRole,
        id=role_id,
        user=request.user,
        status="pending"
    )

    if request.method == "POST":
        role.delete()
        messages.success(request, f"A(z) {role.role.name} szerepkör igénylés sikeresen visszavonva.")
        return redirect("core:main_page")

    # Alapértelmezett visszatérés, ha nem POST kérés
    return redirect("core:main_page")
