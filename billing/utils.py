# billing/utils.py
import logging
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from .models import FinancialTransaction, UserAnalysisBalance, UserSubscription, UserCreditBalance

logger = logging.getLogger(__name__)

def get_user_display_info(user):
    """Segédfüggvény a név és szerepkör formázásához."""
    try:
        prof = user.profile
        return f"{prof.last_name} {prof.first_name} ({prof.get_role_display()})"
    except:
        return user.email

def activate_service(target_user, plan, payer=None):
    # 1. KREDIT LEVONÁSA (ha van payer)
    if payer and plan.price_in_credits:
        wallet, _ = UserCreditBalance.objects.get_or_create(user=payer)
        if wallet.credits < plan.price_in_credits:
            return False
        
        wallet.credits -= plan.price_in_credits
        wallet.save()
        
        payer_info = get_user_display_info(payer)
        target_info = get_user_display_info(target_user)
        
        # Levonás naplózása a fizetőnél
        FinancialTransaction.objects.create(
            user=payer,
            transaction_type='SPEND',
            amount=-plan.price_in_credits,
            description=f"Beváltás: {plan.name} -> {target_info}"
        )

    # 2. SZOLGÁLTATÁS AKTIVÁLÁSA (Összeadódó logika)
    if plan.plan_type in ['AD_FREE', 'ML_ACCESS']:
        existing_sub = UserSubscription.objects.filter(
            user=target_user,
            sub_type=plan.plan_type,
            expiry_date__gt=timezone.now()
        ).order_by('-expiry_date').first()

        if existing_sub:
            new_expiry = existing_sub.expiry_date + timedelta(days=plan.duration_days)
            existing_sub.expiry_date = new_expiry
            existing_sub.save()
        else:
            new_expiry = timezone.now() + timedelta(days=plan.duration_days)
            UserSubscription.objects.create(
                user=target_user,
                sub_type=plan.plan_type,
                expiry_date=new_expiry
            )
            
        # Naplózás a KEDVEZMÉNYEZETTNÉL (ha más vette neki kredittel)
        if payer and payer != target_user:
            payer_info = get_user_display_info(payer)
            FinancialTransaction.objects.create(
                user=target_user,
                transaction_type='EARN',
                amount=0,
                description=f"Csomag érkezett: {plan.name} (Küldte: {payer_info})"
            )

    elif plan.plan_type == 'ANALYSIS':
        balance, _ = UserAnalysisBalance.objects.get_or_create(user=target_user)
        balance.count += plan.analysis_count
        balance.save()
        
        if payer and payer != target_user:
            payer_info = get_user_display_info(payer)
            FinancialTransaction.objects.create(
                user=target_user,
                transaction_type='EARN',
                amount=0,
                description=f"+{plan.analysis_count} elemzés érkezett (Küldte: {payer_info})"
            )

    return True

# A többi függvény (redeem_with_credits, get_analysis_balance, stb.) változatlan marad...
def redeem_with_credits(user, plan):
    balance, _ = UserCreditBalance.objects.get_or_create(user=user)
    if balance.credits >= plan.price_in_credits:
        with transaction.atomic():
            # FONTOS: Itt a payer=user biztosítja, hogy a leírásba a NÉV kerüljön!
            if activate_service(user, plan, payer=user):
                return True, "Sikeres beváltás!"
    return False, "Nincs elég kredited!"

def get_analysis_balance(user):
    balance, _ = UserAnalysisBalance.objects.get_or_create(user=user)
    return balance.count

def dedicate_analysis(user, job=None):
    """Elemzési egység levonása és naplózása."""
    with transaction.atomic():
        balance, _ = UserAnalysisBalance.objects.get_or_create(user=user)
        if balance.count > 0:
            balance.count -= 1
            balance.save()
            
            # Naplózzuk a levonást (0 összeggel, mert ez nem kredit, hanem egység)
            FinancialTransaction.objects.create(
                user=user,
                transaction_type='SPEND',
                amount=0,
                description=f"Elemzés elindítva (Maradt: {balance.count} db)"
            )
            return True, balance.count
        return False, 0

def refund_analysis(user, reason="Hiba az elemzés során"): # Adjunk hozzá alapértelmezett indokot
    """Elemzési egység visszatérítése hiba esetén."""
    with transaction.atomic():
        balance, _ = UserAnalysisBalance.objects.get_or_create(user=user)
        balance.count += 1
        balance.save()
        
        FinancialTransaction.objects.create(
            user=user,
            transaction_type='EARN',
            amount=0,
            description=f"Visszatérítés: {reason} (+1 elemzés)"
        )
        return True, balance.count

def has_active_subscription(user, sub_type):
    return UserSubscription.objects.filter(user=user, sub_type=sub_type, expiry_date__gt=timezone.now()).exists()
