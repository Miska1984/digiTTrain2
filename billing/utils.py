import logging
from datetime import date, timedelta
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from .models import (
    UserAnalysisBalance,
    AnalysisTransaction,
    AdViewStreak,
    JobPrice,
    UserJobDiscount
)

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. ELEMZÉSI EGYENLEG KEZELÉSE
# ==============================================================================

def get_analysis_balance(user):
    """
    Lekéri a felhasználó elemzési egyenlegét.
    Ha még nincs rekord, létrehozza 0-val.
    """
    balance, _ = UserAnalysisBalance.objects.get_or_create(user=user, defaults={'analysis_count': 0})
    return balance.analysis_count


@transaction.atomic
def add_analysis_balance(user, amount, description="Elemzési csomag vásárlás"):
    """
    Hozzáad elemzési egyenleget (darabszám) a felhasználóhoz.
    Ez a függvény most a UserAnalysisBalance.add_credits() wrapperje.
    """
    balance, _ = UserAnalysisBalance.objects.select_for_update().get_or_create(user=user)
    balance.add_credits(amount, description=description, transaction_type='PURCHASE')

    logger.info(
        f"✅ Elemzési egyenleg növelve: {user.username} +{amount} db "
        f"(Új egyenleg: {balance.analysis_count})"
    )
    return balance.analysis_count


@transaction.atomic
def dedicate_analysis(user, job_instance):
    """
    Levon 1 db elemzést a felhasználó egyenlegéből.
    Használat: elemzés indításakor.
    Returns: (success: bool, new_balance: int)
    """
    try:
        balance = UserAnalysisBalance.objects.select_for_update().get(user=user)
    except UserAnalysisBalance.DoesNotExist:
        logger.warning(f"❌ Nincs elemzési egyenleg: {user.username}")
        return False, 0

    success = balance.use_credits(
        amount=1,
        related_job=job_instance,
        description=f'Elemzés felhasználva: {job_instance.get_job_type_display()}'
    )

    if not success:
        logger.warning(f"⚠️ Nincs elég elemzés: {user.username} (Egyenleg: {balance.analysis_count})")
        return False, balance.analysis_count

    logger.info(f"✅ Elemzés levonva: {user.username} -1 db (Új egyenleg: {balance.analysis_count})")
    return True, balance.analysis_count


@transaction.atomic
def refund_analysis(user, job_instance, reason="Sikertelen elemzés"):
    """
    1 elemzés visszatérítése (pl. ha hibás volt az elemzés).
    """
    balance, _ = UserAnalysisBalance.objects.select_for_update().get_or_create(user=user)
    balance.add_credits(
        amount=1,
        description=f'Visszatérítés: {reason}',
        transaction_type='REFUND',
    )
    logger.info(f"↩️ Elemzés visszatérítve: {user.username} +1 db (Új egyenleg: {balance.analysis_count})")
    return balance.analysis_count


# ==============================================================================
# 2. ELEMZÉSI ÁR SZÁMÍTÁSA (Kedvezményekkel)
# ==============================================================================

def calculate_job_cost(user, job_type_code):
    """
    Kedvezményes ár kiszámítása – a darabszám alapú rendszerben csak kompatibilitási okból.
    """
    try:
        job_price = JobPrice.objects.get(job_type=job_type_code)
        base_price = job_price.base_price_ft
    except JobPrice.DoesNotExist:
        logger.error(f"[Billing] Nincs ár definiálva a {job_type_code} típushoz.")
        return Decimal('0.00')

    # Kedvezmény alkalmazása (ha van)
    try:
        discount_obj = UserJobDiscount.objects.get(user=user, job_type=job_type_code)
        discount_percent = discount_obj.discount_percentage or 0
        final_price = base_price * (Decimal('1.0') - Decimal(discount_percent) / Decimal('100'))
    except UserJobDiscount.DoesNotExist:
        final_price = base_price

    return final_price


# ==============================================================================
# 3. HIRDETÉSNÉZÉSI SOROZAT (STREAK) KEZELÉSE
# ==============================================================================

def check_ad_streak(user):
    """
    Ellenőrzi a felhasználó hirdetésnézési sorozatát.
    Returns: (current_streak: int, can_view_today: bool)
    """
    streak, _ = AdViewStreak.objects.get_or_create(user=user, defaults={'current_streak': 0})
    today = date.today()
    can_view_today = (streak.last_view_date != today)
    return streak.current_streak, can_view_today


@transaction.atomic
def reward_ad_view(user):
    """
    Naplózza a hirdetés megtekintést, frissíti a streak-et, és ha 5 nap elérve,
    jutalmaz 1 db elemzéssel.
    Returns: (success: bool, streak: int, rewarded: bool)
    """
    streak, _ = AdViewStreak.objects.select_for_update().get_or_create(user=user, defaults={'current_streak': 0})
    today = date.today()

    if streak.last_view_date == today:
        logger.info(f"ℹ️ {user.username} ma már nézett hirdetést.")
        return False, streak.current_streak, False

    # Sorozat folytatása vagy újrakezdése
    if streak.last_view_date == today - timedelta(days=1):
        streak.current_streak += 1
    else:
        streak.current_streak = 1

    streak.last_view_date = today
    rewarded = False

    if streak.current_streak >= 5:
        add_analysis_balance(
            user=user,
            amount=1,
            description="🎁 Hirdetésnézési jutalom (5 egymást követő nap)"
        )
        streak.total_rewards_earned += 1
        streak.current_streak = 0
        rewarded = True
        logger.info(f"🎉 {user.username} jutalmat kapott: +1 ingyenes elemzés")

    streak.save()
    return True, streak.current_streak, rewarded
