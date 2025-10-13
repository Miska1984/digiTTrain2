from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from users.models import User

from .models import (
    UserCreditBalance,
    InvoiceRequest,
    SubscriptionPlan,
    UserSubscription,
    AlgorithmPricing,
    TransactionHistory
)
from .forms import TopUpForm, AdFreeToggleForm  # Ezeket a formokat később megírjuk!


# ----------------------------------------------------------------------
# SEGÉDFÜGGVÉNYEK
# ----------------------------------------------------------------------

def get_credit_balance(user):
    """Lekéri vagy létrehozza a felhasználó Credit egyenlegét."""
    balance, created = UserCreditBalance.objects.get_or_create(user=user)
    return balance

# ----------------------------------------------------------------------
# 1. VEZÉRLŐPULT (DASHBOARD)
# ----------------------------------------------------------------------

@login_required
def billing_dashboard(request):
    """Megjeleníti a felhasználó Credit egyenlegét és az előfizetés státuszát."""
    balance = get_credit_balance(request.user)
    
    # A Hirdetésmentes státusz már globálisan elérhető a context_processors.py által
    
    context = {
        'credit_balance': balance.balance_amount,
        'transactions': TransactionHistory.objects.filter(user=request.user).order_by('-timestamp')[:10],
        'ad_free_status': request.user.subscription.is_active if hasattr(request.user, 'subscription') else False,
    }
    return render(request, 'billing/dashboard.html', context)


# ----------------------------------------------------------------------
# 2. CREDIT FELTÖLTÉS ÉS SZÁMLA IGÉNYLÉS (TOP-UP)
# ----------------------------------------------------------------------

@login_required
def top_up_view(request):
    """
    Kezeli a pénzügyi feltöltést, a számla igénylést és a célfelhasználó kijelölését.
    """

    # Lekérjük az összes felhasználót, akinek fel lehet tölteni (pl. sportolók, vagy saját maga)
    # Most minden felhasználót megengedi:
    target_users = User.objects.all()

    if request.method == 'POST':
        # Feltételezzük, hogy a TopUpForm tartalmazza az összeget, számlázási adatokat és a target_user-t
        form = TopUpForm(request.POST, user=request.user, target_user_queryset=target_users) 
        if form.is_valid():
            
            amount_ft = form.cleaned_data['amount_ft']
            target_user = form.cleaned_data['target_user']
            
            # --- Ideiglenes Tranzakció/Számlázási Rögzítés ---
            
            # Létrehozzuk a számlaigénylést, ami fizetési bizonylatként/kérésként is szolgál
            invoice_request = InvoiceRequest.objects.create(
                user=request.user,
                amount_ft=amount_ft,
                target_user=target_user,
                billing_name=form.cleaned_data['billing_name'],
                billing_address=form.cleaned_data['billing_address'],
                tax_number=form.cleaned_data.get('tax_number'),
                status='PENDING'
            )

            # Megjegyzés: Itt *nem* történik meg azonnal a Credit jóváírása. 
            # Ez egy kézi/banki átutalásos folyamatot feltételez, ahol az admin utólag könyveli le a fizetést,
            # majd jóváírja a Creditet (valószínűleg egy Admin Action segítségével).
            
            messages.success(request, f'A {amount_ft} Ft értékű Credit feltöltési kérés rögzítve lett ({target_user.username} számára). A számlát hamarosan elkészítjük.')
            return redirect('billing_dashboard')
    else:
        form = TopUpForm(user=request.user, target_user_queryset=target_users)
        
    context = {
        'form': form,
        'pending_invoices': InvoiceRequest.objects.filter(user=request.user, status='PENDING')
    }
    return render(request, 'billing/top_up.html', context)


# ----------------------------------------------------------------------
# 3. HIRDETÉSNÉZÉSÉRT JÁRÓ CREDIT (AD-FOR-CREDIT)
# ----------------------------------------------------------------------

@login_required
@require_POST
@transaction.atomic
def ad_credit_earn_view(request):
    """
    A hirdetés megnézése utáni Credit jóváírása.
    Feltételezi, hogy egy hirdetés nézés 50 Creditet ér.
    """
    CREDIT_PER_AD = settings.CREDIT_PER_AD if hasattr(settings, 'CREDIT_PER_AD') else 50.00
    
    user = request.user
    balance = get_credit_balance(user)
    
    # 1. Credit jóváírása
    balance.balance_amount += CREDIT_PER_AD
    balance.save()
    
    # 2. Tranzakció rögzítése
    TransactionHistory.objects.create(
        user=user,
        transaction_type='AD_EARN',
        amount=CREDIT_PER_AD,
        description=f'Hirdetés nézésért szerzett Credit ({CREDIT_PER_AD} Credit)',
    )
    
    messages.success(request, f'Sikeresen jóváírtuk az 50 Creditet! Jelenlegi egyenleg: {balance.balance_amount} Credit.')
    
    # Valószínűleg egy AJAX hívásnak kell válaszolnia, de most egyszerű átirányítással dolgozunk
    return redirect('billing_dashboard')


# ----------------------------------------------------------------------
# 4. HIRDETÉSMENTES ELŐFIZETÉS AKTIVÁLÁSA/MEGÚJÍTÁSA
# ----------------------------------------------------------------------

@login_required
@require_POST
@transaction.atomic
def toggle_ad_free(request):
    """
    A hirdetésmentes előfizetés megvásárlása Credit vagy közvetlen fizetés felhasználásával.
    """
    # 1. Megkeressük a hirdetésmentes csomagot
    AD_FREE_PLAN_NAME = settings.AD_FREE_PLAN_NAME if hasattr(settings, 'AD_FREE_PLAN_NAME') else 'Ad-Free'
    
    try:
        ad_free_plan = SubscriptionPlan.objects.get(name=AD_FREE_PLAN_NAME)
    except SubscriptionPlan.DoesNotExist:
        messages.error(request, 'A hirdetésmentes előfizetés csomag nem található. Kérem, lépjen kapcsolatba az adminisztrátorral.')
        return redirect('billing_dashboard')
        
    user = request.user
    
    # Itt most feltételezzük a közvetlen, havi 1500 Ft-os fizetést (a felvetés szerint)
    # A bonyolultabb Credit-ből történő fizetést később implementálhatjuk.
    
    # Jelenleg csak a funkció elindítását rögzítjük
    
    # Valódi Fizetésfeldolgozás (pl. Stripe/SimplePay) hiányában ezt a lépést imitáljuk.
    # Ez a kód feltételezi, hogy a felhasználó már "megvásárolta" a csomagot.
    
    # 2. Lejárat dátumának kiszámítása
    try:
        # Ha már van aktív előfizetése, a lejárat a jelenlegi lejárati dátumhoz adódik hozzá
        user_sub = UserSubscription.objects.get(user=user)
        # Ha az előfizetés lejárt, vagy lejárat előtt van, a dátumot a jelenlegi lejárati dátumhoz igazítjuk
        new_start_date = user_sub.end_date if user_sub.end_date > timezone.now() else timezone.now()
        
    except UserSubscription.DoesNotExist:
        # Ha nincs még előfizetése, a kezdés a mostani időpont
        new_start_date = timezone.now()
        
        # Létrehozzuk az új UserSubscription objektumot
        user_sub = UserSubscription(user=user, plan=ad_free_plan)
    
    # 3. Dátumok frissítése
    user_sub.plan = ad_free_plan
    user_sub.start_date = new_start_date
    user_sub.end_date = new_start_date + timezone.timedelta(days=ad_free_plan.duration_days)
    user_sub.is_active = True
    user_sub.save()
    
    # 4. Tranzakció rögzítése (ez most csak a rendszer számára rögzít)
    TransactionHistory.objects.create(
        user=user,
        transaction_type='SUB_PAY',
        amount=ad_free_plan.price_ft, # Itt Ft-ot tárolunk az egyszerűség kedvéért
        description=f'Előfizetés fizetés: {ad_free_plan.name}',
    )
    
    messages.success(request, f'Sikeresen aktiváltuk a hirdetésmentes csomagot! Lejár: {user_sub.end_date.strftime("%Y.%m.%d")}')
    return redirect('billing_dashboard')


# ----------------------------------------------------------------------
# 5. ALGORITMUS FUTTATÁS (API VÉGPONT)
# ----------------------------------------------------------------------

@login_required
@require_POST
@transaction.atomic
def run_algorithm(request, algorithm_name):
    """
    Ez egy API végpont, amely elvonja a Creditet, és jelzi, hogy az algoritmus futtatható.
    """
    user = request.user
    
    # 1. Algoritmus árának lekérése
    try:
        pricing = AlgorithmPricing.objects.get(algorithm_name=algorithm_name)
    except AlgorithmPricing.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Hiba: Az algoritmus nem található vagy nincs árazva.'}, status=404)
        
    cost = pricing.cost_per_run
    balance = get_credit_balance(user)
    
    # 2. Credit ellenőrzése
    if balance.balance_amount < cost:
        return JsonResponse({'success': False, 'message': f'Nincs elegendő Credit az algoritmus futtatásához. Szükséges: {cost} Credit. Jelenlegi: {balance.balance_amount} Credit.'}, status=403)

    # 3. Credit elvonása
    balance.balance_amount -= cost
    balance.save()

    # 4. Tranzakció rögzítése
    TransactionHistory.objects.create(
        user=user,
        transaction_type='ALGO_RUN',
        amount=-cost, # Negatív összeg a levonás jelzésére
        description=f'Algoritmus futtatása: {algorithm_name}',
    )
    
    # 5. Sikeres válasz (ez után indul el a háttérben az igazi algoritmus)
    # JsonResponse-t feltételez, importáljuk a szükséges csomagot:
    from django.http import JsonResponse
    
    return JsonResponse({'success': True, 'message': 'Credit sikeresen elvonva, az elemzés elindult.'}, status=200)