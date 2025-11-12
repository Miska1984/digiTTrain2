import logging
import numpy as np
from typing import List, Dict, Any
from decimal import Decimal

from diagnostics.utils.geometry import calculate_angle_3d, get_landmark_coords
from diagnostics.utils.mediapipe_processor import process_video_with_mediapipe
from diagnostics.utils.snapshot_manager import save_snapshot_to_gcs
from diagnostics_jobs.utils import get_local_video_path
from diagnostics_jobs.services.base_service import BaseDiagnosticService
from diagnostics_jobs.services.utils.anthropometry_loader import get_user_anthropometry_data
from general_results.models import SquatAssessmentResult

logger = logging.getLogger(__name__)


def _calculate_trunk_lean(shoulder: np.ndarray, hip: np.ndarray) -> float:
    """Törzsdőlés szögének becslése (csípő és váll alapján)."""
    vertical_ref = np.array([hip[0], hip[1] + 100, hip[2]])
    angle = calculate_angle_3d(shoulder, hip, vertical_ref)
    return 180.0 - angle


class SquatAssessmentService(BaseDiagnosticService):
    """
    Guggolás biomechanikai elemzése antropometriai skálázással:
    térdszög, törzsdőlés, mozgáskontroll.
    """

    
    def run_analysis(self):
        job = self.job
        self.log(f"▶️ Squat Assessment indítása job_id={job.id}")
        video_path = get_local_video_path(job.video_url)

        try:
            # 0️⃣ Kalibráció betöltése
            anthro = get_user_anthropometry_data(job.user)
            general_factor = anthro.get("calibration_factor", 1.0) if anthro else 1.0
            leg_factor = anthro.get("leg_calibration_factor", 1.0) if anthro else 1.0
            self.log(f"Kalibrációs faktor (általános/videó): {general_factor:.4f}")
            self.log(f"Kalibrációs faktor (láb-specifikus/elemzés): {leg_factor:.4f}")

            # 1️⃣ Videó feldolgozása MediaPipe-pal
            raw_keypoints, skeleton_video_path, keyframes = process_video_with_mediapipe(
                video_path, 
                job.job_type,
                # 🟢 KRITIKUS JAVÍTÁS: Átadjuk a kalibrációs faktort
                calibration_factor=general_factor, 
            )
            self.log(f"MediaPipe feldolgozás kész, {len(raw_keypoints)} frame elemzve.")

            # 2️⃣ Elemzés
            analysis = self._analyze_squat(raw_keypoints, job, general_factor, leg_factor)
            analysis["video_analysis_done"] = True
            analysis["skeleton_video_local_path"] = skeleton_video_path

            # -------------------------------------------------------------------
            # ✅ KRITIKUS JAVÍTÁS: A keyframes listából eltávolítjuk a nagy (NumPy) képadatokat
            # -------------------------------------------------------------------
            cleaned_keyframes = []
            for frame in keyframes:
                # Másolat készítése és a nyers, nem JSON-kompatibilis képadat eltávolítása
                cleaned_frame = frame.copy()
                if 'frame_image' in cleaned_frame:
                    del cleaned_frame['frame_image'] 

                # Biztonsági konverzió: Minden megmaradt NumPy tömböt konvertálunk listává
                for k, v in cleaned_frame.items():
                    if isinstance(v, np.ndarray):
                        cleaned_frame[k] = v.tolist()

                cleaned_keyframes.append(cleaned_frame)

            analysis["keyframes"] = cleaned_keyframes # ⬅️ A TISZTÍTOTT LISTA!
            analysis["calibration_used"] = bool(anthro)
            analysis["general_calibration_factor"] = round(general_factor, 5)
            analysis["leg_calibration_factor"] = round(leg_factor, 5)
            
            # 🆕 3️⃣ AZ EREDMÉNY MENTÉSE A GENERAL_RESULTS TÁBLÁBA ----------------
            
            # Feltételezzük, hogy az 'overall_squat_score', 'min_knee_angle' és
            # 'max_trunk_lean' a fő 'analysis' dictionary-ben van.
            SquatAssessmentResult.objects.create(
                user=job.user,
                job=job,
                created_at=job.created_at,
                
                # Konvertálás Decimal-ra
                overall_squat_score=Decimal(str(analysis.get('overall_squat_score', 0.0))),
                min_knee_angle=Decimal(str(analysis.get('min_knee_angle', 0.0))),
                max_trunk_lean=Decimal(str(analysis.get('max_trunk_lean', 0.0))),

                raw_json_metrics=analysis,
            )
            self.log(f"✅ Squat Assessment eredmény elmentve a general_results táblába job_id={job.id}")
            # --------------------------------------------------------------------------
            
            return analysis

        except Exception as e:
            self.log(f"❌ Squat Assessment hiba job_id={job.id}: {e}")
            return {"error": f"Elemzés hiba: {e}", "video_analysis_done": False}

    def _analyze_squat(self, raw_keypoints: List[Dict[str, Any]], job, general_factor: float, leg_factor: float) -> Dict[str, Any]:
        """A tényleges guggolás-elemzés futtatása kalibrált testarányokkal."""
        import numpy as np
        
        min_knee_angle, max_trunk_lean = 180.0, 0.0
        min_angle_frame, max_trunk_frame = None, None

        # 🆕 KALIBRÁCIÓ KORREKCIÓS TÉNYEZŐ SZÁMÍTÁSA (CSAK EGYSZER!)
        # A raw_keypoints már F_general-lal van skálázva.
        # Korrekciós arány: F_leg / F_general.
        correction_factor = leg_factor / general_factor if general_factor and general_factor != 0 else leg_factor

        for frame_data in raw_keypoints:
            # Kulcspontok beolvasása (ezek F_general-lal skálázottak)
            left_hip = get_landmark_coords(frame_data, 'left_hip')
            left_knee = get_landmark_coords(frame_data, 'left_knee')
            left_ankle = get_landmark_coords(frame_data, 'left_ankle')
            right_hip = get_landmark_coords(frame_data, 'right_hip')
            right_knee = get_landmark_coords(frame_data, 'right_knee')
            right_ankle = get_landmark_coords(frame_data, 'right_ankle')
            left_shoulder = get_landmark_coords(frame_data, 'left_shoulder')
            right_shoulder = get_landmark_coords(frame_data, 'right_shoulder')

            # Alsótest pontok listája
            lower_body_coords = [left_hip, left_knee, left_ankle, right_hip, right_knee, right_ankle]

            # 🔹 ALSÓTEST SKÁLÁZÁSA (KORREKCIÓJA) valós méretre (F_leg)
            scaled_lower_body = []
            for p in lower_body_coords:
                if p is not None:
                    # Alkalmazzuk a korrekciós faktort (F_leg / F_general)
                    scaled_lower_body.append(np.array(p) * correction_factor)
                else:
                    scaled_lower_body.append(None)
            
            # Visszaadjuk a skálázott (korrigált) alsótest értékeket a változóknak
            [left_hip, left_knee, left_ankle, right_hip, right_knee, right_ankle] = scaled_lower_body

            # Térdszög számítás (innentől a hip/knee/ankle pontok már F_leg-gel vannak skálázva)
            if all(np.any(p) for p in [left_hip, left_knee, left_ankle]):
                left_knee_angle = calculate_angle_3d(left_hip, left_knee, left_ankle)
            else:
                left_knee_angle = 180.0

            if all(np.any(p) for p in [right_hip, right_knee, right_ankle]):
                right_knee_angle = calculate_angle_3d(right_hip, right_knee, right_ankle)
            else:
                right_knee_angle = 180.0

            current_knee_angle = (left_knee_angle + right_knee_angle) / 2.0
            if current_knee_angle < min_knee_angle:
                min_knee_angle, min_angle_frame = current_knee_angle, frame_data

            # Törzsdőlés (a vállak F_general-lal, a csípők F_leg-gel vannak skálázva, de a szög számítás stabil)
            if all(np.any(p) for p in [left_shoulder, right_shoulder, left_hip, right_hip]):
                mid_shoulder = (left_shoulder + right_shoulder) / 2.0
                mid_hip = (left_hip + right_hip) / 2.0
                current_trunk_lean = _calculate_trunk_lean(mid_shoulder, mid_hip)
            else:
                current_trunk_lean = 0.0

            if current_trunk_lean > max_trunk_lean:
                max_trunk_lean, max_trunk_frame = current_trunk_lean, frame_data

        # Pontozás (marad változatlan)
        ROM_optimal = 100.0
        ROM_error = abs(min_knee_angle - ROM_optimal)
        ROM_max_error = 80.0
        rom_score = max(0.0, 100.0 * (1 - ROM_error / ROM_max_error))

        Trunk_optimal = 10.0
        Trunk_error = max(0.0, max_trunk_lean - Trunk_optimal)
        trunk_score = max(0.0, 100 - Trunk_error * 4)

        control_score = 100.0
        overall_score = rom_score * 0.4 + trunk_score * 0.4 + control_score * 0.2

        feedback = []
        if min_knee_angle > 110:
            feedback.append(f"Guggolási mélység elmarad az optimálistól ({min_knee_angle:.1f}°).")
        if max_trunk_lean > 40:
            feedback.append(f"Túlzott törzsdőlés ({max_trunk_lean:.1f}°).")
        if overall_score < 70:
            feedback.append("A mozgáskontroll javítása javasolt a biztonságos guggolás érdekében.")

        knee_snapshot_url = save_snapshot_to_gcs(min_angle_frame["frame_image"], job, "knee_angle") if min_angle_frame and "frame_image" in min_angle_frame else None
        trunk_snapshot_url = save_snapshot_to_gcs(max_trunk_frame["frame_image"], job, "trunk_lean") if max_trunk_frame and "frame_image" in max_trunk_frame else None

        return {
            "overall_squat_score": float(round(overall_score, 1)),     
            "min_knee_angle": float(round(min_knee_angle, 1)),           
            "max_trunk_lean": float(round(max_trunk_lean, 1)),           
            "rom_score": float(round(rom_score, 1)),                     
            "trunk_score": float(round(trunk_score, 1)),                 
            "control_score": float(round(control_score, 1)),             
            "feedback": feedback,
            "knee_snapshot_url": knee_snapshot_url,
            "trunk_snapshot_url": trunk_snapshot_url,
        }