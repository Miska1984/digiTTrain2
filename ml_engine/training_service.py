# ml_engine/training_service.py
import os
import joblib
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from django.conf import settings
import logging

from ml_engine.models import UserFeatureSnapshot
from ml_engine.data_generator import SyntheticDataGenerator # Beemeljük a generátort
from .ai_coach_service import DittaCoachService

logger = logging.getLogger(__name__)

class TrainingService:
    # --- JAVÍTÁS: Cloud Run kompatibilis útvonal ---
    # Az /app írásvédett, a /tmp írható.
    MODEL_PATH = "/tmp/form_predictor.pkl"

    def __init__(self):
        # /tmp esetén nem kötelező, de jó gyakorlat
        os.makedirs(os.path.dirname(self.MODEL_PATH), exist_ok=True)
        self.model = self.load_model()

    def load_model(self):
        if os.path.exists(self.MODEL_PATH):
            try:
                # Ezt a sort is ellenőrizd, hogy a joblib megfelelően tölt-e be
                return joblib.load(self.MODEL_PATH)
            except Exception as e:
                logger.error(f"❌ Modell betöltése sikertelen: {e}")
                return None
        return None

    # ------------------------------------------------------
    # HIBRID ADAT-ELŐKÉSZÍTÉS
    # ------------------------------------------------------
    def _prepare_training_data(self):
        """Összegyűjti a valódi adatokat és kiegészíti szintetikussal."""
        real_snapshots = UserFeatureSnapshot.objects.all()
        
        processed_real_data = []
        for s in real_snapshots:
            f = s.features
            if isinstance(f, list) and len(f) > 0:
                f = f[0]
            if isinstance(f, dict):
                processed_real_data.append(f)

        real_df = pd.DataFrame(processed_real_data)
        generator = SyntheticDataGenerator()
        synthetic_df = generator.generate_batch(count_per_category=2500)
        
        if not real_df.empty:
            final_df = pd.concat([real_df, synthetic_df], ignore_index=True)
        else:
            final_df = synthetic_df

        for col in final_df.columns:
            if col != 'category':
                final_df[col] = pd.to_numeric(final_df[col], errors='coerce')

        return final_df.fillna(0)

    # ------------------------------------------------------
    # MODELL TANÍTÁSA
    # ------------------------------------------------------
    def train_model(self):
        """Összeállítja az adatokat és betanítja a modellt."""
        df = self._prepare_training_data()

        if "form_score" not in df.columns:
            logger.error("⚠️ Hiányzik a 'form_score' oszlop!")
            return

        if 'category' in df.columns:
            df['category'] = df['category'].astype('category').cat.codes

        df = df.fillna(0)

        X = df.drop(columns=["form_score"])
        y = df["form_score"]

        X.columns = X.columns.astype(str)

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        model.fit(X_train, y_train)

        # --- MENTÉS A /tmp-be ---
        try:
            joblib.dump(model, self.MODEL_PATH)
            self.model = model
            logger.info(f"✅ Modell sikeresen elmentve a /tmp-be: {self.MODEL_PATH}")
        except Exception as e:
            logger.error(f"❌ Mentési hiba: {e}")

    # ------------------------------------------------------
    # PREDIKCIÓ (marad az eredeti logikád, csak kicsit tisztítva)
    # ------------------------------------------------------
    def predict_form(self, user):
        # A load_model() már az új MODEL_PATH-t nézi az __init__-ben
        if not self.model:
            self.model = self.load_model()
            
        if not self.model:
            logger.warning("⚠️ Nincs betöltött modell.")
            return None, None

        try:
            latest_snapshot = UserFeatureSnapshot.objects.filter(user=user).order_by("-snapshot_date").first()
            if not latest_snapshot:
                return None, None
                
            features = latest_snapshot.features
            data_for_df = features if isinstance(features, list) else [features]
            df_pred = pd.DataFrame(data_for_df)
            
            if "form_score" in df_pred.columns:
                df_pred = df_pred.drop(columns=["form_score"])

            if 'category' in df_pred.columns:
                df_pred['category'] = df_pred['category'].map({
                    'COMBAT': 0, 'STRENGTH': 1, 'ENDURANCE': 2, 'REHAB': 3
                }).fillna(0)

            X_pred = df_pred.select_dtypes(include=[np.number])
            # Fontos: itt is kényszerítsük a string oszlopneveket a predikciónál
            X_pred.columns = X_pred.columns.astype(str)

            prediction = self.model.predict(X_pred)[0]
            predicted_value = float(prediction)
            
            try:
                coach = DittaCoachService()
                coach.generate_advice(user)
                logger.info(f"✅ Ditta tanács generálva: {user.username}")
            except Exception as ai_err:
                logger.error(f"⚠️ Ditta hiba: {ai_err}")

            return latest_snapshot.snapshot_date, predicted_value

        except Exception as e:
            logger.error(f"❌ Predikciós hiba: {e}")
            return None, None
        

        