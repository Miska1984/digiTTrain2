# diagnostics_jobs/services/anthropometry_calibration_service.py
import logging
import numpy as np
import os
import json
from datetime import datetime
from django.conf import settings
from google.cloud import storage
import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision
import cv2

from diagnostics_jobs.models import DiagnosticJob, UserAnthropometryProfile
from diagnostics.utils.geometry import get_landmark_coords
from diagnostics.utils.snapshot_manager import save_snapshot_to_gcs
from diagnostics_jobs.utils import get_local_image_path
from diagnostics_jobs.services.base_service import BaseDiagnosticService
from diagnostics.utils.mediapipe_processor import process_image_with_mediapipe


logger = logging.getLogger(__name__)

MODEL_PATH = '/app/assets/pose_landmarker_full.task'

# ===================================================================
# 🆕 KONSTANSOK: EMBERI TEST ARÁNYOK (validációhoz)
# ===================================================================
BODY_PROPORTIONS = {
    'head_to_total_height': (1/7.5, 1/7.0),  # Fej/Teljes magasság
    'shoulder_to_hip_ratio': (1.3, 1.6),     # Váll/csípő szélesség
    'upper_arm_to_forearm': (0.95, 1.15),    # Felkar/alkar arány
    'thigh_to_shin': (0.95, 1.15),           # Comb/lábszár arány
    'trunk_to_leg': (0.9, 1.1),              # Törzs/láb arány
}


# ===================================================================
# 📸 FOTÓMINŐSÉG VALIDÁCIÓ
# ===================================================================
def _validate_photo_quality(image_path: str, landmarks: dict) -> tuple[bool, list]:
    """
    Ellenőrzi a fotó minőségét és a landmark láthatóságot.
    Returns: (is_valid: bool, issues: list[str])
    """
    issues = []
    
    try:
        img = cv2.imread(image_path)
        if img is None:
            return False, ["Nem sikerült beolvasni a képet"]
        
        h, w = img.shape[:2]
        
        # 1️⃣ Felbontás ellenőrzés
        if w < 720 or h < 960:
            issues.append(f"⚠️ Alacsony felbontás: {w}x{h} (ajánlott min: 720x960)")
        
        # 2️⃣ Blur detekció
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        if laplacian_var < 100:
            issues.append(f"⚠️ Elmosódott kép (blur score: {laplacian_var:.1f}, min: 100)")
        
        # 3️⃣ Kritikus pontok láthatósága
        world_lms = landmarks.get('world_landmarks', [])
        critical_points = {
            'left_shoulder': 11, 'right_shoulder': 12,
            'left_hip': 23, 'right_hip': 24,
            'left_knee': 25, 'right_knee': 26,
            'left_ankle': 27, 'right_ankle': 28,
            'left_elbow': 13, 'right_elbow': 14,
            'left_wrist': 15, 'right_wrist': 16,
        }
        
        low_visibility = []
        for name, idx in critical_points.items():
            if idx < len(world_lms):
                lm = world_lms[idx]
                visibility = lm.get('v', 0.0)
                if visibility < 0.6:
                    low_visibility.append(f"{name}({visibility:.2f})")
        
        if low_visibility:
            issues.append(f"⚠️ Gyenge láthatóság: {', '.join(low_visibility)}")
        
        # 4️⃣ Póz ellenőrzés (egyenes testtartás)
        if len(world_lms) > max(critical_points.values()):
            l_shoulder = world_lms[11]
            r_shoulder = world_lms[12]
            
            shoulder_y_diff = abs(l_shoulder['y'] - r_shoulder['y'])
            if shoulder_y_diff > 0.05:  # 5cm-nél nagyobb eltérés
                issues.append(f"⚠️ Ferde testtartás - váll eltérés: {shoulder_y_diff*100:.1f}cm (max: 5cm)")
        
        return len(issues) == 0, issues
        
    except Exception as e:
        logger.error(f"❌ Fotó validációs hiba: {e}", exc_info=True)
        return False, [f"Validációs hiba: {e}"]


# ===================================================================
# 📥 GCS LETÖLTÉS
# ===================================================================
def _download_photo_for_processing(gcs_key: str) -> str:
    """Letölti a GCS objektumot a /tmp alá feldolgozáshoz."""
    if not gcs_key:
        raise ValueError("❌ Hiányzó GCS kulcs a képhez.")

    temp_path = f"/tmp/{os.path.basename(gcs_key)}_{datetime.now().microsecond}.jpg"

    try:
        client = storage.Client()
        bucket = client.bucket(settings.GS_BUCKET_NAME)
        blob = bucket.blob(gcs_key)
        if not blob.exists():
            raise FileNotFoundError(f"Nem található a fájl a GCS-en: {gcs_key}")

        blob.download_to_filename(temp_path)
        logger.info(f"✅ Kép letöltve: {temp_path}")
        return temp_path
    except Exception as e:
        logger.error(f"❌ GCS letöltési hiba: {e}", exc_info=True)
        raise RuntimeError(f"Nem sikerült letölteni a képet: {gcs_key}")


# ===================================================================
# 🔍 MEDIAPIPE FELDOLGOZÁS
# ===================================================================
def _process_static_image_for_landmarks(image_path: str) -> dict:
    """MediaPipe PoseLandmarker-rel világkoordinátás landmarkokat ad vissza."""
    base_opts = mp_tasks.BaseOptions(model_asset_path=MODEL_PATH)
    opts = vision.PoseLandmarkerOptions(
        base_options=base_opts,
        output_segmentation_masks=False,
        running_mode=vision.RunningMode.IMAGE
    )

    try:
        with vision.PoseLandmarker.create_from_options(opts) as landmarker:
            mp_image = mp.Image.create_from_file(image_path)
            result = landmarker.detect(mp_image)

            if not result.pose_world_landmarks:
                raise ValueError("MediaPipe nem talált emberi alakot a képen.")

            world_landmarks = [
                {
                    'id': i,
                    'x': lm.x,
                    'y': lm.y,
                    'z': lm.z,
                    'v': getattr(lm, 'visibility', 1.0)
                }
                for i, lm in enumerate(result.pose_world_landmarks[0])
            ]
            
            # 🆕 Normalized landmarks is (pixel koordinátákhoz)
            normalized_landmarks = []
            if result.pose_landmarks:
                normalized_landmarks = [
                    {'x': lm.x, 'y': lm.y, 'z': lm.z, 'v': getattr(lm, 'visibility', 1.0)}
                    for lm in result.pose_landmarks[0]
                ]
            
            return {
                'world_landmarks': world_landmarks,
                'normalized_landmarks': normalized_landmarks
            }

    except Exception as e:
        logger.error(f"❌ MediaPipe feldolgozási hiba: {e}", exc_info=True)
        raise RuntimeError(f"Nem sikerült a MediaPipe elemzés: {e}") from e


# ===================================================================
# 🎨 ANNOTÁLT KÉP GENERÁLÁS
# ===================================================================
def generate_annotated_calibration_image(
    front_image_path: str, 
    landmarks: dict, 
    segment_data: dict, 
    calibration_factor: float, 
    user_name: str,
    quality_issues: list,
    job: DiagnosticJob
) -> str:
    """Kirajzolja az antropometriai szegmenseket a képre és feltölti GCS-re."""
    import tempfile
    
    try:
        image = cv2.imread(front_image_path)
        if image is None:
            raise ValueError(f"A kép nem olvasható: {front_image_path}")

        annotated = image.copy()
        h, w = annotated.shape[:2]

        # Normalized landmarks használata pixel koordinátákhoz
        norm_lms = landmarks.get('normalized_landmarks', [])
        
        def get_lm_xy(idx: int):
            if idx >= len(norm_lms):
                return None
            lm = norm_lms[idx]
            x = int(lm['x'] * w)
            y = int(lm['y'] * h)
            return (x, y)

        # Szegmensvonalak (landmark indexekkel)
        pairs = [
            (11, 12, "shoulder_width"),      # Váll szélesség
            (23, 24, "pelvis_width"),        # Medence szélesség
            (11, 13, "left_upper_arm"),      # Bal felkar
            (13, 15, "left_forearm"),        # Bal alkar
            (12, 14, "right_upper_arm"),     # Jobb felkar
            (14, 16, "right_forearm"),       # Jobb alkar
            (23, 25, "left_thigh"),          # Bal comb
            (25, 27, "left_shin"),           # Bal lábszár
            (24, 26, "right_thigh"),         # Jobb comb
            (26, 28, "right_shin"),          # Jobb lábszár
            (11, 23, "trunk"),               # Törzs (bal oldal)
        ]

        color = (0, 255, 0)
        text_color = (0, 0, 255)
        confidence_color = (255, 165, 0)  # Narancssárga
        font = cv2.FONT_HERSHEY_SIMPLEX

        for p1_idx, p2_idx, seg_key in pairs:
            p1 = get_lm_xy(p1_idx)
            p2 = get_lm_xy(p2_idx)
            
            if p1 and p2:
                # Vonal rajzolás
                cv2.line(annotated, p1, p2, color, 3)
                
                # Középpont
                mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
                
                # Mérés és confidence
                seg_len = segment_data.get(seg_key, {}).get('length')
                confidence = segment_data.get(seg_key, {}).get('confidence', 0.0)
                
                if seg_len:
                    label = f"{seg_len:.1f}cm"
                    conf_label = f"({confidence:.0%})"
                    
                    cv2.putText(annotated, label, (mid[0]-20, mid[1]-10), 
                               font, 0.6, text_color, 2, cv2.LINE_AA)
                    cv2.putText(annotated, conf_label, (mid[0]-20, mid[1]+10), 
                               font, 0.4, confidence_color, 1, cv2.LINE_AA)

        # Header információk
        calib_value = job.calibration_factor if job.calibration_factor is not None else 0.0
        cv2.putText(annotated, f"Calibration: {calib_value:.4f}", (30, 40),
                   font, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
        
        # Minőségi figyelmeztetések
        if quality_issues:
            y_offset = 110
            cv2.putText(annotated, "Quality Warnings:", (30, y_offset),
                       font, 0.6, (0, 165, 255), 2, cv2.LINE_AA)
            for i, issue in enumerate(quality_issues[:3]):  # Max 3 warning
                y_offset += 30
                cv2.putText(annotated, f"- {issue[:50]}", (30, y_offset),
                           font, 0.5, (0, 165, 255), 1, cv2.LINE_AA)

        # GCS feltöltés
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        annotated_path = tmp_file.name
        cv2.imwrite(annotated_path, annotated, [cv2.IMWRITE_JPEG_QUALITY, 95])

        client = storage.Client()
        bucket = client.bucket(settings.GS_BUCKET_NAME)
        target_name = f"analysis_output/annotated_calibration_{user_name}_{int(datetime.now().timestamp())}.jpg"
        blob = bucket.blob(target_name)
        blob.upload_from_filename(annotated_path)
        
        os.remove(annotated_path)
        logger.info(f"✅ Annotált kép feltöltve: {blob.public_url}")
        return blob.public_url

    except Exception as e:
        logger.error(f"❌ Hiba az annotált kép generálásakor: {e}", exc_info=True)
        return None

# ===================================================================
# 🔧 EGYSZERŰ KÉPFELDOLGOZÓ FÜGGVÉNY (helyettesíti a hiányzó process_image_with_mediapipe-et)
# ===================================================================
def process_image_with_mediapipe(image_path: str) -> dict:
    """Egyetlen képen futtatja a MediaPipe PoseLandmarker-t."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Kép nem található: {image_path}")

    base_opts = mp_tasks.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.PoseLandmarkerOptions(
        base_options=base_opts,
        running_mode=vision.RunningMode.IMAGE,
        output_segmentation_masks=False,
    )

    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        mp_image = mp.Image.create_from_file(image_path)
        result = landmarker.detect(mp_image)

        if not result.pose_world_landmarks:
            raise ValueError("MediaPipe nem talált emberi alakot a képen.")

        world_landmarks = [
            {'x': lm.x, 'y': lm.y, 'z': lm.z, 'v': getattr(lm, 'visibility', 1.0)}
            for lm in result.pose_world_landmarks[0]
        ]
        image_landmarks = [
            {'x': lm.x, 'y': lm.y, 'z': lm.z, 'v': getattr(lm, 'visibility', 1.0)}
            for lm in result.pose_landmarks[0]
        ] if result.pose_landmarks else []

    return {'world_landmarks': world_landmarks, 'normalized_landmarks': image_landmarks}

# ===================================================================
# 🧮 ANTROPOMETRIA KALIBRÁCIÓ SERVICE
# ===================================================================
class AnthropometryCalibrationService(BaseDiagnosticService):
    """Két képből (szemből + oldalról) történő antropometriai kalibráció."""

    def __init__(self, job_id):
        self.job = DiagnosticJob.objects.get(id=job_id)
        self.front_landmarks = None
        self.side_landmarks = None

    def run_analysis(self, job: DiagnosticJob):
        try:
            logger.info(f"▶️ Antropometriai kalibráció indítása (job_id={job.id})")

            # ==========================================================
            # 1️⃣ Kép URL-ek biztonságos normalizálása
            # ==========================================================
            front_url = job.anthropometry_photo_url_front
            side_url = job.anthropometry_photo_url_side

            if front_url and not front_url.startswith("http"):
                front_url = f"{settings.MEDIA_URL}{front_url.lstrip('/')}"
            if side_url and not side_url.startswith("http"):
                side_url = f"{settings.MEDIA_URL}{side_url.lstrip('/')}"

            logger.info(f"🖼 FRONT URL: {front_url}")
            logger.info(f"🖼 SIDE URL:  {side_url}")

            # ==========================================================
            # 2️⃣ Lokális képek letöltése GCS-ről
            # ==========================================================
            front_path = get_local_image_path(front_url)
            side_path = get_local_image_path(side_url)
            logger.info(f"✅ Képek letöltve lokálisan: {front_path}, {side_path}")

            # ==========================================================
            # 3️⃣ MediaPipe feldolgozás
            # ==========================================================
            self.front_landmarks = process_image_with_mediapipe(front_path)
            self.side_landmarks = process_image_with_mediapipe(side_path)

            # ✅ Ellenőrzés: Sikerült-e detektálni a landmark-okat?
            if not self.front_landmarks or not self.front_landmarks.get("normalized_landmarks"):
                raise ValueError("❌ Nem sikerült detektálni a front fotón az emberi alakot!")
                
            if not self.side_landmarks or not self.side_landmarks.get("normalized_landmarks"):
                raise ValueError("❌ Nem sikerült detektálni a side fotón az emberi alakot!")

            logger.info(f"✅ Front: {len(self.front_landmarks['normalized_landmarks'])} landmark detektálva")
            logger.info(f"✅ Side: {len(self.side_landmarks['normalized_landmarks'])} landmark detektálva")

            # ==========================================================
            # 4️⃣ Kalibrációs faktor számítás
            # ==========================================================
            calibration_factor = self._calculate_calibration_factor(job.user_stated_height_m)
            leg_calibration_factor = self._calculate_leg_calibration_factor(
                job.user_stated_thigh_cm, job.user_stated_shin_cm
            )

            # ==========================================================
            # 5️⃣ Szegmensek mérése
            # ==========================================================
            measurements = self._calculate_all_segments(calibration_factor)

            # ==========================================================
            # 6️⃣ Annotált kép készítése
            # ==========================================================
            annotated_url = self._generate_annotated_image(front_path, measurements, job)
        
            if annotated_url:
                logger.info(f"✅ Annotált kép URL: {annotated_url}")
            else:
                logger.warning("⚠️ Annotált kép nem készült el")

            # ==========================================================
            # 7️⃣ Profil frissítése
            # ==========================================================
            self._update_user_profile(job.user, calibration_factor, leg_calibration_factor, measurements, annotated_url)

            
            # ==========================================================
            # 8️⃣ Job befejezése
            # ==========================================================
            job.calibration_factor = calibration_factor
            job.leg_calibration_factor = leg_calibration_factor
            
            # 🔹 RESULT JSON frissítése
            result_json = {
                "calibration_factor": calibration_factor,
                "leg_calibration_factor": leg_calibration_factor,
                "measurements": measurements,
                "annotated_image_url": annotated_url,
            }
            
            job.result = result_json
            job.status = DiagnosticJob.JobStatus.COMPLETED
            job.save()

            logger.info(f"✅ Antropometria kalibráció sikeres (faktor={calibration_factor:.4f})")
            return result_json

        except Exception as e:
            job.mark_as_failed(str(e))
            logger.error(f"❌ Kalibrációs hiba job_id={job.id}: {e}", exc_info=True)
            return {"error": str(e)}
        
    # =====================================================================
    # 🔹 Felhasználói profil frissítése (antropometriai eredmények mentése)
    # =====================================================================
    def _update_user_profile(self, user, calibration_factor, leg_calibration_factor, measurements, annotated_url):
        """
        Frissíti vagy létrehozza a UserAnthropometryProfile rekordot a felhasználónak.
        """
        try:
            profile, _ = UserAnthropometryProfile.objects.get_or_create(user=user)

            profile.calibration_factor = calibration_factor
            profile.leg_calibration_factor = leg_calibration_factor
            profile.measurements = measurements
            profile.annotated_image_url = annotated_url
            profile.last_updated = datetime.now()

            profile.save()
            logger.info(f"✅ Felhasználói antropometriai profil frissítve: user={user.id}")

        except Exception as e:
            logger.error(f"❌ Hiba a felhasználói profil frissítésekor: {e}", exc_info=True)

    # ===================================================================
    # 🔹 Kalibrációs faktor számítása
    # ===================================================================
    def _calculate_calibration_factor(self, user_height_m: float) -> float:
        try:
            lm = self.front_landmarks["world_landmarks"]
            head = np.array([lm[0]["x"], lm[0]["y"], lm[0]["z"]])
            ankle = np.array([lm[28]["x"], lm[28]["y"], lm[28]["z"]])
            mp_height = np.linalg.norm(head - ankle)
            if mp_height <= 0:
                raise ValueError("MediaPipe magasság nullás értékű.")
            factor = user_height_m / mp_height
            return round(factor, 5)
        except Exception as e:
            logger.warning(f"⚠️ Kalibrációs faktor számítási hiba: {e}")
            return 1.0
        
    def _calculate_leg_calibration_factor(self, user_thigh_cm: float, user_shin_cm: float) -> float:
        """
        Külön kalibrációs faktor számítása a láb szegmensekhez.
        """
        try:
            lm = self.front_landmarks["world_landmarks"]
            thigh_vec = np.array([lm[23]["x"], lm[23]["y"], lm[23]["z"]]) - np.array([lm[25]["x"], lm[25]["y"], lm[25]["z"]])
            shin_vec = np.array([lm[25]["x"], lm[25]["y"], lm[25]["z"]]) - np.array([lm[27]["x"], lm[27]["y"], lm[27]["z"]])

            mp_leg_length = np.linalg.norm(thigh_vec) + np.linalg.norm(shin_vec)
            if mp_leg_length <= 0:
                raise ValueError("MediaPipe lábhossz nullás értékű.")

            user_leg_length_m = (user_thigh_cm + user_shin_cm) / 100
            factor = user_leg_length_m / mp_leg_length
            return round(factor, 5)
        except Exception as e:
            logger.warning(f"⚠️ Láb kalibrációs faktor számítási hiba: {e}")
            return 1.0
        
    # ===================================================================
    # 🔹 Szegmensek kiszámítása
    # ===================================================================
    def _calculate_all_segments(self, calibration_factor: float) -> dict:
        segments_config = [
            (11, 23, "trunk"),
            (11, 12, "shoulder_width"),
            (23, 24, "pelvis_width"),
            (11, 13, "left_upper_arm"),
            (12, 14, "right_upper_arm"),
            (13, 15, "left_forearm"),
            (14, 16, "right_forearm"),
            (23, 25, "left_thigh"),
            (24, 26, "right_thigh"),
            (25, 27, "left_shin"),
            (26, 28, "right_shin"),
        ]

        measurements = {}
        for idx1, idx2, name in segments_config:
            if "thigh" in name or "shin" in name:
                result = self._calculate_segment_with_confidence_hybrid(
                    idx1, idx2, self.front_landmarks, self.side_landmarks, calibration_factor, name
                )
            else:
                result = self._calculate_segment_with_confidence(
                    idx1, idx2, self.front_landmarks, calibration_factor
                )
            measurements[name] = result
        return measurements

    # =====================================================================
    # 🔹 Normál szegmens számítás (egy képből)
    # =====================================================================
    def _calculate_segment_with_confidence(
        self, idx1: int, idx2: int, landmarks: dict,
        calibration_factor: float, min_visibility: float = 0.5
    ) -> dict:
        try:
            lms = landmarks.get("world_landmarks", [])
            if idx1 >= len(lms) or idx2 >= len(lms):
                return {"length": None, "confidence": 0.0, "valid": False}

            p1 = np.array([lms[idx1]["x"], lms[idx1]["y"], lms[idx1]["z"]])
            p2 = np.array([lms[idx2]["x"], lms[idx2]["y"], lms[idx2]["z"]])
            v = min(lms[idx1].get("v", 0.0), lms[idx2].get("v", 0.0))

            if v < min_visibility:
                return {"length": None, "confidence": v, "valid": False}

            dist = np.linalg.norm(p1 - p2)
            real_cm = dist * calibration_factor * 100

            return {"length": round(real_cm, 1), "confidence": round(v, 3), "valid": True}
        except Exception as e:
            logger.warning(f"⚠️ Szegmens számítási hiba: {e}")
            return {"length": None, "confidence": 0.0, "valid": False}

    # =====================================================================
    # 🔹 Hybrid (front + side) szegmens számítás
    # =====================================================================
    def _calculate_segment_with_confidence_hybrid(
        self,
        idx1: int,
        idx2: int,
        front_landmarks: dict,
        side_landmarks: dict,
        calibration_factor: float,
        segment_name: str,
        min_visibility: float = 0.5,
    ) -> dict:
        """
        Hybrid (front + side) szegmensmérés Z-torzítás korrekcióval.
        """
        try:
            front_lms = front_landmarks.get("world_landmarks", [])
            side_lms = side_landmarks.get("world_landmarks", [])

            if idx1 >= len(front_lms) or idx2 >= len(front_lms):
                return {"length": None, "confidence": 0.0, "valid": False}

            f1 = np.array([front_lms[idx1]["x"], front_lms[idx1]["y"], front_lms[idx1]["z"]])
            f2 = np.array([front_lms[idx2]["x"], front_lms[idx2]["y"], front_lms[idx2]["z"]])
            v_front = min(front_lms[idx1].get("v", 0.0), front_lms[idx2].get("v", 0.0))

            if idx1 < len(side_lms) and idx2 < len(side_lms):
                s1 = np.array([side_lms[idx1]["x"], side_lms[idx1]["y"], side_lms[idx1]["z"]])
                s2 = np.array([side_lms[idx2]["x"], side_lms[idx2]["y"], side_lms[idx2]["z"]])
                v_side = min(side_lms[idx1].get("v", 0.0), side_lms[idx2].get("v", 0.0))
            else:
                s1, s2, v_side = f1, f2, v_front

            confidence = round((v_front + v_side) / 2.0, 3)
            if confidence < min_visibility:
                return {"length": None, "confidence": confidence, "valid": False}

            dx = f1[0] - f2[0]
            dy = f1[1] - f2[1]
            dz = s1[2] - s2[2]
            z_corr = dz * 1.15 if "thigh" in segment_name or "shin" in segment_name else dz
            mp_dist = np.sqrt(dx**2 + dy**2 + z_corr**2)
            real_cm = mp_dist * calibration_factor * 100

            return {"length": round(real_cm, 1), "confidence": confidence, "valid": True}
        except Exception as e:
            logger.warning(f"⚠️ Hybrid szegmensmérés hiba [{segment_name}]: {e}")
            return {"length": None, "confidence": 0.0, "valid": False}

    # =====================================================================
    # 🔹 Annotált kép generálása
    # =====================================================================
    def _generate_annotated_image(self, img_path: str, measurements: dict, job: DiagnosticJob) -> str:
        """
        Annotált kép mentése GCS-re, ahol a mért szegmensek és hosszak is látszanak.
        """
        
        import tempfile
        from diagnostics.utils.gcs_signer import get_storage_client
        
        try:
            # 1️⃣ Kép beolvasása
            image = cv2.imread(img_path)
            if image is None:
                logger.error(f"❌ Nem sikerült beolvasni a képet: {img_path}")
                return None

            h, w = image.shape[:2]
            annotated = image.copy()

            # 2️⃣ Normalized landmarks lekérése
            norm_lms = self.front_landmarks.get('normalized_landmarks', [])
            
            if not norm_lms:
                logger.error("❌ Nincs normalized landmark a képhez!")
                return None
            
            logger.info(f"✅ {len(norm_lms)} normalized landmark elérhető az annotáláshoz")

            def get_lm_xy(idx: int):
                """Landmark pixel koordinátáinak lekérése."""
                if idx >= len(norm_lms):
                    return None
                lm = norm_lms[idx]
                x = int(lm['x'] * w)
                y = int(lm['y'] * h)
                return (x, y)

            # 3️⃣ Szegmensvonalak rajzolása
            pairs = [
                (11, 12, "shoulder_width"),
                (23, 24, "pelvis_width"),
                (11, 13, "left_upper_arm"),
                (13, 15, "left_forearm"),
                (12, 14, "right_upper_arm"),
                (14, 16, "right_forearm"),
                (23, 25, "left_thigh"),
                (25, 27, "left_shin"),
                (24, 26, "right_thigh"),
                (26, 28, "right_shin"),
                (11, 23, "trunk"),
            ]

            color = (0, 255, 0)
            text_color = (0, 0, 255)
            confidence_color = (255, 165, 0)
            font = cv2.FONT_HERSHEY_SIMPLEX

            for p1_idx, p2_idx, seg_key in pairs:
                p1 = get_lm_xy(p1_idx)
                p2 = get_lm_xy(p2_idx)
                
                if p1 and p2:
                    # Vonal rajzolás
                    cv2.line(annotated, p1, p2, color, 3)
                    
                    # Középpont
                    mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
                    
                    # Mérés és confidence
                    seg_data = measurements.get(seg_key, {})
                    seg_len = seg_data.get('length')
                    confidence = seg_data.get('confidence', 0.0)
                    
                    if seg_len:
                        label = f"{seg_len:.1f}cm"
                        conf_label = f"({confidence*100:.0f}%)"
                        
                        cv2.putText(annotated, label, (mid[0]-20, mid[1]-10), 
                                   font, 0.6, text_color, 2, cv2.LINE_AA)
                        cv2.putText(annotated, conf_label, (mid[0]-20, mid[1]+10), 
                                   font, 0.4, confidence_color, 1, cv2.LINE_AA)

            # 4️⃣ Header információk
            calib_value = job.calibration_factor if job.calibration_factor is not None else 0.0
            cv2.putText(annotated, f"Calibration: {calib_value:.4f}", (30, 40),
                        font, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(annotated, f"User: {job.user.username}", (30, 75),
                        font, 0.8, (255, 255, 255), 2, cv2.LINE_AA)

            # 5️⃣ Mentés /tmp-be
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            annotated_path = tmp_file.name
            success = cv2.imwrite(annotated_path, annotated, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            if not success:
                logger.error(f"❌ Nem sikerült menteni az annotált képet: {annotated_path}")
                return None
            
            logger.info(f"✅ Annotált kép mentve lokálisan: {annotated_path}")

            # 6️⃣ GCS feltöltés
            client = get_storage_client()
            bucket = client.bucket(settings.GS_BUCKET_NAME)
            target_name = f"analysis_output/annotated_calibration_{job.user.username}_{int(datetime.now().timestamp())}.jpg"
            blob = bucket.blob(target_name)
            blob.upload_from_filename(annotated_path)
            
            
            annotated_url = blob.public_url
            logger.info(f"✅ Annotált kép feltöltve GCS-re: {annotated_url}")
            
            # 7️⃣ Lokális fájl törlése
            os.remove(annotated_path)
            
            return annotated_url  # ← EZ FONTOS! GCS URL-t adunk vissza!

        except Exception as e:
            logger.error(f"❌ Hiba az annotált kép generálásakor: {e}", exc_info=True)
            return None