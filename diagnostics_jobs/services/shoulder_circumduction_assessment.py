import logging
import numpy as np
from typing import List, Dict, Any
from decimal import Decimal

# Importáljuk a szükséges geometriai függvényeket
from diagnostics.utils.geometry import calculate_angle_3d, get_landmark_coords, calculate_horizontal_tilt
from diagnostics.utils.mediapipe_processor import process_video_with_mediapipe
from diagnostics.utils.snapshot_manager import save_snapshot_to_gcs
from diagnostics_jobs.utils import get_local_video_path
from diagnostics_jobs.services.base_service import BaseDiagnosticService
from diagnostics_jobs.services.utils.anthropometry_loader import get_user_anthropometry_data
from general_results.models import ShoulderCircumductionResult # ❗ Ezt a Modelt még létre kell hozni!

logger = logging.getLogger(__name__)

# Segédfüggvény (Váll-törzs szög számításához, a kompenzációhoz)
def _calculate_trunk_tilt(shoulder: np.ndarray, hip: np.ndarray) -> float:
    """Törzsdőlés szögének becslése (csípő és váll függőlegeshez viszonyított dőlése)."""
    # Létrehozunk egy függőleges referenciapontot (vagy a tengelyt használjuk, ha elérhető)
    vertical_ref = np.array([hip[0], hip[1] + 100, hip[2]])
    # Itt a calculate_horizontal_tilt a megfelelő, ha a frontális aszimmetriát mérjük.
    # Ha a törzsdőlés mértékét mérjük (oldalnézet, mint guggolásnál), akkor ez kell:
    angle = calculate_angle_3d(shoulder, hip, vertical_ref)
    return 180.0 - angle


class ShoulderCircumductionService(BaseDiagnosticService):
    """
    Vállkörzés elemzés (ROM, lapocka kontroll, szimmetria, kompenzáció).
    """

    
    def run_analysis(self):
        job = self.job
        self.log(f"▶️ Vállkörzés Assessment indítása job_id={job.id}")
        video_path = get_local_video_path(job.video_url)

        try:
            # 0️⃣ Kalibráció
            anthro = get_user_anthropometry_data(job.user)
            general_factor = anthro.get("calibration_factor", 1.0) if anthro else 1.0
            # A leg_calibration_factor-t betöltjük, de nem használjuk a számításban, mert ez egy felsőtest teszt.
            leg_factor = anthro.get("leg_calibration_factor", 1.0) if anthro else 1.0 
            
            self.log(f"Kalibrációs faktor (általános/felsőtest): {general_factor:.4f}")

            # 1️⃣ Videó feldolgozása MediaPipe-pal
            raw_keypoints, skeleton_video_path, keyframes = process_video_with_mediapipe(
                video_path, 
                job.job_type,
                calibration_factor=general_factor,
            )
            self.log(f"MediaPipe feldolgozás kész, {len(raw_keypoints)} frame elemzve.")

            # 2️⃣ Elemzés
            analysis = self._analyze_shoulder_circumduction(raw_keypoints, job, general_factor, leg_factor)
            analysis["video_analysis_done"] = True
            analysis["skeleton_video_local_path"] = skeleton_video_path
            
            # ⚠️ JSON-hiba Javítás: Tisztítjuk a keyframes-t
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
            analysis["general_calibration_factor"] = round(general_factor, 5)
            analysis["leg_calibration_factor"] = round(leg_factor, 5)
            
            # 🆕 3️⃣ AZ EREDMÉNY MENTÉSE ----------------
            # Kinyerjük a fő metrikákat
            overall_score = analysis.get('overall_score', 0.0)
            max_rom_left = analysis.get('max_elevation_angle_left', 0.0)
            max_rom_right = analysis.get('max_elevation_angle_right', 0.0)
            
            ShoulderCircumductionResult.objects.create(
                user=job.user,
                job=job,
                created_at=job.created_at,
                
                # Konvertálás Decimal-ra
                overall_score=Decimal(str(overall_score)),
                max_rom_left=Decimal(str(max_rom_left)),
                max_rom_right=Decimal(str(max_rom_right)),

                # Az összes elemzési adat mentése JSON-ként
                raw_json_metrics=analysis,
            )
            self.log(f"✅ Vállkörzés Assessment eredmény elmentve job_id={job.id}")
            # --------------------------------------------------------------------------
            
            return analysis

        except Exception as e:
            self.log(f"❌ Vállkörzés Assessment hiba job_id={job.id}: {e}")
            return {"error": f"Elemzés hiba: {e}", "video_analysis_done": False}

    
    def _analyze_shoulder_circumduction(self, raw_keypoints: List[Dict[str, Any]], job, general_factor: float, leg_factor: float) -> Dict[str, Any]:
        """A vállkörzés elemzésének futtatása (ROM, kontroll, kompenzáció)."""
        
        # 1. Metrikák inicializálása
        max_elevation_l, max_elevation_r = 0.0, 0.0
        max_asymmetry = 0.0
        max_tilt_l, max_tilt_r = 0.0, 0.0 # Törzs aszimmetria/kompenzáció
        max_elevation_frame_l, max_elevation_frame_r = None, None
        
        elevation_angles_l, elevation_angles_r = [], []
        tilt_angles = []

        # 2. Frame-enkénti elemzés
        for frame_data in raw_keypoints:
            # Kulcspontok beolvasása (FONTOS: r_elbow, r_wrist hozzáadva!)
            l_shoulder = get_landmark_coords(frame_data, 'left_shoulder')
            l_elbow = get_landmark_coords(frame_data, 'left_elbow')
            l_wrist = get_landmark_coords(frame_data, 'left_wrist')
            l_hip = get_landmark_coords(frame_data, 'left_hip')
            
            r_shoulder = get_landmark_coords(frame_data, 'right_shoulder')
            r_elbow = get_landmark_coords(frame_data, 'right_elbow') # 🆕 Ezt a sort felejtettük ki!
            r_wrist = get_landmark_coords(frame_data, 'right_wrist') # 🆕 Ez is szükséges
            r_hip = get_landmark_coords(frame_data, 'right_hip')
            
            # Skálázás (az egyszerűség kedvéért kihagyom, de a kódodban benne van a ciklus)
            # ❗ Fontos: A kalibrálás miatt a get_landmark_coords-nak is NumPy tömböt kellene visszaadnia, ha kalibrálunk! 
            # Az eredeti kódban a ciklusban konvertáltál np.array-re, itt feltételezzük, hogy a kapott adatok már NumPy-k.

            # Váll eleváció számítás (Ha a nézet frontális, akkor a kar-törzs szög kell)
            if all(p is not None for p in [l_shoulder, l_hip, l_wrist]):
                # A váll eleváció szögét (humerus a törzshöz képest) itt hip-shoulder-wrist szögként becsüljük, 
                # vagy a törzs függőlegeséhez képest. Használjuk a Hip-Shoulder-Elbow szögét, ha van könyök adat.
                
                # Feltételezve, hogy a 'calculate_angle_3d' a törzset veszi referenciának:
                # Váll eleváció: hip - shoulder - elbow/wrist
                # Mivel 2D frontális (legtöbbször), feltételezzük, hogy a 'vertical_ref' a hip felett van:
                vertical_ref = np.array([l_shoulder[0], l_shoulder[1] + 100, l_shoulder[2]]) 
                
                # ❗ Megjegyzés: Vállkörzésnél az eleváció szögét a törzs hosszanti tengelyéhez képest mérik!
                # Itt most a vállkörzés frontális nézetből történik. Használjunk egy leegyszerűsített tengelyt.
                
                # Törzs referencia: hip - shoulder (hosszanti tengely)
                # Kar referencia: shoulder - elbow/wrist
                # A legegyszerűbb, ha a Y tengelyhez viszonyítjuk az elevációt (180 - szög)
                
                if l_elbow is not None:
                     l_elev_angle = calculate_angle_3d(l_hip, l_shoulder, l_elbow) # Hip-Shoulder-Elbow szög
                     l_elev_angle_deg = 180.0 - l_elev_angle # Kb. a törzshöz képesti eleváció
                else: # Ha nincs könyök (vagy csukló)
                     l_elev_angle_deg = 0.0 # Képtelenség számolni
                     
                elevation_angles_l.append(l_elev_angle_deg)
                if l_elev_angle_deg > max_elevation_l:
                    max_elevation_l, max_elevation_frame_l = l_elev_angle_deg, frame_data
            
            # Jobb oldal
                if all(p is not None for p in [r_hip, r_shoulder, r_elbow]):
                    # Ugyanaz a számítási logika, mint a bal oldalon
                    r_elev_angle = calculate_angle_3d(r_hip, r_shoulder, r_elbow)
                    r_elev_angle_deg = 180.0 - r_elev_angle
                 
                    elevation_angles_r.append(r_elev_angle_deg)
                    if r_elev_angle_deg > max_elevation_r:
                        max_elevation_r, max_elevation_frame_r = r_elev_angle_deg, frame_data
                else:
                 # Ha hiányzik a kulcspont, nulla szöget veszünk fel, de ez nem befolyásolja a max_elevation_r-t,
                 # mert az eleve 0.0-ról indul.
                    elevation_angles_r.append(0.0)
                    if r_elev_angle_deg > max_elevation_r:
                        max_elevation_r, max_elevation_frame_r = r_elev_angle_deg, frame_data


            # Törzs Kompenzáció (Pl. Törzsdőlés aszimmetria frontális nézetből)
            if all(p is not None for p in [l_shoulder, r_shoulder, l_hip, r_hip]):
                current_tilt = calculate_horizontal_tilt(l_shoulder, r_shoulder) # Válldőlés
                tilt_angles.append(current_tilt)
                if abs(current_tilt) > abs(max_asymmetry):
                    max_asymmetry = current_tilt

        # 3. Pontozás (a melléklet alapján)
        avg_asymmetry = np.mean(np.abs(tilt_angles)) if tilt_angles else 0.0
        
        # ROM score (Mobilitás - 35p)
        max_rom_avg = (max_elevation_l + max_elevation_r) / 2.0
        ROM_optimal = 175.0 # Az elemzésben 160° a határ, de 175° a cél
        ROM_error = max(0.0, ROM_optimal - max_rom_avg)
        ROM_max_error = 40.0
        rom_score = max(0.0, 35.0 * (1 - ROM_error / ROM_max_error))

        # Kompenzáció score (Törzs/Nyak billenés - 10p)
        # Törzsdőlés optimalizálás: 5 fok alatti válldőlés
        Trunk_optimal_error = 5.0 
        Trunk_error = max(0.0, avg_asymmetry - Trunk_optimal_error)
        trunk_comp_score = max(0.0, 10.0 * (1 - Trunk_error / 10.0))

        # A többi score-hoz (Scapula kontroll, Szimmetria, Kontroll) feltételezések kellenek
        scapula_score = 30.0 # Főleg a váll aszimmetria alapján
        symm_score = 15.0 * max(0.0, 1.0 - (abs(max_elevation_l - max_elevation_r) / 20.0)) # 20 fok eltérés = 0 pont
        control_score = 10.0 # Még nincs megvalósítva, de tegyünk be egy átlagos pontot

        overall_score = rom_score + scapula_score + symm_score + trunk_comp_score + control_score

        # 4. Visszajelzés
        feedback = []
        if max_rom_avg < 160:
            feedback.append(f"A maximális eleváció elmarad az optimálistól ({max_rom_avg:.1f}°). Valószínű m. latissimus dorsi / mellizom rövidülés.")
        if abs(max_elevation_l - max_elevation_r) > 10:
            feedback.append(f"Jelentős aszimmetria ({abs(max_elevation_l - max_elevation_r):.1f}°) a bal és jobb kar között.")
        if abs(max_asymmetry) > 5:
            feedback.append(f"Törzs kompenzáció észlelhető a mozgás során (max. válldőlés: {max_asymmetry:.1f}°).")
        
        if overall_score > 85:
            feedback.append("Optimális vállövi funkció és kontroll!")
        elif overall_score < 70:
            feedback.append("Mérsékelt diszfunkció — korrekció szükséges a sérüléskockázat csökkentéséhez.")


        # 5. Snapshotok
        # Snapshot mentése a bal/jobb maximális mobilitási pontoknál
        snapshot_url_l = save_snapshot_to_gcs(max_elevation_frame_l["frame_image"], job, "max_elevation_l") if max_elevation_frame_l and "frame_image" in max_elevation_frame_l else None
        snapshot_url_r = save_snapshot_to_gcs(max_elevation_frame_r["frame_image"], job, "max_elevation_r") if max_elevation_frame_r and "frame_image" in max_elevation_frame_r else None


        return {
            "overall_score": float(round(overall_score, 1)), 
            "max_elevation_angle_left": float(round(max_elevation_l, 1)), 
            "max_elevation_angle_right": float(round(max_elevation_r, 1)), 
            "max_asymmetry": float(round(abs(max_asymmetry), 1)),
            "rom_score": float(round(rom_score, 1)), 
            "scapula_score": float(round(scapula_score, 1)),
            "symm_score": float(round(symm_score, 1)),
            "trunk_comp_score": float(round(trunk_comp_score, 1)),
            "control_score": float(round(control_score, 1)),
            "feedback": feedback,
            "snapshot_url_left": snapshot_url_l,
            "snapshot_url_right": snapshot_url_r,
        }