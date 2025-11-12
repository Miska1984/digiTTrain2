import logging
import numpy as np
from typing import List, Dict, Any
from decimal import Decimal
import numpy.linalg # 🆕 Import hozzáadva a np.linalg használatához

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

    
    def run_analysis(self):
        job = self.job
    
        self.log(f"▶️ Posture Assessment indítása job_id={job.id}") 
        video_path = get_local_video_path(job.video_url)

        try:
            # 0️⃣ Kalibráció és Antropometria betöltése
            anthro_profile_data = get_user_anthropometry_data(job.user)
            calibration_factor = float(anthro_profile_data.get("calibration_factor", 1.0))
            # leg_calibration_factor a jövőbeli láb-specifikus számításokhoz, de nem adjuk át a MediaPipe-nak
            leg_calibration_factor = float(anthro_profile_data.get("leg_calibration_factor", calibration_factor)) 
            self.log(f"Kalibrációs faktor használva: {calibration_factor:.4f} (Láb: {leg_calibration_factor:.4f})")

            # 📏 Szegmensméretek kinyerése
            segment_measurements_cm = {
                "trunk_height_cm": float(anthro_profile_data.get("trunk_height_cm", 0)),
                "shoulder_width_cm": float(anthro_profile_data.get("shoulder_width_cm", 0)),
                "pelvis_width_cm": float(anthro_profile_data.get("pelvis_width_cm", 0)),
            }

            # 1️⃣ Videó feldolgozása MediaPipe-pal 
            raw_keypoints, skeleton_video_path, keyframes = process_video_with_mediapipe(
                video_path, 
                job.job_type,
                # 🟢 KRITIKUS JAVÍTÁS: ELTÁVOLÍTVA a 'leg_calibration_factor', mert hibát okozott.
                calibration_factor=calibration_factor, 
            )
            self.log(f"MediaPipe feldolgozás kész, {len(raw_keypoints)} frame elemzve.")

            # 2️⃣ Elemzés lefuttatása
            analysis_result = self._analyze_posture_keypoints(
                raw_keypoints, 
                job, 
                calibration_factor,
                segment_measurements_cm # 👈 Átadjuk a szegmensméreteket
            )

            # Extra metaadatok hozzáadása
            analysis_result["video_analysis_done"] = True
            analysis_result["skeleton_video_local_path"] = skeleton_video_path

            # ✅ JSON SERIALIZÁCIÓS JAVÍTÁS (np.ndarray eltávolítása/konvertálása)
            cleaned_keyframes = []
            for frame in keyframes:
                cleaned_frame = frame.copy()
                
                if 'frame_image' in cleaned_frame:
                    del cleaned_frame['frame_image'] 
                    
                for k, v in cleaned_frame.items():
                    if isinstance(v, np.ndarray):
                        cleaned_frame[k] = v.tolist()
                        
                cleaned_keyframes.append(cleaned_frame)

            analysis_result["keyframes"] = cleaned_keyframes
            
            # 🟢 HIBÁNAK JAVÍTÁSA: 'anthro' helyett 'anthro_profile_data'-t használunk.
            analysis_result["calibration_used"] = bool(anthro_profile_data.get("calibration_factor")) 
            analysis_result["calibration_factor"] = round(calibration_factor, 5)

            # 🟢 ÚJ: Antropometriai adatok eltárolása az eredményben
            analysis_result["anthropometry"] = {
                "calibration_factor": calibration_factor,
                "leg_calibration_factor": leg_calibration_factor,
                "segment_measurements": segment_measurements_cm,
            }

            # 🆕 3️⃣ AZ EREDMÉNY MENTÉSE A GENERAL_RESULTS TÁBLÁBA 
            metrics = analysis_result.get('metrics', {})

            PostureAssessmentResult.objects.create(
                user=job.user,
                job=job,
                created_at=job.created_at,
                
                # A metrikák Decimal típusra konvertálása
                posture_score=Decimal(str(metrics.get('posture_score', 0.0))),
                avg_shoulder_tilt=Decimal(str(metrics.get('average_shoulder_tilt', 0.0))),
                avg_hip_tilt=Decimal(str(metrics.get('average_hip_tilt', 0.0))),
                # 🟢 ÚJ METRIKA
                # avg_ap_proxy=Decimal(str(metrics.get('average_ap_proxy', 0.0))),

                # Az összes elemzési adat mentése JSON-ként
                raw_json_metrics=analysis_result,
            )
            self.log(f"✅ Posture Assessment eredmény elmentve a general_results táblába job_id={job.id}")
            return analysis_result

        except Exception as e:
            self.log(f"❌ Posture Assessment hiba job_id={job.id}: {e}")
            # ⚠️ A job hibaüzenettel tér vissza, ha a MediaPipe feldolgozás sikertelen
            return {"error": f"Elemzés hiba: {e}", "video_analysis_done": False}

    
    # ------------------------------------------------------------------------------
    # 🧠 _analyze_posture_keypoints METÓDUS: AP Proxy és Lateral Shift implementáció
    # ------------------------------------------------------------------------------
    def _analyze_posture_keypoints(
        self, 
        raw_keypoints: List[Dict[str, Any]], 
        job, 
        calibration_factor: float,
        segment_measurements: Dict[str, float] # 👈 Antropometria
    ) -> Dict[str, Any]:
        """
        Kinyeri a váll-, csípő- dőlési, valamint a Sagittális és Laterális egyensúly adatokat.
        """
        shoulder_tilts, hip_tilts = [], []
        ap_proxies, lateral_shifts = [], []
        max_shoulder_tilt, max_hip_tilt = 0.0, 0.0
        max_ap_proxy, max_lateral_shift = 0.0, 0.0
        max_shoulder_frame, max_hip_frame = None, None

        for frame_data in raw_keypoints:
            # Kulcspontok kinyerése
            left_shoulder = get_landmark_coords(frame_data, 'left_shoulder')
            right_shoulder = get_landmark_coords(frame_data, 'right_shoulder')
            left_hip = get_landmark_coords(frame_data, 'left_hip')
            right_hip = get_landmark_coords(frame_data, 'right_hip')
            left_ankle = get_landmark_coords(frame_data, 'left_ankle')
            right_ankle = get_landmark_coords(frame_data, 'right_ankle')
            nose = get_landmark_coords(frame_data, 'nose')

            # 1️⃣ Laterális dőlés (Lateral Tilt)
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

            # 2️⃣ Sagittális és Laterális egyensúly (AP Proxy & Lateral Shift)
            if all(p is not None for p in [left_hip, right_hip, left_ankle, right_ankle, nose]):
                
                # Hip távolság (referenciahossz)
                hip_distance = np.linalg.norm(np.array(left_hip)[:2] - np.array(right_hip)[:2]) # X,Y sík
                mid_ankle = (np.array(left_ankle) + np.array(right_ankle)) / 2

                if hip_distance > 0:
                    
                    # 🟢 AP Proxy (Sagittális stabilitás - Fej előrehelyezkedés)
                    # Z tengely eltérés (mélység) a MediaPipe koordináta rendszerben
                    ap_offset = nose[2] - mid_ankle[2] 
                    ap_proxy = ap_offset / hip_distance
                    ap_proxies.append(ap_proxy)
                    
                    if abs(ap_proxy) > abs(max_ap_proxy):
                        max_ap_proxy = ap_proxy
                        
                    # 🟢 Laterális egyensúly (Lateral Shift - Súlypont eltérés)
                    # X tengely eltérés (oldalirány)
                    center_line_hip = (np.array(left_hip) + np.array(right_hip)) / 2
                    lateral_offset = center_line_hip[0] - mid_ankle[0] 
                    lateral_shift = abs(lateral_offset) / hip_distance
                    lateral_shifts.append(lateral_shift)
                    
                    if lateral_shift > max_lateral_shift:
                        max_lateral_shift = lateral_shift

        # Metrikák átlaga
        avg_shoulder_tilt = np.mean(np.abs(shoulder_tilts)) if shoulder_tilts else 0.0
        avg_hip_tilt = np.mean(np.abs(hip_tilts)) if hip_tilts else 0.0
        avg_ap_proxy = np.mean(ap_proxies) if ap_proxies else 0.0
        avg_lateral_shift = np.mean(lateral_shifts) if lateral_shifts else 0.0
        
        posture_score = max(0.0, 100.0 - ((avg_shoulder_tilt + avg_hip_tilt) / 2.0) * 5)
        
        feedback = [
            f"Testtartás pontszám: {posture_score:.1f}%",
            f"Átlagos válldőlés: {avg_shoulder_tilt:.1f}°",
            f"Átlagos csípődőlés: {avg_hip_tilt:.1f}°"
        ]
        
        # Kontextuális visszajelzés (Antropometrián alapulva)
        shoulder_width = segment_measurements.get("shoulder_width_cm")
        pelvis_width = segment_measurements.get("pelvis_width_cm")
        
        if shoulder_width and pelvis_width and pelvis_width > 0:
            shoulder_hip_ratio = shoulder_width / pelvis_width
            feedback.append(f"Antropometriai Váll/Csípő arány: {shoulder_hip_ratio:.2f}")

        # Visszajelzések AP Proxy alapján (Sagittális Stabilitás)
        if avg_ap_proxy > 0.4:
            feedback.append(f"❗ **Jelentős Sagittális Instabilitás:** Előrehelyezett fej/törzs tartás észlelhető (Átlagos AP Proxy: {avg_ap_proxy:.2f}).")
        elif avg_ap_proxy > 0.2:
            feedback.append(f"Enyhe Sagittális Instabilitás: Valószínűsíthető előrehelyezett tartás (Átlagos AP Proxy: {avg_ap_proxy:.2f}).")
        
        # Visszajelzések Laterális Shift alapján (Laterális Egyensúly)
        if avg_lateral_shift > 0.05:
            feedback.append(f"❗ **Jelentős Lateral Shift:** Súlypont eltolódás észlelhető, core kontroll fejlesztése javasolt (Átlagos Shift: {avg_lateral_shift:.3f}).")
        elif avg_lateral_shift > 0.02:
            feedback.append(f"Mérsékelt Lateral Shift: Figyelmet érdemlő oldalirányú súlypont eltérés (Átlagos Shift: {avg_lateral_shift:.3f}).")
            

        # A meglévő dőlési visszajelzések:
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
                # 🟢 ÚJ METRIKÁK
                "average_ap_proxy": float(round(avg_ap_proxy, 2)),
                "max_ap_proxy": float(round(max_ap_proxy, 2)),
                "average_lateral_shift": float(round(avg_lateral_shift, 3)),
                "max_lateral_shift": float(round(max_lateral_shift, 3)),
                "feedback": feedback,
            },
            "shoulder_snapshot_url": shoulder_snapshot_url,
            "hip_snapshot_url": hip_snapshot_url,
        }