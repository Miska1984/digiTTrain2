# ml_engine/training_service.py
import os
import joblib
import pandas as pd
import numpy as np
import logging
from django.conf import settings
from google.cloud import storage
from google.oauth2 import service_account

from sklearn.ensemble import RandomForestRegressor
from ml_engine.models import UserFeatureSnapshot
from ml_engine.data_generator import SyntheticDataGenerator
from .ai_coach_service import DittaCoachService

logger = logging.getLogger(__name__)

class TrainingService:
    # Helyi ideiglenes útvonal (Cloud Run-on és Codespace-ben is írható)
    LOCAL_MODEL_PATH = "/tmp/form_predictor.pkl"
    # GCS-en belüli útvonal
    GCS_MODEL_PATH = "models/form_predictor.pkl"

    # 🔹 DEFINIÁLJUK A FIX SORRENDET
    FEATURE_COLUMNS = [
        'age', 'gender', 'category', 'avg_hrv', 'avg_sleep', 
        'grip_right', 'grip_left', 'weight_loss_delta', 'dehydration_index'
    ]

    def __init__(self):
        self.bucket_name = getattr(settings, 'GS_BUCKET_NAME', None)
        self.model = self.load_model()

    def _get_storage_client(self):
        """Hitelesített GCS kliens létrehozása a meglévő settings alapján."""
        if hasattr(settings, 'GS_CREDENTIALS') and settings.GS_CREDENTIALS:
            return storage.Client(credentials=settings.GS_CREDENTIALS, project=settings.GS_PROJECT_ID)
        
        # Ha nincs közvetlen credentials (pl. Production Cloud Run-on), próbálja az alapértelmezettet
        return storage.Client()

    def load_model(self):
        """Betölti a modellt: GCS -> Local /tmp -> Memory"""
        # 1. Ha nincs a /tmp-ben, próbáljuk letölteni a GCS-ről
        if not os.path.exists(self.LOCAL_MODEL_PATH):
            logger.info("🤖 Modell nem található a /tmp-ben, letöltés a GCS-ről...")
            self._download_from_gcs()

        # 2. Ha most már létezik a fájl, betöltjük
        if os.path.exists(self.LOCAL_MODEL_PATH):
            try:
                return joblib.load(self.LOCAL_MODEL_PATH)
            except Exception as e:
                logger.error(f"❌ Modell betöltése sikertelen: {e}")
        
        logger.warning("⚠️ Nem sikerült betölteni a modellt (még nem készült el).")
        return None

    def _download_from_gcs(self):
        """Modell letöltése a bödönből."""
        try:
            client = self._get_storage_client()
            bucket = client.bucket(self.bucket_name)
            blob = bucket.blob(self.GCS_MODEL_PATH)
            
            if blob.exists():
                blob.download_to_filename(self.LOCAL_MODEL_PATH)
                logger.info(f"✅ Modell sikeresen letöltve: gs://{self.bucket_name}/{self.GCS_MODEL_PATH}")
            else:
                logger.warning("⚠️ Modell nem létezik a GCS-en.")
        except Exception as e:
            logger.error(f"❌ Hiba a GCS letöltés során: {e}")

    def _upload_to_gcs(self):
        """Modell feltöltése a bödönbe."""
        try:
            client = self._get_storage_client()
            bucket = client.bucket(self.bucket_name)
            blob = bucket.blob(self.GCS_MODEL_PATH)
            blob.upload_from_filename(self.LOCAL_MODEL_PATH)
            logger.info(f"🚀 Modell feltöltve a GCS-re: gs://{self.bucket_name}/{self.GCS_MODEL_PATH}")
        except Exception as e:
            logger.error(f"❌ Hiba a GCS feltöltés során: {e}")

    def train_model(self):
        """A hibrid tanítási folyamat."""
        logger.info("🧠 Modell tanítása indul...")
        
        X, y = self._prepare_training_data()
        
        if X.empty or len(y) < 10:
            logger.error("❌ Nincs elég adat a tanításhoz.")
            return False

        # Tanítás
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X, y)

        # Mentés helyben
        joblib.dump(model, self.LOCAL_MODEL_PATH)
        
        # Feltöltés GCS-re
        self._upload_to_gcs()
        
        self.model = model
        return True

    def _prepare_training_data(self):
        """Valódi és szintetikus adatok összefésülése (a korábbi kódod alapján)."""
        # Itt marad a korábbi logikád a SyntheticDataGenerator-ral
        gen = SyntheticDataGenerator()
        df_synth = gen.generate_batch(count_per_category=2500)
        
        real_snapshots = UserFeatureSnapshot.objects.all()
        real_data = []
        for s in real_snapshots:
            feat = s.features
            if isinstance(feat, dict) and 'form_score' in feat:
                real_data.append(feat)
        
        df_real = pd.DataFrame(real_data)
        df_combined = pd.concat([df_synth, df_real], ignore_index=True)

        if 'category' in df_combined.columns:
            df_combined['category'] = df_combined['category'].map({
                'COMBAT': 0, 'STRENGTH': 1, 'ENDURANCE': 2, 'REHAB': 3
            }).fillna(0)

        y = df_combined['form_score']
        
        # 🔹 CSAK A FIX OSZLOPOKAT TARTJUK MEG ÉS SORBA RENDEZZÜK
        X = df_combined[self.FEATURE_COLUMNS].copy()
        X.columns = X.columns.astype(str)
        
        return X, y

    def predict_form(self, user):
        """Predikció végrehajtása egy adott felhasználóra."""
        if not self.model:
            self.model = self.load_model()
            if not self.model: return None, None

        try:
            latest_snapshot = UserFeatureSnapshot.objects.filter(user=user).order_by("-snapshot_date").first()
            if not latest_snapshot: return None, None
                
            features = latest_snapshot.features
            # Ha a features dict, listává tesszük a DataFrame-hez
            data_for_df = [features] if isinstance(features, dict) else features
            df_pred = pd.DataFrame(data_for_df)
            
            if 'category' in df_pred.columns:
                df_pred['category'] = df_pred['category'].map({
                    'COMBAT': 0, 'STRENGTH': 1, 'ENDURANCE': 2, 'REHAB': 3
                }).fillna(0)

            # 🔹 KÉNYSZERÍTJÜK UGYANAZT A SORRENDET, MINT A TANÍTÁSNÁL
            # Ha valami hiányzik a snapshotból, kitöltjük nullával
            for col in self.FEATURE_COLUMNS:
                if col not in df_pred.columns:
                    df_pred[col] = 0
            
            X_pred = df_pred[self.FEATURE_COLUMNS].copy()
            X_pred.columns = X_pred.columns.astype(str)

            prediction = self.model.predict(X_pred)[0]
            
            # AI Tanács (Ditta)
            try:
                coach = DittaCoachService()
                coach.generate_advice(user)
            except: pass

            return latest_snapshot.snapshot_date, float(prediction)

        except Exception as e:
            logger.error(f"❌ Predikciós hiba: {e}")
            return None, None