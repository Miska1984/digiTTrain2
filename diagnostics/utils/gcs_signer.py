# diagnostics/utils/gcs_signer.py

import os
import logging
from google.cloud import storage
from google.auth import compute_engine
from datetime import timedelta
from django.conf import settings

logger = logging.getLogger(__name__)

# Alap beállítások
GCP_SA_KEY_PATH = os.getenv("GCP_SA_KEY_PATH", os.path.join(settings.BASE_DIR, "gcp_service_account.json"))
GCS_BUCKET_NAME = settings.GS_BUCKET_NAME
CLOUD_RUN_SA_EMAIL = "195803356854-compute@developer.gserviceaccount.com"


def get_storage_client():
    """
    Visszaadja a Google Cloud Storage klienst.
    - PROD/ÉLES: Ha van privát kulcs fájl, azzal inicializál.
    - Ha nincs, Compute Engine ADC-t használ.
    """
    if os.path.exists(GCP_SA_KEY_PATH):
        logger.info(f"🔐 GCS kliens inicializálása kulccsal: {GCP_SA_KEY_PATH}")
        return storage.Client.from_service_account_json(GCP_SA_KEY_PATH)
    else:
        logger.info("🟡 GCS kliens inicializálása ADC-vel (Compute Engine Auth)")
        credentials = compute_engine.Credentials()
        return storage.Client(credentials=credentials)


def upload_file_and_make_public(local_file_path: str, gcs_destination_path: str) -> str | None:
    """
    Feltölt egy fájlt a GCS-re és publikussá teszi.
    """
    if not local_file_path or not os.path.exists(local_file_path):
        logger.error(f"🚫 A lokális fájl nem létezik: {local_file_path}")
        return None

    try:
        client = get_storage_client()
        if not client:
            logger.error("❌ Nem sikerült GCS klienst inicializálni.")
            return None

        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(gcs_destination_path)

        blob.upload_from_filename(local_file_path)
        blob.make_public()

        public_url = blob.public_url
        logger.info(f"✅ Feltöltve és publikálva: {public_url}")
        return public_url

    except Exception as e:
        logger.error(f"❌ GCS feltöltési hiba ({local_file_path}) → {e}")
        return None


def generate_signed_upload_url(file_name: str, content_type: str) -> dict:
    """
    Létrehoz egy aláírt GCS feltöltési URL-t (PUT metódus).
    """
    try:
        client = get_storage_client()
        if not client:
            return {"success": False, "error": "GCS kliens inicializálása sikertelen."}

        bucket = client.bucket(settings.GS_BUCKET_NAME)
        blob_path = f"videos/uploads/{file_name}"
        blob = bucket.blob(blob_path)

        logger.info(f"🪶 Aláírás indítása fájlhoz: {blob_path}")

        signed_url = blob.generate_signed_url(
            version="v4",
            method="PUT",
            expiration=timedelta(minutes=15),
            content_type=content_type,
        )

        return {
            "success": True,
            "signed_url": signed_url,
            "file_name": blob_path,
            "public_url": f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{blob_path}",
        }

    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"❌ Hiba az aláírt URL generálásakor: {e}")
        return {"success": False, "error": str(e)}