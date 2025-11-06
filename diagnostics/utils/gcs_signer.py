# diagnostics/utils/gcs_signer.py

import os
import logging
from google.cloud import storage
from datetime import timedelta
from django.conf import settings
from typing import Dict, Any

logger = logging.getLogger(__name__)

# ❗ KRITIKUS: A szolgáltatási fiók kulcsának elérési útja a settings-ből jön, egységesen
# Feltételezve, hogy a 'gcp_service_account.json' a BASE_DIR-ben van.
GCP_SA_KEY_PATH = os.path.join(settings.BASE_DIR, 'gcp_service_account.json')
GCS_BUCKET_NAME = settings.GS_BUCKET_NAME


def get_storage_client():
    """
    Visszaadja a Google Cloud Storage klienst.
    - PROD/ÉLES: Automatikusan használja a környezeti hitelesítést (ADC).
    - DEV/CODESPACE: Használja a helyi gcp_service_account.json kulcsfájlt.
    """
    # Ha a DEBUG=False ÉS az ENVIRONMENT='production', feltételezzük, hogy az ADC működik
    if not settings.DEBUG and settings.ENVIRONMENT == 'production':
        # Éles környezetben (Cloud Run/GAE) az ADC-t (környezeti hitelesítést) használjuk
        logger.info("GCS kliens inicializálása: ÉLES/PRODUCTION mód (ADC)")
        return storage.Client()
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
        client = get_storage_client()
        if not client:
             # Ez a kritikus pont. Ha a get_storage_client() nem tudott klienst inicializálni,
             # visszajelzést kell adnunk!
             logger.error("GCS kliens inicializálása sikertelen. Ellenőrizze a kulcsfájl elérhetőségét.")
             return {"success": False, "error": "GCS kliens hiba."}
        bucket = client.bucket(GCS_BUCKET_NAME)
        
        # Elérési út a videóknak a GCS-en
        blob_path = f"videos/uploads/{file_name}"
        blob = bucket.blob(blob_path)

        # Aláírt URL generálása (15 perc érvényességgel)
        signed_url = blob.generate_signed_url(
            version="v4",
            method="PUT",
            expiration=timedelta(minutes=15),
            content_type=content_type,
        )

        return {
            "success": True,
            "signed_url": signed_url,
            "file_name": blob_path, # Ezt az útvonalat mentjük az adatbázisba!
            "public_url": f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{blob_path}"
        }

    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"❌ Hiba az aláírt URL generálásakor: {e}")
        return {"success": False, "error": f"Hiba az aláírt URL generálásakor: {e}"}
    
    