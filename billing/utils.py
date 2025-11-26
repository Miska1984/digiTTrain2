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
def refund_analysis(job_instance):
    """
    Visszatéríti a levont elemzési Credit-et egy hibásan lefutott job esetén.
    A job_instance a DiagnosticJob modell példánya.
    """
    from .models import AnalysisTransaction # A ciklikus import elkerülése miatt a modellen belül kell importálni
    
    user = job_instance.user
    
    # 1. Megkeressük az eredeti, negatív USAGE tranzakciót
    try:
        usage_transaction = AnalysisTransaction.objects.get(
            related_job=job_instance,
            transaction_type='USAGE',
            amount__lt=0  # Csak a negatív levonásokat keressük
        )
    except AnalysisTransaction.DoesNotExist:
        logger.warning(f"⚠️ Nincs levonási tranzakció a Job ID {job_instance.id} számára. Nincs teendő.")
        return False

    # Megnézzük, hogy a tranzakciót már visszatérítették-e
    if usage_transaction.amount > 0:
        logger.warning(f"⚠️ A Job ID {job_instance.id} tranzakciója már pozitív. Nincs teendő.")
        return False
        
    # 2. Visszatérítés összegének meghatározása (az eredeti levonás abszolút értéke)
    refund_amount = abs(usage_transaction.amount) # Pl. ha -1 volt, akkor +1
    
    # 3. Hozzáadjuk a Credit-et az egyenleghez (ez frissíti a UserAnalysisBalance-t)
    # Az add_analysis_balance már tranzakcióban fut.
    add_analysis_balance(
        user=user, 
        amount=refund_amount, 
        description=f"Visszatérítés hibás job miatt (Job ID: {job_instance.id}). Hiba: {job_instance.error_message or 'Ismeretlen hiba'}",
        transaction_type='PURCHASE' # Ez a típus nem ideális, lehetne 'REFUND' is. Nézze meg, van-e 'REFUND' a choices-ban, ha nincs, akkor 'PURCHASE' (jóváírás) a legjobb választás.
    )

    logger.info(f"✅ Visszatérítés sikeres {user.username} felhasználónak {refund_amount} Credit: Job ID {job_instance.id}")
    return True


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
