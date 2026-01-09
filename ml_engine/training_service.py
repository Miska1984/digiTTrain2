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
from .ai_coach_service import AICoachService

logger = logging.getLogger(__name__)

class TrainingService:
    MODEL_PATH = os.path.join(settings.BASE_DIR, "ml_engine", "trained_models", "form_predictor.pkl")

    def __init__(self):
        os.makedirs(os.path.dirname(self.MODEL_PATH), exist_ok=True)
        self.model = self.load_model()

    def load_model(self):
        if os.path.exists(self.MODEL_PATH):
            try:
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
            # Ha a features véletlenül lista marad: [ {...} ]
            if isinstance(f, list) and len(f) > 0:
                f = f[0]
            
            # Csak akkor adjuk hozzá, ha szótár és nem üres
            if isinstance(f, dict):
                processed_real_data.append(f)

        real_df = pd.DataFrame(processed_real_data)
        
        # Szintetikus adatok
        generator = SyntheticDataGenerator()
        synthetic_df = generator.generate_batch(count_per_category=2500)
        
        if not real_df.empty:
            # Itt a trükk: Csak azokat az oszlopokat tartsuk meg, amik mindkettőben megvannak
            # és dobjuk ki azokat a mezőket, amik véletlenül objektumok maradtak
            final_df = pd.concat([real_df, synthetic_df], ignore_index=True)
        else:
            final_df = synthetic_df

        # KÉNYSZERÍTÉS: Minden oszlop legyen numerikus (kivéve a 'category'-t, amit később kódolunk)
        # Ez kidobja a maradék 'dict' vagy 'list' típusú szemetet a cellákból
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

        # Kategória átalakítása számmá
        if 'category' in df.columns:
            df['category'] = df['category'].astype('category').cat.codes

        # Hiányzó értékek kezelése
        df = df.fillna(0)

        # Split
        X = df.drop(columns=["form_score"])
        y = df["form_score"]

        # --- EZ AZ ÚJ SOR, AMI MEGOLDJA A HIBÁT ---
        X.columns = X.columns.astype(str)
        # -----------------------------------------

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        model.fit(X_train, y_train)

        # Mentés
        joblib.dump(model, self.MODEL_PATH)
        self.model = model
        logger.info(f"✅ Modell sikeresen frissítve: {self.MODEL_PATH}")

    # ------------------------------------------------------
    # PREDIKCIÓ (marad az eredeti logikád, csak kicsit tisztítva)
    # ------------------------------------------------------
    def predict_form(self, user):
        if not self.model:
            logger.warning("⚠️ Nincs betöltött modell.")
            return None, None

        try:
            # 1. Snapshot keresése
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

            # 2. ML Predikció futtatása
            prediction = self.model.predict(X_pred)[0]
            predicted_value = float(prediction)
            
            # 3. AI COACH MEGHÍVÁSA (Itt generáljuk le a tanácsot a friss eredmény alapján)
            try:
                coach = AICoachService()
                coach.generate_advice(user)
                logger.info(f"✅ AI Coach tanács generálva a következő felhasználónak: {user.username}")
            except Exception as ai_err:
                logger.error(f"⚠️ AI Coach hiba (de a predikció kész): {ai_err}")

            return latest_snapshot.snapshot_date, predicted_value

        except Exception as e:
            logger.error(f"❌ Predikciós hiba: {e}")
            return None, None
        

        