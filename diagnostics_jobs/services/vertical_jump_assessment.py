import logging
import numpy as np
from typing import List, Dict, Any
from decimal import Decimal
import random # Szimulációhoz

# ❗ Importok frissítve a Vertical Jump elemzéshez
from diagnostics.utils.geometry import calculate_angle_3d, get_landmark_coords
from diagnostics.utils.mediapipe_processor import process_video_with_mediapipe
from diagnostics.utils.snapshot_manager import save_snapshot_to_gcs
from diagnostics_jobs.utils import get_local_video_path
from diagnostics_jobs.services.base_service import BaseDiagnosticService
# ❗ Kalibrációs modell betöltése a korábbi kérésnek megfelelően
from diagnostics_jobs.services.utils.anthropometry_loader import get_user_anthropometry_data 
# ❗ Feltételezve, hogy a GeneralResults.models-ben létezik a megfelelő modell
from general_results.models import VerticalJumpAssessmentResult 

logger = logging.getLogger(__name__)


def _calculate_valgus_angle_proxy(hip: np.ndarray, knee: np.ndarray, ankle: np.ndarray) -> float:
    """
    Knee Valgus szög proxy számítása.
    (A valós valgus mérés frontális síkot igényelne, itt a szimulációhoz helykitöltő.)
    """
    # A valós valgus mérés frontális síkban, 2D/3D projektálással történik.
    # Itt egy szimuláció zajlik a valgus szög tipikus tartományában.
    
    # ⚠️ FIGYELEM: A valós logikában ez helyettesítené a bonyolult CV modellt.
    return random.uniform(5.0, 15.0)


class VerticalJumpAssessmentService(BaseDiagnosticService):
    """
    Helyből Magassági Ugrás biomechanikai elemzése antropometriai skálázással.
    Méri a robbanékonyságot, a landolási kontrollt és a valgus kockázatot.
    """

    @classmethod
    def run_analysis(cls, job):
        cls.log(f"▶️ Vertical Jump Assessment indítása job_id={job.id}")
        video_path = get_local_video_path(job.video_url)

        try:
            # 0️⃣ Kalibráció betöltése
            anthro = get_user_anthropometry_data(job.user)
            # A loader függvény most már egy dictionary-t vagy None-t ad vissza.
            calibration_factor = anthro.get("calibration_factor", 1.0) if anthro else 1.0
            
            # ❗ KRITIKUS: Elemzés indítása Kalibráció hiányában
            if not anthro:
                error_msg = "❌ Kalibráció Hiba: A Helyből Magassági Ugrás elemzéshez antropometriai adatokra (Kalibrációra) van szükség!"
                cls.log(error_msg)
                job.mark_as_failed(error_msg)
                return {"error": error_msg, "video_analysis_done": False}
                
            cls.log(f"✅ Kalibrációs faktor betöltve: {calibration_factor:.4f}")

            # 1️⃣ Videó feldolgozása MediaPipe-pal
            raw_keypoints, skeleton_video_path, keyframes = process_video_with_mediapipe(
                video_path, 
                job.job_type,
                calibration_factor=calibration_factor, 
            )
            cls.log(f"MediaPipe feldolgozás kész, {len(raw_keypoints)} frame elemzve.")

            # 2️⃣ Elemzés
            analysis = cls._analyze_vertical_jump(raw_keypoints, job, calibration_factor)
            analysis["video_analysis_done"] = True
            analysis["skeleton_video_local_path"] = skeleton_video_path

            # -------------------------------------------------------------------
            # ✅ JSON-kompatibilis Keyframes lista előkészítése (a NumPy tömbök eltávolítása)
            # -------------------------------------------------------------------
            cleaned_keyframes = []
            for frame in keyframes:
                cleaned_frame = frame.copy()
                if 'frame_image' in cleaned_frame:
                    del cleaned_frame['frame_image'] 
                for k, v in cleaned_frame.items():
                    if isinstance(v, np.ndarray):
                        cleaned_frame[k] = v.tolist()

                cleaned_keyframes.append(cleaned_frame)

            analysis["keyframes"] = cleaned_keyframes 
            analysis["calibration_used"] = bool(anthro)
            analysis["calibration_factor"] = round(calibration_factor, 5)
            
            # 🆕 3️⃣ AZ EREDMÉNY MENTÉSE A GENERAL_RESULTS TÁBLÁBA ----------------
            
            VerticalJumpAssessmentResult.objects.create(
                user=job.user,
                job=job,
                created_at=job.created_at,
                
                # Konvertálás Decimal-ra (a jump metrikák mentése)
                overall_jump_score=Decimal(str(analysis.get('overall_jump_score', 0.0))),
                jump_height_cm=Decimal(str(analysis.get('jump_height_cm', 0.0))),
                max_valgus_angle=Decimal(str(analysis.get('max_valgus_angle', 0.0))), # Landolási kockázat
                
                raw_json_metrics=analysis,
            )
            cls.log(f"✅ Vertical Jump Assessment eredmény elmentve a general_results táblába job_id={job.id}")
            # --------------------------------------------------------------------------
            
            return analysis

        except Exception as e:
            cls.log(f"❌ Vertical Jump Assessment hiba job_id={job.id}: {e}")
            return {"error": f"Elemzés hiba: {e}", "video_analysis_done": False}

    @classmethod
    def _analyze_vertical_jump(cls, raw_keypoints: List[Dict[str, Any]], job, calibration_factor: float) -> Dict[str, Any]:
        """
        A Magassági Ugrás elemzés futtatása kalibrált testarányokkal.
        A számításokat szimuláljuk, de a struktúrát a dokumentum alapján adjuk vissza.
        """
        # Célok: Legnagyobb ugrásmagasság (z) és legnagyobb valgus szög (frontális sík) megtalálása
        
        # Iterálunk, de most a szimulált max/min értékeket keressük
        min_cm_knee_angle = 180.0
        max_valgus_angle = 0.0
        cm_frame = None
        valgus_frame = None
        
        # ⚠️ Valós logikában ez a rész felelne a mozgás fázisainak felismeréséért (CM, Takeoff, Flight, Landing)
        for frame_data in raw_keypoints:
            # Szimuláció: A valós életben a MediaPipe kulcspontokból számolnánk!
            
            # Keresés a legmélyebb Countermovement pontra (legkisebb térdszög)
            current_knee_angle = random.uniform(70, 140) 
            if current_knee_angle < min_cm_knee_angle:
                min_cm_knee_angle = current_knee_angle
                cm_frame = frame_data
                
            # Keresés a maximális valgus pontra (általában a landolási fázisban)
            current_valgus_angle = _calculate_valgus_angle_proxy(
                get_landmark_coords(frame_data, 'left_hip'), 
                get_landmark_coords(frame_data, 'left_knee'), 
                get_landmark_coords(frame_data, 'left_ankle')
            )
            if current_valgus_angle > max_valgus_angle:
                max_valgus_angle = current_valgus_angle
                valgus_frame = frame_data

        
        # ---------------------------------------------------------
        # 📊 VÉGSŐ PONTOZÁS ÉS EREDMÉNY SZIMULÁCIÓ (A dokumentum alapján)
        # ---------------------------------------------------------
        
        # 1. Alapmetrikák szimulációja
        jump_height_cm = random.uniform(25.0, 50.0)
        landing_control_score = random.uniform(65.0, 95.0) 
        jump_symmetry_score = random.uniform(85.0, 99.0)
        
        # 2. Összesített pontszám számítása a Word dokumentum szerint (40p+30p+20p+10p)
        # Egyszerűsített pontozás szimuláció
        
        # Erőkifejtés (Jump Height) 40p: 40 cm = 40p, 20 cm = 0p
        jump_score = max(0, min(40, (jump_height_cm - 20) * 2)) 
        
        # Valgus Kontroll 20p: 5 fok alatt 20p, 15 fok felett 0p
        valgus_points = max(0, 20 - (max_valgus_angle - 5) * 2) 
        
        overall_score = jump_score * 0.4 + landing_control_score * 0.3 + valgus_points * 0.2 + jump_symmetry_score * 0.1
        
        
        # 3. Visszajelzések generálása
        feedback = []
        if jump_height_cm < 30.0:
            feedback.append("Az ugrásmagasság (robbanékonyság) elmarad az optimálistól. Fókuszáljon az erőfejlesztésre.")
        if max_valgus_angle > 12.0:
            feedback.append(f"Túlzott Knee Valgus ({max_valgus_angle:.1f}°) figyelhető meg a landolásnál. Gluteus medius/maximus erősítése javasolt.")
        if landing_control_score < 75.0:
            feedback.append("A landolás merev és hangosnak tűnik. Javítani kell az excentrikus kontrollt (plyometria).")

        # 4. Snapshot generálás (A guggolás mintájára)
        landing_snapshot_url = save_snapshot_to_gcs(valgus_frame["frame_image"], job, "landing_valgus") if valgus_frame and "frame_image" in valgus_frame else None
        takeoff_snapshot_url = save_snapshot_to_gcs(cm_frame["frame_image"], job, "takeoff_cm") if cm_frame and "frame_image" in cm_frame else None

        
        # 5. Eredmény struktúra visszaadása
        return {
            "overall_jump_score": float(round(overall_score, 1)),
            "jump_height_cm": float(round(jump_height_cm, 1)),
            "countermovement_depth_deg": float(round(min_cm_knee_angle, 1)), # Ezt a PDF is használja
            "takeoff_speed_index": float(round(random.uniform(0.7, 0.95), 2)), # Szimuláció

            "max_valgus_angle": float(round(max_valgus_angle, 1)),
            "landing_control_score": float(round(landing_control_score, 1)),
            "jump_symmetry_score": float(round(jump_symmetry_score, 1)),
            
            "feedback": feedback,
            "snapshot_urls": { 
                # Ez a struktúra illeszkedik a vertical_jump_details.html sablonhoz
                "landing": landing_snapshot_url, 
                "takeoff": takeoff_snapshot_url, 
            }
        }