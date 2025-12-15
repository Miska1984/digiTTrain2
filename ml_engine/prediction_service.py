# ml_engine/prediction_service.py

import os
import joblib
import pandas as pd
from django.conf import settings
from ml_engine.features import FeatureBuilder
from ml_engine.models import PredictedForm
import logging

logger = logging.getLogger(__name__)


class PredictionService:
    """
    Betölti a mentett modellt és előrejelzést készít egy adott userre.
    Az eredményt automatikusan elmenti az adatbázisba.
    """

    MODEL_PATH = os.path.join(settings.BASE_DIR, "ml_engine", "trained_models", "form_predictor.pkl")

    def __init__(self):
        if not os.path.exists(self.MODEL_PATH):
            raise FileNotFoundError(f"❌ A modell nem található: {self.MODEL_PATH}")
        self.model = joblib.load(self.MODEL_PATH)
        logger.info(f"🤖 Modell betöltve: {self.MODEL_PATH}")

    def predict_for_user(self, user):
        """
        Egy adott userhez generál feature-öket és előrejelzi a form_score-t.
        Eredményt elmenti a PredictedForm táblába.
        """
        logger.info(f"🔮 Predikció indítása userre: {user}")

        fb = FeatureBuilder(user)
        features_list = fb.build()

        if not features_list:
            logger.warning("⚠️ Nincsenek feature-ök ehhez a userhez.")
            return None

        df = pd.DataFrame(features_list)

        # Kódolás a nem numerikus oszlopokra
        for col in df.columns:
            if df[col].dtype == "object":
                df[col] = df[col].astype("category").cat.codes

        # Predikció
        prediction = float(self.model.predict(df)[0])
        logger.info(f"✅ Predikció sikeres: {prediction:.3f}")

        # Mentés adatbázisba
        PredictedForm.objects.create(user=user, form_score=prediction)
        logger.info(f"💾 Predikció mentve adatbázisba user={user} érték={prediction:.3f}")

        return prediction
