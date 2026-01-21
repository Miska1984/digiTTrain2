# ml_engine/tasks.py
import logging
from datetime import date
from django.utils import timezone
from django.db import transaction
from django.utils.timezone import make_aware
from datetime import datetime

from users.models import User
from ml_engine.features import FeatureBuilder
from ml_engine.models import UserFeatureSnapshot, UserPredictionResult
from ml_engine.training_service import TrainingService
from billing.models import UserSubscription
from users.models import UserRole

logger = logging.getLogger(__name__)

def generate_user_features():
    """Napi feature snapshot generálás - CSAK JÓVÁHAGYOTT SPORTOLÓKNAK."""
    logger.info("🚀 [ML_ENGINE] Feature generálás indul a sportolóknak...")
    generated_count = 0
    today = timezone.now().date()

    # Szűrés: CSAK azok a userek, akiknek van 'Sportoló' szerepkörük és 'approved' státuszúak
    sportolo_users = User.objects.filter(
        user_roles__role__name='Sportoló',
        user_roles__status='approved'
    ).distinct()

    for user in sportolo_users:
        try:
            fb = FeatureBuilder(user)
            features_dict = fb.build()

            if not features_dict:
                continue

            # JAVÍTÁS: Itt biztosítjuk, hogy a változó neve konzisztens legyen
            # A build() vagy dict-et vagy listát ad vissza, ezt kezeljük le:
            final_features = features_dict[0] if isinstance(features_dict, list) else features_dict

            UserFeatureSnapshot.objects.update_or_create(
                user=user,
                snapshot_date=today,
                defaults={'features': final_features}
            )
            generated_count += 1
            logger.info(f"✅ Feature snapshot készült: {user.username}")
        except Exception as e:
            logger.error(f"❌ Hiba a {user.username} feldolgozásakor: {e}", exc_info=True)

    logger.info(f"🏁 Összesen {generated_count} sportoló feature snapshot elkészült.")
    return generated_count

def train_form_prediction_model():
    """Modell tréning indítása a TrainingService segítségével."""
    try:
        trainer = TrainingService()
        success = trainer.train_model()
        if success:
            logger.info("✅ Napi modell tanítás és GCS feltöltés sikeres.")
        else:
            logger.warning("⚠️ A modell tanítás nem futott le (kevés adat?).")
    except Exception as e:
        logger.error(f"❌ Tréning hiba: {e}", exc_info=True)
        raise

def predict_form_for_active_subscribers():
    """Predikció futtatása - CSAK ELŐFIZETŐ SPORTOLÓKNAK."""
    logger.info("🤖 [ML_ENGINE] Formaindex predikció indul...")

    # Szűrés: aktív ML előfizetés ÉS Sportoló szerepkör
    active_subs = UserSubscription.objects.filter(
        sub_type='ML_ACCESS',
        expiry_date__gte=timezone.now(),
        user__user_roles__role__name='Sportoló',
        user__user_roles__status='approved'
    ).select_related("user").distinct()

    trainer = TrainingService()
    processed_count = 0

    for sub in active_subs:
        user = sub.user
        try:
            pred_date, prediction = trainer.predict_form(user)

            if prediction is not None:
                # Dátum átalakítása timezone-aware formátumba, ha szükséges
                source_val = pred_date
                if isinstance(source_val, date) and not isinstance(source_val, datetime):
                    # Ha csak date, csinálunk belőle éjféli datetime-ot a mai napra
                    source_val = make_aware(datetime.combine(source_val, datetime.min.time()))
                elif isinstance(source_val, datetime) and source_val.tzinfo is None:
                    source_val = make_aware(source_val)
                
                UserPredictionResult.objects.update_or_create(
                    user=user,
                    defaults={
                        "predicted_at": timezone.now(),
                        "form_score": prediction,
                        "source_date": source_val,
                    },
                )
                processed_count += 1
                logger.info(f"✅ Predikció készült: {user.username} -> {prediction:.2f}")
        except Exception as e:
            logger.error(f"❌ Hiba a predikció során ({user.username}): {e}", exc_info=True)

    logger.info(f"🏁 Összesen {processed_count} predikció frissítve.")
    return processed_count