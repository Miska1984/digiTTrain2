import logging
import numpy as np
from typing import List, Dict, Any
from decimal import Decimal

from diagnostics.utils.geometry import calculate_horizontal_tilt, get_landmark_coords
from diagnostics.utils.mediapipe_processor import process_video_with_mediapipe
from diagnostics.utils.snapshot_manager import save_snapshot_to_gcs
from diagnostics_jobs.utils import get_local_video_path
from diagnostics_jobs.services.base_service import BaseDiagnosticService
from diagnostics_jobs.services.utils.anthropometry_loader import get_user_anthropometry_data 
from general_results.models import PostureAssessmentResult

logger = logging.getLogger(__name__)


class PostureAssessmentService(BaseDiagnosticService):
    """
    Testtartás (álló helyzet) kiegyensúlyozottságának és szimmetriájának vizsgálata,
    antropometriai kalibrációval skálázott koordináták alapján.
    """

    @classmethod
    def run_analysis(cls, job):
        cls.log(f"▶️ Posture Assessment indítása job_id={job.id}")
        video_path = get_local_video_path(job.video_url)

        try:
            # 0️⃣ Kalibráció betöltése
            anthro = get_user_anthropometry_data(job.user)
            calibration_factor = anthro["calibration_factor"] if anthro else 1.0
            cls.log(f"Kalibrációs faktor használva: {calibration_factor:.4f}")

            # 1️⃣ Videó feldolgozása MediaPipe-pal
            raw_keypoints, skeleton_video_path, keyframes = process_video_with_mediapipe(
                video_path, 
                job.job_type,
                # 🟢 KRITIKUS JAVÍTÁS: Átadjuk a kalibrációs faktort
                calibration_factor=calibration_factor, 
            )
            cls.log(f"MediaPipe feldolgozás kész, {len(raw_keypoints)} frame elemzve.")

            # 2️⃣ Elemzés lefuttatása
            analysis_result = cls._analyze_posture_keypoints(raw_keypoints, job, calibration_factor)

            # Extra metaadatok hozzáadása
            analysis_result["video_analysis_done"] = True
            analysis_result["skeleton_video_local_path"] = skeleton_video_path

            # -------------------------------------------------------------------
            # ✅ KRITIKUS JAVÍTÁS A JSON SERIALIZÁCIÓHOZ (sor 58 körül)
            # -------------------------------------------------------------------
            cleaned_keyframes = []
            for frame in keyframes:
                # Létrehozunk egy másolatot a keretadatokról
                cleaned_frame = frame.copy()
                
                # Eltávolítjuk a nyers képet (ami np.ndarray és hibát okoz), mivel már elmentettük a GCS-re.
                if 'frame_image' in cleaned_frame:
                    del cleaned_frame['frame_image'] 
                    
                # Általános konverzió: ha a frame-ben maradt még valamilyen rejtett ndarray, azt listává konvertáljuk.
                for k, v in cleaned_frame.items():
                    if isinstance(v, np.ndarray):
                        cleaned_frame[k] = v.tolist()
                        
                cleaned_keyframes.append(cleaned_frame)


            analysis_result["keyframes"] = cleaned_keyframes
            analysis_result["calibration_used"] = bool(anthro)
            analysis_result["calibration_factor"] = round(calibration_factor, 5)

            # 🆕 3️⃣ AZ EREDMÉNY MENTÉSE A GENERAL_RESULTS TÁBLÁBA ----------------
            metrics = analysis_result.get('metrics', {}) # A metrikák kinyerése

            PostureAssessmentResult.objects.create(
                user=job.user,
                job=job,
                created_at=job.created_at,
                
                # A metrikák Decimal típusra konvertálása stringen keresztül a precizitásért
                posture_score=Decimal(str(metrics.get('overall_posture_score', 0.0))),
                avg_shoulder_tilt=Decimal(str(metrics.get('average_shoulder_tilt', 0.0))),
                avg_hip_tilt=Decimal(str(metrics.get('average_hip_tilt', 0.0))),

                # Az összes elemzési adat mentése JSON-ként (további metrikákhoz)
                raw_json_metrics=analysis_result,
            )
            cls.log(f"✅ Posture Assessment eredmény elmentve a general_results táblába job_id={job.id}")
            # --------------------------------------------------------------------------
            return analysis_result

        except Exception as e:
            cls.log(f"❌ Posture Assessment hiba job_id={job.id}: {e}")
            return {"error": f"Elemzés hiba: {e}", "video_analysis_done": False}

    @classmethod
    def _analyze_posture_keypoints(cls, raw_keypoints: List[Dict[str, Any]], job, calibration_factor: float) -> Dict[str, Any]:
        """
        Kinyeri a váll- és csípődőlési adatokat a kulcspontokból, kalibrált testarányok szerint.
        """
        shoulder_tilts, hip_tilts = [], []
        max_shoulder_tilt, max_hip_tilt = 0.0, 0.0
        max_shoulder_frame, max_hip_frame = None, None

        for frame_data in raw_keypoints:
            # Kulcspontok kinyerése
            left_shoulder = get_landmark_coords(frame_data, 'left_shoulder')
            right_shoulder = get_landmark_coords(frame_data, 'right_shoulder')
            left_hip = get_landmark_coords(frame_data, 'left_hip')
            right_hip = get_landmark_coords(frame_data, 'right_hip')

            # 🧭 Skálázás valós méretre
            for p in [left_shoulder, right_shoulder, left_hip, right_hip]:
                if p is not None:
                    p = np.array(p) * calibration_factor

            if all(p is not None for p in [left_shoulder, right_shoulder]):
                shoulder_tilt = calculate_horizontal_tilt(left_shoulder, right_shoulder)
                shoulder_tilts.append(shoulder_tilt)
                if abs(shoulder_tilt) > abs(max_shoulder_tilt):
                    max_shoulder_tilt, max_shoulder_frame = shoulder_tilt, frame_data

            if all(p is not None for p in [left_hip, right_hip]):
                hip_tilt = calculate_horizontal_tilt(left_hip, right_hip)
                hip_tilts.append(hip_tilt)
                if abs(hip_tilt) > abs(max_hip_tilt):
                    max_hip_tilt, max_hip_frame = hip_tilt, frame_data

        # Metrikák
        avg_shoulder_tilt = np.mean(np.abs(shoulder_tilts)) if shoulder_tilts else 0.0
        avg_hip_tilt = np.mean(np.abs(hip_tilts)) if hip_tilts else 0.0
        posture_score = max(0.0, 100.0 - ((avg_shoulder_tilt + avg_hip_tilt) / 2.0) * 5)

        feedback = [
            f"Testtartás pontszám: {posture_score:.1f}%",
            f"Átlagos válldőlés: {avg_shoulder_tilt:.1f}°",
            f"Átlagos csípődőlés: {avg_hip_tilt:.1f}°"
        ]

        if avg_shoulder_tilt > 5:
            feedback.append("Magas válldőlés észlelhető.")
        if avg_hip_tilt > 5:
            feedback.append("Csípőferdeség észlelhető.")
        if posture_score > 85:
            feedback.append("Nagyon jó testtartás és szimmetria!")
        elif posture_score > 70:
            feedback.append("Átlagos testtartás, kisebb aszimmetria észlelhető.")
        else:
            feedback.append("Javasolt a törzs és váll mobilitásának fejlesztése.")

        # Snapshotok
        shoulder_snapshot_url, hip_snapshot_url = None, None
        if max_shoulder_frame and "frame_image" in max_shoulder_frame:
            shoulder_snapshot_url = save_snapshot_to_gcs(max_shoulder_frame["frame_image"], job, "shoulder_tilt")
        if max_hip_frame and "frame_image" in max_hip_frame:
            hip_snapshot_url = save_snapshot_to_gcs(max_hip_frame["frame_image"], job, "hip_tilt")

        return {
            "metrics": {
                "average_shoulder_tilt": float(round(avg_shoulder_tilt, 1)), 
                "average_hip_tilt": float(round(avg_hip_tilt, 1)),          
                "max_shoulder_tilt": float(round(max_shoulder_tilt, 1)),    
                "max_hip_tilt": float(round(max_hip_tilt, 1)),              
                "posture_score": float(round(posture_score, 1)),            
                "feedback": feedback,
            },
            "shoulder_snapshot_url": shoulder_snapshot_url,
            "hip_snapshot_url": hip_snapshot_url,
        }