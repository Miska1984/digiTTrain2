# ml_engine/tasks.py

import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction

from users.models import User
from ml_engine.features import FeatureBuilder
from ml_engine.models import UserFeatureSnapshot, UserPredictionResult # Felülre hozva
from ml_engine.training_service import TrainingService
from billing.models import UserSubscription

logger = logging.getLogger(__name__)

@shared_task(queue="ml_engine")
def generate_user_features():
    """
    Napi feature snapshot generálás minden userre.
    """
    logger.info("🚀 [ML_ENGINE] Feature generálás indul minden userre...")
    generated_count = 0
    today = timezone.now().date()

    users = User.objects.all()
    for user in users:
        try:
            fb = FeatureBuilder(user)
            # FONTOS: Ez most már egy SZÓTÁR (dict), nem lista!
            features_dict = fb.build()

            if not features_dict:
                continue

            # JAVÍTÁS: features_list[0] helyett közvetlenül a szótárat adjuk át
            # Ha véletlenül mégis lista jönne (régi kód miatt), lekezeljük:
            final_features = features_dict[0] if isinstance(features_dict, list) else features_dict

            UserFeatureSnapshot.objects.update_or_create(
                user=user,
                snapshot_date=today,
                defaults={'features': final_features}
            )
            generated_count += 1
        except Exception as e:
            logger.error(f"❌ Hiba a {user.username} feldolgozásakor: {e}")

    logger.info(f"🏁 Összesen {generated_count} feature snapshot elkészült.")

@shared_task(queue="ml_engine")
def predict_form_for_active_subscribers():
    """Predikció futtatása az előfizetőknek."""
    logger.info("🤖 [ML_ENGINE] Formaindex predikció indul...")

    active_subs = UserSubscription.objects.filter(
        sub_type='ML_ACCESS',
        expiry_date__gte=timezone.now()
    ).select_related("user")

    trainer = TrainingService()
    processed_count = 0

    for sub in active_subs:
        user = sub.user
        try:
            pred_date, prediction = trainer.predict_form(user)

            if prediction is not None:
                UserPredictionResult.objects.update_or_create(
                    user=user,
                    defaults={
                        "predicted_at": timezone.now(),
                        "form_score": prediction,
                        "source_date": pred_date.date() if pred_date else timezone.now().date(),
                    },
                )
                processed_count += 1
        except Exception as e:
            logger.error(f"❌ Hiba a predikció során ({user.username}): {e}")

    logger.info(f"🏁 {processed_count} predikció elkészült.")

    