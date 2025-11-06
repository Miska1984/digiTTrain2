# diagnostics_jobs/utils.py

import os
import cv2
import json
import logging
import requests 
import re
from urllib.parse import urlparse
from django.conf import settings
from django.core.files.storage import default_storage
# A MediaPipe importok maradnak az analyze_video_with_mediapipe-hoz
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe import solutions
from mediapipe.framework.formats import landmark_pb2

logger = logging.getLogger(__name__)
# 💡 GCS URL minta. A ([^/]+) a bucket neve, az (.+) a fájl elérési útja!
GCS_URL_PATTERN = r"https://storage\.googleapis\.com/[^/]+/(.+)"

# --- BIZTONSÁGOS FÁJL ELÉRÉS KONVERTÁLÁSA ---
def get_local_video_path(job_url: str) -> str:
    """
    Kinyeri a videó letöltéséhez szükséges lokális elérési utat.
    """
    
    gcs_object_path = None
    full_download_url = job_url # Alapértelmezésben a Job URL-t használjuk

    # 1. Próba: Hagyományos MEDIA_URL alapú konverzió (lokális fejlesztéshez)
    if job_url.startswith(settings.MEDIA_URL) and not 'storage.googleapis.com' in settings.MEDIA_URL:
        # Lokális útvonal kiszámítása (ha a DevelopmentMediaStorage-ot FileSystemStorage-ként használjuk)
        relative_path = job_url[len(settings.MEDIA_URL):]
        local_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        logger.info(f"💾 Fájl betöltése MEDIA_ROOT-ból: {local_path}")
        return local_path

    # 2. Próba: GCS URL-ből való kinyerés
    if 'storage.googleapis.com' in job_url:
        match = re.search(GCS_URL_PATTERN, job_url)
        if match:
            # gcs_object_path: Pl. 'media/dev/videos/uploads/...'
            gcs_object_path = match.group(1) 
            # A full_download_url már be van állítva fent: full_download_url = job_url
        else:
            logger.error(f"❌ Nem sikerült kinyerni a GCS objektum útvonalát: {job_url}")
            raise RuntimeError(f"Hibás GCS URL formátum: {job_url}")

    # 3. GCS-ből való letöltés (requests-szel a prefix hiba elkerülése érdekében)
    if 'storage.googleapis.com' in full_download_url:
        # Ideiglenes fájl a /tmp könyvtárban
        local_temp_path = os.path.join("/tmp", os.path.basename(gcs_object_path or "temp_video.mp4"))

        try:
            logger.info(f"⬇️ Fájl letöltése GCS-ről (Requests-szel): {full_download_url}")

            # Használjuk a requests-et, hogy megkerüljük a DevelopmentMediaStorage prefixelési hibáját
            response = requests.get(full_download_url, stream=True)
            response.raise_for_status() # Hiba esetén exception

            with open(local_temp_path, 'wb') as local_file:
                # Letöltés és mentés a /tmp-be chunk-onként
                for chunk in response.iter_content(chunk_size=8192):
                    local_file.write(chunk)
            
            logger.info(f"✅ Fájl letöltve a /tmp-be: {local_temp_path}")
            return local_temp_path

        except Exception as e:
            logger.critical(f"❌ Kritikus hiba a GCS letöltéskor (Requests-szel, {full_download_url}): {e}")
            raise RuntimeError(f"Nem sikerült letölteni a videót a feldolgozáshoz: {e}")

    # 4. Ha sem a MEDIA_URL, sem a GCS URL nem illik rá
    raise RuntimeError(f"Érvénytelen videó URL formátum: {job_url}")

def get_local_image_path(image_url: str) -> str:
    """
    Letölti vagy előkészíti a képet (JPG/PNG) a feldolgozáshoz.
    A működés megegyezik a get_local_video_path()-éval, csak képekhez optimalizálva.
    """
    import re
    import requests
    import os

    if not image_url:
        raise ValueError("❌ Nincs megadva kép URL.")

    gcs_object_path = None
    full_download_url = image_url

    # 1️⃣ Lokális fejlesztési környezet (MEDIA_URL)
    if image_url.startswith(settings.MEDIA_URL) and not "storage.googleapis.com" in settings.MEDIA_URL:
        relative_path = image_url[len(settings.MEDIA_URL):]
        local_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        logger.info(f"🖼️ Lokális kép betöltve: {local_path}")
        return local_path

    # 2️⃣ GCS formátumú URL kezelése
    if "storage.googleapis.com" in image_url:
        # Biztonságos regex minta
        GCS_URL_PATTERN = r"https://storage\.googleapis\.com/[^/]+/(.+)"
        match = re.search(GCS_URL_PATTERN, image_url)
        if match:
            gcs_object_path = match.group(1)
        else:
            logger.error(f"❌ Nem sikerült kinyerni a GCS objektum elérési útját: {image_url}")
            raise RuntimeError(f"Hibás GCS URL formátum: {image_url}")

        # Lokális ideiglenes fájl a /tmp alá
        local_temp_path = os.path.join("/tmp", os.path.basename(gcs_object_path or "temp_image.jpg"))

        try:
            # Ha a kép URL-je nem publikus vagy 404-et ad, próbáljuk meg a storage klienssel is
            logger.info(f"⬇️ Kép letöltése GCS-ről: {full_download_url}")
            response = requests.get(full_download_url, stream=True)
            response.raise_for_status()

            with open(local_temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"✅ Kép letöltve: {local_temp_path}")
            return local_temp_path

        except requests.exceptions.HTTPError as e:
            # 404 vagy 403 esetén fallback a GCS API kliensre
            logger.warning(f"⚠️ HTTP hiba a letöltéskor ({e}). Fallback GCS API kliensre.")
            try:
                from google.cloud import storage
                client = storage.Client()
                bucket_name = settings.GS_BUCKET_NAME
                bucket = client.bucket(bucket_name)

                # A GCS prefixeket (pl. "media/dev/") levágjuk
                object_name = gcs_object_path.replace("media/dev/", "").replace("media/", "")
                blob = bucket.blob(object_name)
                blob.download_to_filename(local_temp_path)

                logger.info(f"✅ GCS API-val letöltve: {local_temp_path}")
                return local_temp_path

            except Exception as e2:
                logger.critical(f"❌ GCS API letöltési hiba: {e2}")
                raise RuntimeError(f"Nem sikerült letölteni a képet GCS API-n keresztül: {e2}") from e

        except Exception as e:
            logger.critical(f"❌ Kritikus hiba a kép letöltésekor: {e}")
            raise RuntimeError(f"Nem sikerült letölteni a képet: {e}")

    # 3️⃣ Ha sem a MEDIA_URL, sem a GCS URL nem illik rá
    raise RuntimeError(f"Érvénytelen kép URL formátum: {image_url}")

# ----------------------------------------------------------------------------------
# A analyze_video_with_mediapipe függvény változatlanul jó, a kódfejlesztéshez
# szükséges lépéseket és a MediaPipe logikát tartalmazza.
# ----------------------------------------------------------------------------------

# --- VIDEÓ FELDOLGOZÓ FÜGGVÉNY ---
def analyze_video_with_mediapipe(video_path: str, output_dir: str) -> dict:
    """
    MediaPipe Pose Estimator futtatása a videón.
    Kinyeri a kulcspontokat, menti a JSON-t és visszaad egy egyszerűsített eredményt.
    """
    
    # Ellenőrzés
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Videó nem található a helyi elérési úton: {video_path}")
    
    os.makedirs(output_dir, exist_ok=True)
    
    BaseOptions = python.BaseOptions
    PoseLandmarker = vision.PoseLandmarker
    PoseLandmarkerOptions = vision.PoseLandmarkerOptions
    VisionRunningMode = vision.RunningMode
    
    # 📝 Konfiguráció: 
    # Változtasd meg a "pose_landmarker.task" elérési útvonalát, 
    # hogy megfeleljen a Docker image-ben lévő elérési útnak!
    MODEL_PATH = os.environ.get("MEDIAPIPE_MODEL_PATH", "/app/models/pose_landmarker.task")
    
    # Inicializálás
    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=VisionRunningMode.VIDEO,
        output_segmentation_masks=False,
    )

    # 🎥 Videó feldolgozás
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Nem sikerült megnyitni a videót: {video_path}")
        
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    all_keypoints = []

    with PoseLandmarker.create_from_options(options) as landmarker:
        frame_number = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Kép konvertálása MediaPipe formátumba
            mp_image = (
                solutions.base_options.Image(image_format=solutions.base_options.ImageFormat.SRGB, data=frame)
            )

            # Elemzés
            # A frame időbélyegét (ms) adjuk meg
            timestamp_ms = int(frame_number * 1000 / fps)
            result = landmarker.detect_for_video(mp_image, timestamp_ms)
            
            # Kulcspontok mentése
            if result.pose_landmarks:
                # Egyszerűsített JSON formátum a DiagnosticJob.result mezőhöz
                keypoints = []
                for landmark in result.pose_landmarks[0]:
                    keypoints.append({
                        'x': landmark.x, 
                        'y': landmark.y, 
                        'z': landmark.z, 
                        'v': landmark.visibility
                    })
                all_keypoints.append({
                    'frame': frame_number,
                    'time_ms': timestamp_ms,
                    'keypoints': keypoints
                })
            
            frame_number += 1
        
        cap.release()

    # 💾 Eredmény JSON fájl mentése
    json_path = os.path.join(output_dir, "analysis_raw_keypoints.json")
    with open(json_path, 'w') as f:
        json.dump(all_keypoints, f, indent=4)

    # 📊 Egyszerűsített, mock eredmény visszaadása
    # Ezt fogjuk a job.result mezőbe menteni, és ez kerül majd a PDF-be
    # Később a MediaPipe keypoints alapján számolhatsz itt metrikákat
    return {
        "status": "success",
        "frames_analyzed": frame_number,
        "raw_json_file": json_path.replace(settings.MEDIA_ROOT, settings.MEDIA_URL), # URL-t adunk vissza
        "overall_rating": "Jó",
        "shoulder_angle": 15.2, # Mock érték
        "hip_symmetry": 98.5, # Mock érték
    }