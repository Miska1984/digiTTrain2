# billing/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from decimal import Decimal

from .forms import CombinedPurchaseForm
from .models import (
    UserSubscription, 
    UserAnalysisBalance,
    AnalysisTransaction,
    AdViewStreak,
    SubscriptionPlan,
    JobPrice,
    TopUpInvoice  # ⬅️ fontos!
)
from .utils import get_analysis_balance, check_ad_streak, reward_ad_view

import logging
logger = logging.getLogger(__name__)


# ==============================================================================
# 1. PÉNZÜGYI VEZÉRLŐPULT (Dashboard)
# ==============================================================================

@login_required
def billing_dashboard_view(request):
    """Megjeleníti a felhasználó egyenlegét, előfizetését és tranzakcióit"""
    
    # 1. Elemzési egyenleg lekérése
    analysis_balance = get_analysis_balance(request.user)
    
    # 2. Aktív előfizetés lekérése
    current_subscription = UserSubscription.objects.filter(
        user=request.user,
        end_date__gt=timezone.now()
    ).select_related('plan').first()
    
    # 3. Hirdetésnézési sorozat
    current_streak, can_view_today = check_ad_streak(request.user)
    try:
        streak_obj = AdViewStreak.objects.get(user=request.user)
        total_rewards = streak_obj.total_rewards_earned
    except AdViewStreak.DoesNotExist:
        total_rewards = 0
    
    # 4. Tranzakciók (utolsó 10)
    transactions = AnalysisTransaction.objects.filter(
        user=request.user
    ).order_by('-timestamp')[:10]
    

    
    context = {
        'analysis_balance': analysis_balance,
        'current_subscription': current_subscription,
        'current_streak': current_streak,
        'can_view_ad_today': can_view_today,
        'total_ad_rewards': total_rewards,
        'transactions': transactions,
    }
    
    return render(request, 'billing/dashboard.html', context)


# ==============================================================================
# 2. VÁSÁRLÁS (Előfizetés / Elemzési csomag)
# ==============================================================================

@login_required
@transaction.atomic
def purchase_view(request):
    """
    Kombinált nézet elemzési csomagok (Credit) és hirdetésmentes előfizetés vásárlására.
    Létrehozza a TopUpInvoice-t, amit az admin később jóváhagy.
    """
    analysis_packages = JobPrice.objects.all().order_by('price_ft')
    ad_free_plans = SubscriptionPlan.objects.filter(is_ad_free=True).order_by('duration_days')

    # 🔥 ÚJ: Függőben lévő számlák lekérése
    pending_invoices = TopUpInvoice.objects.filter(
        user=request.user,
        status='PENDING'
    ).select_related('subscription_plan', 'related_analysis_package').order_by('-request_date')

    if not analysis_packages.exists() and not ad_free_plans.exists():
        messages.error(request, "Nincsenek elérhető csomagok vásárlásra.")
        return redirect('billing:billing_dashboard')

    if request.method == 'POST':
        form = CombinedPurchaseForm(
            request.POST, 
            user=request.user,
            analysis_packages=analysis_packages,
            ad_free_plans=ad_free_plans
        )
        
        if form.is_valid():
            data = form.cleaned_data
            purchase_type = data['purchase_type']
            amount_ft = Decimal(0)
            invoice_type = ''
            related_package = None
            related_plan = None

            if purchase_type == 'AD_FREE':
                related_plan = data['subscription_plan']
                amount_ft = related_plan.price_ft
                invoice_type = 'AD_FREE_SUBSCRIPTION'  # ✅ JAVÍTVA
                description = f"Hirdetésmentes előfizetés: {related_plan.name}"

            elif purchase_type == 'ANALYSIS_PACKAGE':
                related_package = data['analysis_package']
                amount_ft = related_package.price_ft
                invoice_type = 'ANALYSIS_PACKAGE'  # ✅ JAVÍTVA
                description = f"Elemzési csomag: {related_package.name} ({related_package.analysis_count} db)"

            # =============== Számlázási igény rögzítése ===============
            invoice = TopUpInvoice.objects.create(
                user=request.user,
                target_user=request.user,
                amount_ft=amount_ft,
                invoice_type=invoice_type,
                status='PENDING',
                request_date=timezone.now(),
                related_analysis_package=related_package,
                subscription_plan=related_plan,
                billing_name=data['billing_name'],
                billing_address=data['billing_address'],
                tax_number=data.get('tax_number', ''),
                billing_email=data['billing_email'],
            )
            # =============================================================

            logger.info(f"💰 Számlázási igény létrehozva: {invoice} (összeg: {amount_ft} Ft)")
            messages.success(
                request,
                f"✅ Számlaigénylés rögzítve! Hamarosan visszajelzést kapsz e-mailben: {data['billing_email']}."
            )
            return redirect('billing:billing_dashboard')

    else:
        form = CombinedPurchaseForm(
            user=request.user,
            analysis_packages=analysis_packages,
            ad_free_plans=ad_free_plans
        )

    context = {
        'form': form,
        'analysis_packages': analysis_packages,
        'ad_free_plans': ad_free_plans,
        'pending_invoices': pending_invoices,  # ✅ ÚJ
    }
    return render(request, 'billing/purchase.html', context) 


# ==============================================================================
# 3. HIRDETÉS MEGTEKINTÉSE (Ingyenes elemzésért)
# ==============================================================================

@login_required
def ad_for_credit_view(request):
    """
    Hirdetés megtekintése 5 egymást követő napon keresztül.
    Jutalom: +1 ingyenes elemzés
    """
    
    # Sorozat állapotának lekérése
    current_streak, can_view_today = check_ad_streak(request.user)
    
    if request.method == 'POST':
        # Felhasználó megnézte a hirdetést és megnyomta a gombot
        if not can_view_today:
            messages.warning(request, "⚠️ Ma már megnézted a hirdetést. Gyere vissza holnap!")
            return redirect('billing_dashboard')
        
        # Hirdetés megtekintésének rögzítése
        success, new_streak, rewarded = reward_ad_view(request.user)
        
        if rewarded:
            messages.success(
                request,
                f"🎉 Gratulálunk! 5 egymást követő nap teljesítve! "
                f"+1 ingyenes elemzést kaptál ajándékba!"
            )
        elif success:
            remaining = 5 - new_streak
            messages.info(
                request,
                f"✅ Hirdetés rögzítve! Jelenlegi sorozat: {new_streak}/5 nap. "
                f"Még {remaining} nap és kapsz +1 ingyenes elemzést!"
            )
        
        return redirect('billing_dashboard')
    
    # GET kérés: Hirdetési oldal megjelenítése
    context = {
        'current_streak': current_streak,
        'can_view_today': can_view_today,
        'remaining_days': max(0, 5 - current_streak) if can_view_today else 0,
    }
    
    return render(request, 'billing/ad_for_credit.html', context)


# ==============================================================================
# 4. HIRDETÉSMENTESSÉG AKTIVÁLÁS/KIKAPCSOLÁS
# ==============================================================================

@login_required
def toggle_ad_free_view(request):
    """
    Hirdetésmentes előfizetés gyors aktiválása.
    Ez az oldal átirányít a purchase_view-ra.
    """
    
    # Aktuális előfizetés lekérése
    current_subscription = UserSubscription.objects.filter(
        user=request.user,
        end_date__gt=timezone.now(),
        plan__is_ad_free=True
    ).select_related('plan').first()
    
    if request.method == 'POST':
        # Ha van aktív előfizetés, akkor kikapcsolás (törlés)
        if current_subscription:
            # Kikapcsolás: end_date-et most-ra állítjuk
            current_subscription.end_date = timezone.now()
            current_subscription.save(update_fields=['end_date'])
            
            messages.info(request, "ℹ️ Hirdetésmentesség kikapcsolva.")
            return redirect('billing_dashboard')
        else:
            # Ha nincs előfizetés, átirányítás vásárlásra
            messages.info(request, "ℹ️ Válasszon hirdetésmentes csomagot a vásárláshoz.")
            return redirect('billing_purchase')
    
    # GET kérés: Megerősítő oldal
    context = {
        'current_subscription': current_subscription,
    }
    
    return render(request, 'billing/toggle_ad_free.html', context)


