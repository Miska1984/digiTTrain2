# ml_engine/tasks.py
import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from users.models import User
from ml_engine.features import FeatureBuilder
from ml_engine.models import UserFeatureSnapshot
from ml_engine.training_service import TrainingService

logger = logging.getLogger(__name__)

@shared_task(queue="ml_engine")
def generate_user_features():
    """Napi feature snapshot generálás minden felhasználóra."""
    logger.info("🚀 [ML_ENGINE] Feature generálás indul minden userre...")
    generated_count = 0

    users = User.objects.all()
    logger.info(f"👥 {users.count()} user feldolgozása...")

    for user in users:
        try:
            fb = FeatureBuilder(user)
            features_list = fb.build()
            if not features_list:
                logger.warning(f"⚠️ {user} - nincs elég adat a feature generáláshoz.")
                continue

            with transaction.atomic():
                UserFeatureSnapshot.objects.filter(
                    user=user, generated_at__date=timezone.now().date()
                ).delete()

                UserFeatureSnapshot.objects.create(
                    user=user,
                    features=features_list[0],
                )
                generated_count += 1
                logger.info(f"✅ Feature snapshot létrehozva: {user.email}")

        except Exception as e:
            logger.error(f"❌ Hiba a {user.email} feldolgozásakor: {e}", exc_info=True)

    logger.info(f"🏁 Összesen {generated_count} feature snapshot elkészült.")


@shared_task(queue="ml_engine")
def train_form_prediction_model():
    """Form prediction modell újratanítása a feature snapshotok alapján."""
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

@shared_task(queue="ml_engine")
def generate_user_features_for_user(user_id):
    """Feature snapshot generálása egy adott felhasználónak."""
    logger.info(f"🚀 [ML_ENGINE] Feature generálás indul a user ID={user_id} számára...")

    try:
        user = User.objects.get(id=user_id)
        fb = FeatureBuilder(user)
        features_list = fb.build()

        if not features_list:
            logger.warning(f"⚠️ {user} - nincs elég adat a feature generáláshoz.")
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