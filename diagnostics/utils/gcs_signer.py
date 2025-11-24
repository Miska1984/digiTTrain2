# diagnostics/utils/gcs_signer.py

import os
import logging
from google.cloud import storage
from google.auth import compute_engine
from datetime import timedelta
from django.conf import settings
from typing import Dict, Any

logger = logging.getLogger(__name__)

# ❗ KRITIKUS: A szolgáltatási fiók kulcsának elérési útja a settings-ből jön, egységesen
# Feltételezve, hogy a 'gcp_service_account.json' a BASE_DIR-ben van.
GCP_SA_KEY_PATH = os.path.join(settings.BASE_DIR, 'gcp_service_account.json')
GCS_BUCKET_NAME = settings.GS_BUCKET_NAME
CLOUD_RUN_SA_EMAIL = '195803356854-compute@developer.gserviceaccount.com'


def get_storage_client():
    """
    Visszaadja a Google Cloud Storage klienst.
    - PROD/ÉLES: Automatikusan használja a környezeti hitelesítést (ADC).
    - DEV/CODESPACE: Használja a helyi gcp_service_account.json kulcsfájlt.
    """
    # Ha a DEBUG=False ÉS az ENVIRONMENT='production', feltételezzük, hogy az ADC működik
    if not settings.DEBUG and settings.ENVIRONMENT == 'production':
        # Éles környezetben (Cloud Run) explicit Compute Engine Credentials-t használunk.
        logger.info("GCS kliens inicializálása: ÉLES/PRODUCTION mód (Compute Engine Auth)")
        
        # 🟢 VÉGLEGES JAVÍTÁS: Explicit hitelesítő adatok átadása
        credentials = compute_engine.Credentials()
        return storage.Client(credentials=credentials)
    else:
        # Fejlesztési környezetben (Codespace) a lokális fájlt használjuk
        if not GCP_SA_KEY_PATH or not os.path.exists(GCP_SA_KEY_PATH):
            logger.error(f"GCP_SA_KEY_PATH: {GCP_SA_KEY_PATH}")
            # Ezt a hibát a view-nak is el kell kapnia!
            raise FileNotFoundError(
                f"Hiányzik a GCP szolgáltatási fiók kulcsa a fejlesztői feltöltéshez: {GCP_SA_KEY_PATH}. "
                "Kérem, helyezze a 'gcp_service_account.json' fájlt a projekt gyökérkönyvtárába!"
            )
        # 🟢 JAVÍTOTT: A kliens a settings-ben megadott kulcsot használja
        logger.info("GCS kliens inicializálása: FEJLESZTÉS mód (service_account.json)")
        return storage.Client.from_service_account_json(GCP_SA_KEY_PATH)


def upload_file_and_make_public(local_file_path: str, gcs_destination_path: str) -> str | None:
    """
    Feltölt egy fájlt a GCS-re a megadott útvonalra és publikussá teszi.
    (Ezt a funkciót használja az anthropometry_assessment.py a skeleton videó feltöltéséhez)
    """
    if not local_file_path or not os.path.exists(local_file_path):
        logger.error(f"A lokális fájl nem létezik: {local_file_path}")
        return None
        
    try:
        # 1. GCS kliens inicializálása
        client = get_storage_client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(gcs_destination_path)
        
        # 2. Feltöltés
        blob.upload_from_filename(local_file_path)
        
        # 3. Nyilvánossá tétel
        blob.make_public()
        
        return blob.public_url
    except Exception as e:
        logger.error(f"❌ GCS publikus feltöltési hiba a {local_file_path} fájlnál (cél: {gcs_destination_path}): {e}")
        return None


def generate_signed_upload_url(file_name: str, content_type: str) -> dict:
    """
    Létrehoz egy aláírt URL-t a fájl közvetlen GCS-re való feltöltéséhez (PUT metódus).
    """
    try:
        # A kliens inicializálása ADC-vel (get_storage_client() PRODUCTION módban)
        client = get_storage_client() 
        if not client:
            logger.error("GCS kliens inicializálása sikertelen.")
            return {"success": False, "error": "GCS kliens hiba."}
            
        bucket = client.bucket(settings.GS_BUCKET_NAME) # Használja a settings-ből a vödröt
        blob_path = f"videos/uploads/{file_name}"
        blob = bucket.blob(blob_path)

        logger.info(f"Signing URL with SA: {CLOUD_RUN_SA_EMAIL}") # 💡 Új log! Ezzel ellenőrizzük, mi megy ki.

        # 🟢 KRITIKUS JAVÍTÁS: A service_account_email paraméter beállítása
        signed_url = blob.generate_signed_url(
            version="v4",
            method="PUT",
            expiration=timedelta(minutes=15),
            content_type=content_type,
            credentials=client._credentials,  # Compute Engine token
        )

        return {
            "success": True,
            "signed_url": signed_url,
            "file_name": blob_path, 
            "public_url": f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{blob_path}"
        }

    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"❌ Hiba az aláírt URL generálásakor: {e}")
        return {"success": False, "error": f"Hiba az aláírt URL generálásakor: {e}"}
    
    