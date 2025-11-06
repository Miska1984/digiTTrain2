# diagnostics/utils/snapshot_manager.py
import logging
import cv2
import os
from datetime import datetime
from django.conf import settings
# A google.cloud.storage importálása nem szükséges, ha a get_storage_client()-et használjuk
from diagnostics.utils.gcs_signer import get_storage_client 

logger = logging.getLogger(__name__)


def save_snapshot_to_gcs(frame_image, job, label="snapshot"):
    """
    Pillanatkép mentése GCS-re publikusan.

    :param frame_image: numpy array (OpenCV BGR formátum)
    :param job: DiagnosticJob objektum (job_id szükséges)
    :param label: snapshot címkéje (pl. "knee_angle", "hip_tilt")
    :return: A feltöltött fájl publikus URL-je vagy None
    """
    temp_path = None # Inicializálás a finally blokk biztonságáért
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 1. Fájlnév generálása
        filename = f"job_{job.id}_{label}_{timestamp}.jpg"
        
        # 2. Mentés a /tmp könyvtárba (NumPy array-ből JPG-be)
        if hasattr(frame_image, 'shape'):  # Ellenőrzés: numpy array?
            # 💡 KRITIKUS JAVÍTÁS: A temp_path meghatározása és a fájl kiírása
            temp_path = os.path.join("/tmp", filename)
            cv2.imwrite(temp_path, frame_image)
        else:
            logger.error("frame_image nem numpy array, snapshot mentés sikertelen.")
            return None

        # 3. GCS feltöltés a get_storage_client() segítségével
        client = get_storage_client() 
        bucket = client.bucket(settings.GS_BUCKET_NAME)
        
        # GCS célútvonal: jobs/<job_id>/snapshots/fájlnév.jpg
        gcs_destination = f"jobs/{job.id}/snapshots/{filename}"
        blob = bucket.blob(gcs_destination)
        
        # Feltöltés a lokális fájlból
        blob.upload_from_filename(temp_path)
        
        # Publikussá tétel
        blob.make_public() 
        
        snapshot_url = blob.public_url
        logger.info(f"✅ Snapshot feltöltve GCS-re: {snapshot_url}")
        return snapshot_url
        
    except Exception as e:
        # A GCS hitelesítési hibák is itt jelennek meg
        logger.error(f"❌ Snapshot GCS feltöltési hiba a {filename} fájlnál: {e}")
        return None
    finally:
        # 4. Lokális fájl törlése (még hiba esetén is)
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                logger.debug(f"Lokális átmeneti fájl törölve: {temp_path}")
            except Exception as remove_e:
                logger.warning(f"Nem sikerült törölni a lokális fájlt: {temp_path}. Hiba: {remove_e}")