# ml_engine/task.py 
import logging
from django.utils import timezone
from django.db import transaction

from users.models import User
from ml_engine.features import FeatureBuilder
from ml_engine.models import UserFeatureSnapshot, UserPredictionResult
from ml_engine.training_service import TrainingService
from billing.models import UserSubscription

logger = logging.getLogger(__name__)

def generate_user_features():
    """
    Napi feature snapshot generálás minden userre.
    KÖZVETLENÜL HÍVHATÓ FÜGGVÉNY (nem Celery task).
    """
    logger.info("🚀 [ML_ENGINE] Feature generálás indul minden userre...")
    generated_count = 0
    today = timezone.now().date()

    users = User.objects.all()
    for user in users:
        try:
            fb = FeatureBuilder(user)
            features_dict = fb.build()

            if not features_dict:
                continue

            # Ha véletlenül lista jönne vissza, akkor az első elemet vesszük
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

    logger.info(f"🏁 Összesen {generated_count} feature snapshot elkészült.")
    return generated_count

def train_form_prediction_model():
    """
    Hibrid modell tréning.
    """
    logger.info("🎓 [ML_ENGINE] Modell tréning indul...")
    
    try:
        trainer = TrainingService()
        
        # JAVÍTÁS: Hozzáadjuk a 'train_model' ellenőrzést, mert ez a valódi neve a szervizben!
        if hasattr(trainer, 'train_model'):
            metrics = trainer.train_model()
        elif hasattr(trainer, 'train_with_synthetic_data'):
            metrics = trainer.train_with_synthetic_data()
        elif hasattr(trainer, 'train'):
            metrics = trainer.train()
        else:
            raise AttributeError("TrainingService-nek nincs train_model, train vagy train_with_synthetic_data metódusa!")
        
        logger.info(f"✅ Tréning sikeres. Metrikák: {metrics}")
        return metrics
    except Exception as e:
        logger.error(f"❌ Tréning hiba: {e}", exc_info=True)
        raise

def predict_form_for_active_subscribers():
    """
    Predikció futtatása az előfizetőknek.
    KÖZVETLENÜL HÍVHATÓ FÜGGVÉNY (nem Celery task).
    """
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
                logger.info(f"✅ Predikció készült: {user.username} -> {prediction:.2f}")
        except Exception as e:
            logger.error(f"❌ Hiba a predikció során ({user.username}): {e}", exc_info=True)

    logger.info(f"🏁 {processed_count} predikció elkészült.")
    return processed_count

def predict_form_for_active_subscribers():
    """
    Predikció futtatása az előfizetőknek.
    KÖZVETLENÜL HÍVHATÓ FÜGGVÉNY (nem Celery task).
    """
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
                        "source_date": pred_date if pred_date else timezone.now().date(),
                    },
                )
                processed_count += 1
                logger.info(f"✅ Predikció készült: {user.username} -> {prediction:.2f}")
        except Exception as e:
            logger.error(f"❌ Hiba a predikció során ({user.username}): {e}", exc_info=True)

    logger.info(f"🏁 {processed_count} predikció elkészült.")
    return processed_count

