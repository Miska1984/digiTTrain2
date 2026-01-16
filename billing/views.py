from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.utils import timezone  # Django specifikus timezone!
from .models import ServicePlan, TopUpInvoice, UserCreditBalance, UserAnalysisBalance, UserSubscription, FinancialTransaction
from .forms import CombinedPurchaseForm
from .utils import activate_service, redeem_with_credits

@login_required
def billing_dashboard_view(request):
    analysis_balance, _ = UserAnalysisBalance.objects.get_or_create(user=request.user)
    credit_balance, _ = UserCreditBalance.objects.get_or_create(user=request.user)
    
    # Összes aktív előfizetés lekérése (lehet több is!)
    active_subscriptions = UserSubscription.objects.filter(
        user=request.user, 
        expiry_date__gt=timezone.now()
    )
    
    # Függőben lévő számlák (PENDING és INVOICED)
    pending_invoices = TopUpInvoice.objects.filter(
        user=request.user,
        status__in=['PENDING', 'INVOICED']
    ).order_by('-created_at')

    # Ellenőrizzük a mai hirdetést
    ad_today = FinancialTransaction.objects.filter(
        user=request.user,
        transaction_type='EARN',
        description__icontains="Napi hirdetés bónusz",
        timestamp__date=timezone.now().date()
    ).exists()

    context = {
        'analysis_balance': analysis_balance.count,
        'credit_balance': credit_balance.credits,
        'active_subscriptions': active_subscriptions, # HTML-hez igazítva
        'pending_invoices': pending_invoices,         # HTML-hez igazítva
        'ad_earned_today': ad_today,
        'transactions': FinancialTransaction.objects.filter(user=request.user).order_by('-timestamp')[:10],
        'app_context': 'billing_dashboard',
    }
    return render(request, 'billing/dashboard.html', context)

@login_required
def purchase_view(request):
    wallet, created = UserCreditBalance.objects.get_or_create(user=request.user)
    
    initial_data = {'billing_email': request.user.email}
    if hasattr(request.user, 'profile'):
        full_name = f"{request.user.profile.first_name} {request.user.profile.last_name}".strip()
        if full_name: initial_data['billing_name'] = full_name

    if request.method == 'POST':
        # Átadjuk a request.user-t a formnak!
        form = CombinedPurchaseForm(request.POST, user=request.user)
        if form.is_valid():
            plan_id = request.POST.get('selected_plan_id')
            plan = get_object_or_404(ServicePlan, id=plan_id)
            
            # MEGHATÁROZZUK A KEDVEZMÉNYEZETTET:
            # Ha a szülő választott gyereket, ő lesz az, különben marad a bejelentkezett user
            target_user = form.cleaned_data.get('target_user') or request.user
            payment_method = form.cleaned_data['payment_method']

            if payment_method == 'CASH':
                TopUpInvoice.objects.create(
                    user=request.user,        # A fizető mindig a szülő
                    target_user=target_user,  # ⚠️ EHHEZ KELL EGY ÚJ MEZŐ A MODELLBEN (lásd lentebb)
                    plan=plan,
                    amount_ft=plan.price_ft,
                    billing_name=form.cleaned_data['billing_name'],
                    billing_address=form.cleaned_data['billing_address'],
                    billing_email=form.cleaned_data['billing_email'],
                    status='PENDING'
                )
                messages.success(request, f"Díjbekérő generálva {target_user.get_full_name()} részére.")
                return redirect('billing:billing_dashboard')

            elif payment_method == 'CREDIT':
                if wallet.credits >= plan.price_in_credits:
                    from .utils import activate_service
                    # Fontos: a levonás a szülőtől megy, de az aktiválás a target_user-nek!
                    if activate_service(target_user, plan, payer=request.user):
                        messages.success(request, f"Sikeresen aktiválva {target_user.get_full_name()} számára!")
                        return redirect('billing:billing_dashboard')
                else:
                    messages.error(request, "Nincs elég kredited!")
        else:
            # Ha a form nem valid (pl. hiányzik a cím)
            messages.error(request, "Kérjük, ellenőrizze a megadott adatokat! Banki utaláshoz kötelező a számlázási cím.")
    else:
        form = CombinedPurchaseForm(initial=initial_data, user=request.user)

    return render(request, 'billing/purchase.html', {
        'form': form,
        'user_credits': wallet.credits,
        'app_context': 'purchase_view',
    })

# ============================================================
# 🆕 HIRDETÉSNÉZÉS ÉS KREDIT JÓVÁÍRÁS
# ============================================================

@login_required
def ad_for_credit_view(request):
    user = request.user
    today = timezone.now().date()
    
    # Ellenőrizzük, kapott-e már ma kreditet hirdetésért
    already_earned = FinancialTransaction.objects.filter(
        user=user,
        transaction_type='EARN',
        description__icontains="Napi hirdetés bónusz",
        timestamp__date=today
    ).exists()

    if request.method == 'POST':
        if already_earned:
            messages.warning(request, "Ma már gyűjtöttél kreditet, gyere vissza holnap!")
            return redirect('billing:billing_dashboard')
        
        # Kredit jóváírása (pl. 1 kredit)
        amount = 1
        with transaction.atomic():
            wallet, _ = UserCreditBalance.objects.get_or_create(user=user)
            wallet.credits += amount
            wallet.save()
            
            FinancialTransaction.objects.create(
                user=user,
                transaction_type='EARN',
                amount=amount,
                description=f"Napi hirdetés bónusz ({user.email})"
            )
        
        messages.success(request, f"Gratulálunk! {amount} kreditet kaptál.")
        return redirect('billing:billing_dashboard')

    # GET kérés esetén megjelenítjük a hirdetés oldalt
    context = {
        'already_earned': already_earned,
        'app_context': 'ad_view',
    }
    return render(request, 'billing/ad_view.html', context)

@login_required
def toggle_ad_free_view(request): return redirect('billing:billing_dashboard')

# ============================================================
# AJAX VÉGPONT A CSOMAGOKHOZ
# ============================================================

def get_plans_ajax(request):
    p_type = request.GET.get('type') # Ezt küldi a JS: ANALYSIS, AD_FREE, vagy ML_ACCESS
    plans = ServicePlan.objects.filter(plan_type=p_type, is_active=True).values(
        'id', 'name', 'description', 'price_ft', 'price_in_credits'
    )
    return JsonResponse(list(plans), safe=False)