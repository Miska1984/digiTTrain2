# ml_engine/tasks.py
import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from users.models import User
from ml_engine.features import FeatureBuilder
from ml_engine.models import UserFeatureSnapshot
from ml_engine.training_service import TrainingService
from billing.models import UserSubscription, ServicePlan

logger = logging.getLogger(__name__)

# ======================================================================
# 1️⃣ NAPI FEATURE GENERÁLÁS – minden felhasználóra
# ======================================================================
@shared_task(queue="ml_engine")
def generate_user_features():
    """
    Napi feature snapshot generálás minden userre (függetlenül az előfizetéstől).
    Az ML modell így gazdagabb adathalmazból tanul.
    """
    logger.info("🚀 [ML_ENGINE] Feature generálás indul minden userre...")
    generated_count = 0

    users = User.objects.all()
    logger.info(f"👥 {users.count()} user feldolgozása...")

    for user in users:
        try:
            fb = FeatureBuilder(user)
            features_list = fb.build()

            if not features_list:
                logger.warning(f"⚠️ {user.email} - nincs elég adat a feature generáláshoz.")
                continue

            with transaction.atomic():
                # Eltávolítjuk a korábbi snapshotot az adott napra
                UserFeatureSnapshot.objects.filter(
                    user=user, generated_at__date=timezone.now().date()
                ).delete()

                # Új snapshot mentése
                UserFeatureSnapshot.objects.create(
                    user=user,
                    features=features_list[0],
                )

                generated_count += 1
                logger.info(f"✅ Feature snapshot létrehozva: {user.email}")

        except Exception as e:
            logger.error(f"❌ Hiba a {user.email} feldolgozásakor: {e}", exc_info=True)

    logger.info(f"🏁 Összesen {generated_count} feature snapshot elkészült.")


# ======================================================================
# 2️⃣ MODELL TRÉNING – az összes user adatával
# ======================================================================
@shared_task(queue="ml_engine")
def train_form_prediction_model():
    """
    Form prediction modell újratanítása a snapshotok alapján.
    A tréningbe minden user adata bekerül – még a nem előfizetőké is.
    """
    logger.info("📈 [ML_ENGINE] Modell tréning task indul...")

    try:
        df = UserFeatureSnapshot.to_training_dataframe()
    except Exception as e:
        logger.error(f"❌ Hiba a snapshot DataFrame előállításakor: {e}", exc_info=True)
        return

    if df.empty:
        logger.warning("⚠️ Nincs elég adat a tréninghez.")
        return

    try:
        trainer = TrainingService()
        trainer.train_model(df)
        logger.info("✅ Modell tréning sikeresen befejezve.")
    except Exception as e:
        logger.error(f"❌ Modell tréning hiba: {e}", exc_info=True)


# ======================================================================
# 3️⃣ PREDIKCIÓ – csak aktív ML előfizetőknek
# ======================================================================
@shared_task(queue="ml_engine")
def predict_form_for_active_subscribers():
    """
    Csak azoknak a felhasználóknak generál predikciót,
    akiknek aktív ML-hozzáférést tartalmazó előfizetésük van.
    """
    logger.info("🤖 [ML_ENGINE] Formaindex predikció indul aktív előfizetőkre...")

    # 🟢 JAVÍTVA: Az új ServicePlan struktúra szerint keressük az ML csomagokat
    ml_plans = ServicePlan.objects.filter(plan_type='ML_ACCESS', is_active=True)
    
    if not ml_plans.exists():
        logger.warning("⚠️ Nincs ML hozzáférést biztosító ServicePlan beállítva!")
        return

    # 🟢 JAVÍTVA: UserSubscription szűrése az új mezőnevek (sub_type, expiry_date) alapján
    active_subs = UserSubscription.objects.filter(
        sub_type='ML_ACCESS',
        expiry_date__gte=timezone.now()
    ).select_related("user")

    if not active_subs.exists():
        logger.info("ℹ️ Nincs aktív ML előfizető jelenleg.")
        return

    trainer = TrainingService()
    processed_count = 0

    for sub in active_subs:
        user = sub.user
        try:
            from ml_engine.models import UserPredictionResult
            pred_date, prediction = trainer.predict_form(user)

            if pred_date and prediction is not None:
                UserPredictionResult.objects.update_or_create(
                    user=user,
                    defaults={
                        "predicted_at": timezone.now(),
                        "form_score": prediction,
                        "source_date": pred_date,
                    },
                )
                processed_count += 1
                logger.info(f"✅ Predikció elmentve {user.email} számára: {prediction:.2f}")
        except Exception as e:
            logger.error(f"❌ Hiba a predikció során ({user.email}): {e}", exc_info=True)

    logger.info(f"🏁 {processed_count} előfizető predikciója sikeresen elkészült.")


# ======================================================================
# 4️⃣ EGYSZERI / DEBUG FELADAT – egy adott userre
# ======================================================================
@shared_task(queue="ml_engine")
def generate_user_features_for_user(user_id):
    """
    Feature snapshot generálása egy adott felhasználónak (debug / admin célokra).
    Ez a funkció akkor is futhat, ha nincs előfizetése – tanulási célból.
    """
    logger.info(f"🚀 [ML_ENGINE] Feature generálás indul a user ID={user_id} számára...")

    try:
        user = User.objects.get(id=user_id)
        fb = FeatureBuilder(user)
        features_list = fb.build()

        if not features_list:
            logger.warning(f"⚠️ {user.email} - nincs elég adat a feature generáláshoz.")
            return "⚠️ Nincs elég adat a feature generáláshoz."

        with transaction.atomic():
            UserFeatureSnapshot.objects.filter(
                user=user, generated_at__date=timezone.now().date()
            ).delete()

            UserFeatureSnapshot.objects.create(
                user=user,
                features=features_list[0],
            )

        logger.info(f"✅ Feature snapshot létrehozva: {user.email}")
        return f"✅ Feature snapshot létrehozva a felhasználónak: {user.email}"

    except Exception as e:
        logger.error(f"❌ Hiba a user (id={user_id}) feldolgozásakor: {e}", exc_info=True)
        return f"❌ Hiba történt: {e}"
