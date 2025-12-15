# ml_engine/training_service.py

import os
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class TrainingService:
    """
    A modell tanításért és predikcióért felelős szolgáltatás.
    """
    MODEL_PATH = os.path.join(settings.BASE_DIR, "ml_engine", "trained_models", "form_predictor.pkl")

    def __init__(self):
        os.makedirs(os.path.dirname(self.MODEL_PATH), exist_ok=True)
        self.model = self.load_model()  # <<< EZ A LÉNYEG!

    def load_model(self):
        """Megpróbálja betölteni a már betanított modellt."""
        if os.path.exists(self.MODEL_PATH):
            try:
                model = joblib.load(self.MODEL_PATH)
                logger.info(f"📦 Modell betöltve: {self.MODEL_PATH}")
                return model
            except Exception as e:
                logger.error(f"❌ Modell betöltése sikertelen: {e}")
                return None
        else:
            logger.warning("⚠️ Nincs mentett modell, új tanítás szükséges.")
            return None

    def train_model(self, df: pd.DataFrame):
        logger.info(f"🎯 Tanítás indul {len(df)} sorral...")

        if "form_score" not in df.columns:
            logger.warning("⚠️ A DataFrame nem tartalmaz 'form_score' oszlopot, tréning kihagyva.")
            return

        for col in df.columns:
            if df[col].dtype == "object":
                df[col] = df[col].astype("category").cat.codes

        df = df.dropna(subset=["form_score"])
        if df.empty:
            logger.warning("⚠️ Minden form_score érték hiányzik, tréning kihagyva.")
            return

        if len(df) < 3:
            X_train, y_train = df.drop(columns=["form_score"]), df["form_score"]
        else:
            X_train, _, y_train, _ = train_test_split(
                df.drop(columns=["form_score"]),
                df["form_score"],
                test_size=0.2,
                random_state=42
            )

        model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        model.fit(X_train, y_train)

        joblib.dump(model, self.MODEL_PATH)
        self.model = model  # <<< FONTOS: mostantól az objektumban is elérhető
        logger.info(f"✅ Modell elmentve ide: {self.MODEL_PATH}")

    def predict_form(self, user):
        """
        A megadott felhasználó legfrissebb feature-snapshotját használja a forma index előrejelzésére.
        Visszatér: (dátum, predikció) vagy (None, None), ha nem sikerül.
        """
        from ml_engine.models import UserFeatureSnapshot  # késleltetett import a körkörös hivatkozások miatt
        import numpy as np
        from datetime import datetime

        if not self.model:
            logger.warning("⚠️ Nincs betöltött modell a predikcióhoz.")
            return None, None

        try:
            # Legutóbbi snapshot kiválasztása
            latest_snapshot = UserFeatureSnapshot.objects.filter(user=user).latest("generated_at")
            features = latest_snapshot.features

            if not isinstance(features, dict):
                logger.error("❌ Snapshot features mező nem dict típusú.")
                return None, None

            # Pandas DataFrame konverzió (egysoros)
            X_pred = pd.DataFrame([features])

            # Csak numerikus oszlopok megtartása
            X_pred = X_pred.select_dtypes(include=[np.number]).fillna(0)

            predicted_value = self.model.predict(X_pred)[0]
            logger.info(f"✅ Predikció sikeres: {predicted_value:.2f}")

            return latest_snapshot.generated_at, float(predicted_value)

        except UserFeatureSnapshot.DoesNotExist:
            logger.warning(f"⚠️ Nincs elérhető snapshot {user.username} számára.")
            return None, None
        except Exception as e:
            logger.error(f"❌ Predikciós hiba: {e}")
            return None, None
