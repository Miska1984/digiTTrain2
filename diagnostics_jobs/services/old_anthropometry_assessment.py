import logging
import numpy as np
import os # 🆕 ÚJ: Szükséges a lokális skeleton videó törléséhez a feltöltés után
from typing import Dict, Any, List

# A szükséges importok
from diagnostics.utils.mediapipe_processor import process_video_with_mediapipe
from diagnostics.utils.snapshot_manager import save_snapshot_to_gcs 
from diagnostics_jobs.utils import get_local_video_path
from diagnostics_jobs.services.base_service import BaseDiagnosticService
from diagnostics_jobs.models import UserAnthropometryProfile
# 🆕 ÚJ: Importáljuk a get_landmark_coords-ot a geometria segédfájlból
from diagnostics.utils.geometry import get_landmark_coords 
# 🆕 ÚJ: Importáljuk a publikus feltöltő funkciót
from diagnostics.utils.gcs_signer import upload_file_and_make_public 

logger = logging.getLogger(__name__)

# --- Segédfüggvények a magasság becsléséhez és annotációhoz ---

def _estimate_height_and_annotate(keypoints_data: Dict[str, Any], job, known_height: float = None) -> Dict[str, Any]:
    """
    Becsüli a felhasználó magasságát és egy feliratozott képet ment a GCS-re.
    """
    
    keypoints = keypoints_data['frames']
    
    # 1. Keresd meg a legstabilabb frame-et a keypoints_data-ban
    if not keypoints:
        logger.warning("Nincs elemzett képkocka (keyframes) a becsléshez.")
        estimated_height_cm = None
        frame_data = {}
    else:
        # A példa kedvéért a videó középső képkockáját használjuk.
        mid_frame_index = len(keypoints) // 2
        frame_data = keypoints[mid_frame_index]
    
        # 2. Becslési logika (PLACEHOLDER + KALIBRÁCIÓ)
        # 💡 Mivel a MediaPipe 3D adatai natív egységekben vannak (méterben), 
        # a becslést egyszerűen a legmagasabb (NOSE) és legalacsonyabb (ANKLE/HEEL) 
        # Y pontok távolsága adja a 3D (world_landmarks) adatokban.
        
        # Keressük meg a középső frame 3D pontjait
        world_landmarks = frame_data.get('world_landmarks', [])
        
        # Kinyerjük a pontokat
        nose_coords = get_landmark_coords(world_landmarks, 'nose')
        left_heel_coords = get_landmark_coords(world_landmarks, 'left_heel')
        right_heel_coords = get_landmark_coords(world_landmarks, 'right_heel')
        
        # Ideális esetben mindkét sarok megvan
        heel_coords = (left_heel_coords + right_heel_coords) / 2 if (left_heel_coords is not None and right_heel_coords is not None) else left_heel_coords if left_heel_coords is not None else right_heel_coords
        
        raw_estimate_m = 0.0
        if nose_coords is not None and heel_coords is not None:
            # 3D távolság (Y-tengely mentén) méterben (ez az alapértelmezett egység)
            # A magasság a NOSE legmagasabb Y pontja és a HEEL legalacsonyabb Y pontja közötti távolság.
            raw_estimate_m = abs(nose_coords[1] - heel_coords[1])
        
        raw_estimate = raw_estimate_m * 100.0 # Átszámolás cm-re
        
        # ❌ PLACEHOLDER helyettesítése az 175.0-val, ha a becslés nulla.
        if raw_estimate == 0.0:
            raw_estimate = 175.0 
        
        estimated_height_cm = raw_estimate
        
        if known_height and known_height > 100:
            logger.info(f"🔎 Kalibráció indítása ismert magassággal: {known_height} cm. Nyers becslés: {raw_estimate:.1f} cm.")
            estimated_height_cm = (known_height * 0.8) + (raw_estimate * 0.2)
        
        estimated_height_cm = round(estimated_height_cm, 1) if estimated_height_cm is not None else None


    # 3. Kép feliratozása (Annotáció)
    annotated_image_url = None
    if "frame_image" in frame_data:
        frame_image = frame_data["frame_image"]
        
        # A save_snapshot_to_gcs a 2. lépésben javasolt javításokkal publikus URL-t ad vissza.
        annotated_image_url = save_snapshot_to_gcs(
            frame_image, 
            job, 
            "anthropometry_snapshot_annotated",
        )
        
    # 4. Antropometriai metrikák számítása
    anthropometry_metrics = _calculate_anthropometry_metrics(
        frame_data, 
        estimated_height_cm
    )
    
    # 5. Eredmény dict összeállítása
    return {
        "estimated_height_cm": estimated_height_cm,
        "annotated_snapshot_url": annotated_image_url,
        "video_analysis_done": True,
        # 💡 ÚJ: Metrikák hozzáadása az összevont dict-hez
        **anthropometry_metrics 
    }

# --- ÚJ SEGÉDFÜGGVÉNY A METRIKÁK SZÁMÍTÁSÁRA ---

def _calculate_anthropometry_metrics(frame_data: Dict[str, Any], calibrated_height_cm: float) -> Dict[str, Any]:
    """
    Kiszámolja a vállszélességet, csípőszélességet és karhosszúságot a 3D adatokból.
    
    A kalibrációs tényező a magasságra vonatkozó kalibrációs arány.
    """
    
    if not frame_data or not calibrated_height_cm or calibrated_height_cm <= 0:
        return {
            "shoulder_width_cm": None, 
            "hip_width_cm": None,
            "arm_length_cm": None,
        }

    world_landmarks = frame_data.get('world_landmarks', [])
    
    # 1. Kinyerjük a 3D pontokat (numpy tömbként)
    left_shoulder = get_landmark_coords(world_landmarks, 'left_shoulder')
    right_shoulder = get_landmark_coords(world_landmarks, 'right_shoulder')
    left_hip = get_landmark_coords(world_landmarks, 'left_hip')
    right_hip = get_landmark_coords(world_landmarks, 'right_hip')
    
    # A karhosszhoz (váll-csukló távolság)
    left_wrist = get_landmark_coords(world_landmarks, 'left_wrist')
    
    # A MediaPipe 3D koordináták már méterben vannak, így közvetlenül használhatóak.

    # Ez a távolság adja a vállszélességet méterben.
    shoulder_width_m = np.linalg.norm(left_shoulder - right_shoulder) if (left_shoulder is not None and right_shoulder is not None) else 0
    hip_width_m = np.linalg.norm(left_hip - right_hip) if (left_hip is not None and right_hip is not None) else 0
    # A kar hossza (váll-csukló)
    arm_length_m = np.linalg.norm(left_shoulder - left_wrist) if (left_shoulder is not None and left_wrist is not None) else 0

    # 3. Átszámolás cm-re és kerekítés
    shoulder_width_cm = round(shoulder_width_m * 100.0, 1) if shoulder_width_m > 0 else None
    hip_width_cm = round(hip_width_m * 100.0, 1) if hip_width_m > 0 else None
    arm_length_cm = round(arm_length_m * 100.0, 1) if arm_length_m > 0 else None
    
    # 4. Placeholder metrikák: PL. a váll/csípő arány
    shoulder_hip_ratio = round(shoulder_width_cm / hip_width_cm, 2) if shoulder_width_cm and hip_width_cm else None

    logger.info(f"✅ Antropometriai metrikák számítva: Váll: {shoulder_width_cm} cm, Csípő: {hip_width_cm} cm")

    return {
        "shoulder_width_cm": shoulder_width_cm,
        "hip_width_cm": hip_width_cm,
        "arm_length_cm": arm_length_cm,
        "shoulder_hip_ratio": shoulder_hip_ratio,
    }

# --- Service Osztály ---

class AnthropometryAssessmentService(BaseDiagnosticService):
    """
    Antropometriai adatok becslése videó alapján (magasság, végtagarányok).
    """

    @classmethod
    def run_analysis(cls, job) -> Dict[str, Any]:
        cls.log(f"▶️ Anthropometry Assessment indítása job_id={job.id}")
        
        # LÉPÉS 1: Profil betöltése az ismert adatokhoz (known_height)
        known_height = None
        try:
            profile = UserAnthropometryProfile.objects.get(user=job.user)
            if profile.height_cm and profile.height_cm > 100: 
                known_height = float(profile.height_cm) 
                cls.log(f"🔎 Előzetes profil magasság betöltve a kalibrációhoz: {known_height} cm")
        except UserAnthropometryProfile.DoesNotExist:
            cls.log(f"⚠️ Profil nem található, ismert magasság nélkül folytatódik.")
        
        
        # LÉPÉS 2: Videó letöltése
        video_path = get_local_video_path(job.video_url)

        try:
            # MediaPipe feldolgozás
            raw_keypoints, skeleton_video_path, keyframes = process_video_with_mediapipe(video_path)
            cls.log(f"MediaPipe feldolgozás kész, {len(raw_keypoints)} frame elemzve.")
            
            # LÉPÉS 3: Elemzés, becslés és feliratozott kép mentése (átadjuk a known_height-et!)
            analysis_result_raw = _estimate_height_and_annotate(
                {"raw_keypoints": raw_keypoints, "frames": keyframes}, 
                job,
                known_height
            )
            
            # 💡 LÉPÉS 4: Profil Magasság Frissítése
            estimated_height_cm = analysis_result_raw.get("estimated_height_cm")
            if estimated_height_cm and estimated_height_cm > 100:
                try:
                    profile, created = UserAnthropometryProfile.objects.get_or_create(user=job.user)
                    profile.height_cm = estimated_height_cm
                    profile.save()
                    cls.log(f"✅ Profil frissítve! Új magasság: {estimated_height_cm} cm")
                except Exception as update_e:
                    cls.log(f"❌ Hiba a profil magasság frissítése során: {update_e}")


            # 💡 LÉPÉS 5: Eredménystruktúra Összeállítása a Job Eredményéhez (HTML-nek!)
            
            # 🆕 LÉPÉS 5.1: Skeleton videó feltöltése publikusan (Ezzel a Service kezeli a feltöltést)
            # Ez KRITIKUS javítás a lejárt videó URL-ek problémájára.
            skeleton_video_url = None
            if skeleton_video_path and os.path.exists(skeleton_video_path):
                cls.log(f"⬆️ Skeleton videó feltöltése publikusan GCS-re: jobs/{job.id}/skeleton/skeleton_video.mp4")
                gcs_destination = f"jobs/{job.id}/skeleton/skeleton_video.mp4"
                
                # Használjuk a publikus feltöltő funkciót
                uploaded_url = upload_file_and_make_public(skeleton_video_path, gcs_destination)
                
                if uploaded_url:
                    skeleton_video_url = uploaded_url
                    cls.log(f"🎥 Skeleton videó feltöltve: {skeleton_video_url}")
                    # Töröljük a lokális fájlt, mivel már feltöltöttük
                    os.remove(skeleton_video_path)
                else:
                    cls.log("❌ Hiba a skeleton videó publikus feltöltésekor.")

            
            # Az `analysis_result_raw` tartalmazza a magasságot, a snapshot URL-t és az antropometriai metrikákat.
            
            final_result = {
                # 🆕 KRITIKUS JAVÍTÁS: A skeleton videó URL-jét a GYÖKÉRBE helyezzük.
                "skeleton_video_url": skeleton_video_url, 
                
                "general_metrics": {
                    "estimated_height_cm": analysis_result_raw.get("estimated_height_cm"),
                    "video_analysis_done": analysis_result_raw.get("video_analysis_done", False),
                    # A skeleton_video_url-t a tasks.py fogja beállítani a skeleton_video_local_path alapján,
                    # így azt a tasks.py-nak adjuk át.
                },
                # 🛠️ KRITIKUS JAVÍTÁS: Metrikák beágyazása a template által várt kulcs alá
                "anthropometry_metrics": {
                    "shoulder_width_cm": analysis_result_raw.get("shoulder_width_cm"),
                    "hip_width_cm": analysis_result_raw.get("hip_width_cm"),
                    "arm_length_cm": analysis_result_raw.get("arm_length_cm"),
                    "shoulder_hip_ratio": analysis_result_raw.get("shoulder_hip_ratio"),
                },
                # 🛠️ KRITIKUS JAVÍTÁS: Snapshot URL beágyazása a template által várt kulcs alá
                "visualizations": {
                    "anthropometry_snapshot_url": analysis_result_raw.get("annotated_snapshot_url"),
                }
            }


            # A skeleton_video_local_path-ot NE adjuk vissza, mivel a feltöltést mi intéztük.
            # Ezzel megelőzzük, hogy a tasks.py a régi, hibás GCS funkcióval próbálja feltölteni.
            
            return final_result

        except Exception as e:
            cls.log(f"❌ Kritikus hiba az Antropometriai elemzés során: {e}")
            raise e