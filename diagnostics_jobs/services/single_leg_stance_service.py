# diagnostics_jobs/services/single_leg_stance_service.py

import logging
import json
import os
from diagnostics_jobs.models import DiagnosticJob
from diagnostics_jobs.services.base_service import BaseDiagnosticService
from diagnostics.utils.mediapipe_processor import process_video_with_mediapipe
# Fontos: A BaseDiagnosticService-ben feltételezzük, hogy a szükséges segédosztályok (pl. geometry, snapshot_manager) már importálva vannak
# A példa tisztasága kedvéért a BaseService-re támaszkodunk.

from diagnostics.utils.geometry import (
    get_landmark_coords, 
    calculate_horizontal_tilt, 
    calculate_angle_3d,
    calculate_distance_3d,
    calculate_midpoint_3d
)
import numpy as np
from diagnostics_jobs.services.utils.anthropometry_loader import get_user_anthropometry_data
from diagnostics_jobs.utils import get_local_video_path
from diagnostics.utils.snapshot_manager import upload_file_to_gcs, save_snapshot_to_gcs

logger = logging.getLogger(__name__)

class SingleLegStanceAssessmentService(BaseDiagnosticService):
    """
    Az Egylábon Állás teszt (Single-Leg Stance) elemzéséért felelős szolgáltatás.
    Vizsgálja a medence, térd és boka stabilitását (SINGLE_LEG_STANCE_LEFT/RIGHT).
    """

    def run_analysis(self):
        job = self.job
        logger.info(f"Feldolgozás elindítva a job: {job.id} számára")

        # 0️⃣ Kalibráció betöltése
        anthro = get_user_anthropometry_data(job.user)
        general_factor = anthro.get("calibration_factor", 1.0) if anthro else 1.0
        leg_factor = anthro.get("leg_calibration_factor", 1.0) if anthro else 1.0
        
        # ❗ KRITIKUS: Elemzés indítása Kalibráció hiányában (ha kötelező)
        # Ha a statikus teszt (SLS) megengedett kalibráció nélkül, hagyjuk el ezt a blokkot. 
        # Feltételezzük, hogy itt is kell, mivel az abszolút elmozdulás fontos.
        if not anthro:
            self.log("❌ Kalibráció Hiba: Az Egylábon Állás elemzéshez antropometriai adatok (Kalibráció) hiányoznak. Elemzés F_general=1.0 faktorral.")
            # A hiba ellenére folytatjuk, de a pontosság csökken
            
        logger.info(f"✅ Kalibrációs faktorok betöltve: Általános={general_factor:.4f}, Láb={leg_factor:.4f}")

        # 1. Oldal meghatározása (melyik lábon áll)
        side_to_analyze = "left" if "LEFT" in job.job_type else "right"
        is_left_stance = side_to_analyze == "left"
        
        # 2. Videó letöltése és MediaPipe feldolgozás
        # ❌ EREDETI: local_video_path = self.download_video()
        # ✅ JAVÍTVA: Használjuk a standard utility függvényt
        local_video_path = get_local_video_path(job.video_url) 
        
        if not local_video_path:
            # ❗ Ez most a get_local_video_path függvény hibáját jelzi
            self.fail_job("Nem sikerült letölteni a videót.") 
            return {}

        # Végigfut a videón és visszaadja a teljes landmark adatokat minden frame-re
        # 🟢 Fő skálázáshoz az általános faktort használjuk
        all_landmarks, skeleton_path, keyframes = process_video_with_mediapipe(
            local_video_path, 
            job.job_type,
            calibration_factor=general_factor,
        ) 
        
        if not all_landmarks:
            self.fail_job("Nincs detektálható landmark a videóban.")
            return {}

        # 3. Biomechanikai számítások
        # 🟢 Átadjuk mindkét faktort
        analysis_result, video_summary = self._calculate_sls_metrics(
            all_landmarks, 
            is_left_stance, 
            general_factor, 
            leg_factor
        )
        
        # 4. Kép/videó előállítás
        # ❌ HIBÁS: skeleton_video_url = self.create_skeleton_video(local_video_path, all_landmarks)
        # 🟢 JAVÍTOTT: Feltöltjük a MediaPipe által generált videót (skeleton_path)
        
        # Feltételezzük, hogy a BaseDiagnosticService-ből megöröklődik egy upload_file_to_gcs nevű metódus:
        # Ha a BaseService-ből öröklődik az upload_file:
        try:
            if skeleton_path and os.path.exists(skeleton_path):
                logger.info(f"📤 Skeleton videó feltöltése GCS-re: {skeleton_path}")
                
                # 🟢 JAVÍTOTT: Egységes útvonal struktúra (mint a többi jobnál)
                gcs_destination = f"media/dev/jobs/{job.id}/skeleton_video.avi"
                
                skeleton_video_url = upload_file_to_gcs( 
                    local_file_path=skeleton_path, 
                    gcs_destination=gcs_destination
                )
                logger.info(f"✅ Skeleton videó feltöltve: {skeleton_video_url}")
            else:
                logger.error(f"❌ A skeleton videó nem létezik: {skeleton_path}")
                skeleton_video_url = None
                
        except Exception as e:
            logger.error(f"❌ Skeleton videó feltöltési hiba: {e}", exc_info=True)
            skeleton_video_url = None

        # Snapshot feltöltése a leginstabilabb frame-ről
        # ❌ HIBÁS: worst_frame_snapshot_url = self.upload_snapshot(...)
        # 🟢 JAVÍTOTT: A BaseService-ben feltételezünk egy upload_snapshot metódust.
        # Ha az upload_snapshot sem létezik (mint ahogy a create_skeleton_video sem):
        
        # Ezt a részt a BaseDiagnosticService-re alapozzuk, de mivel az hibázott, 
        # inkább csak tároljuk a lokális keyframe-et, és feltöltjük:
        
        worst_frame_snapshot_url = None
        worst_frame_index = video_summary.get('worst_frame_index', 0)
        
        if worst_frame_index > 0:
            # 💡 LOGIKAI KORREKCIÓ: A MediaPipe által generált keyframes-ből kikeressük a képadatot
            worst_frame_data = next((k for k in keyframes if k.get('frame_index', -1) == worst_frame_index), None)
            
            # Ha van kép adat ('frame_image' kulcs alatt) a kiválasztott frame-hez:
            if worst_frame_data and worst_frame_data.get('frame_image') is not None:
                try:
                    # 🟢 HELYES HÍVÁS: A kinyert frame-et (NumPy array) adjuk át a save_snapshot_to_gcs-nek
                    worst_frame_snapshot_url = save_snapshot_to_gcs(
                        frame_image=worst_frame_data['frame_image'],
                        job=job,
                        label=f"sls_worst_{side_to_analyze}"
                    )
                except Exception as e:
                    logger.warning(f"Snapshot létrehozás/feltöltés Hiba: {e}")


        # 5. Eredmények összegzése a PDF számára
        # 🟢 JAVÍTÁS: Biztonságos kulcshozzáférés a .get() metódusokkal, 
        # hogy ha egy kulcs hiányzik, ne szakadjon meg a program.
        
        # 1. Biztonságos hozzáférés a 'scoring_breakdown'-hoz (alapértelmezett: üres szótár {})
        scoring_breakdown = analysis_result.get("scoring_breakdown", {})
        
        final_result = {
            # Biztonságos hozzáférés a fő kulcsokhoz
            "overall_score": analysis_result.get("overall_score", 0),
            "stability_score": analysis_result.get("stability_score", 0),
            "pelvic_control_score": analysis_result.get("pelvic_control_score", 0),
            "knee_ankle_score": analysis_result.get("knee_ankle_score", 0),
            
            # Biztonságos hozzáférés a 'scoring_breakdown' belsejében lévő kulcsokhoz
            "time_score": scoring_breakdown.get('Kitartás idő', 0),
            "symmetry_score": scoring_breakdown.get('Szimetriaviszony', 0),
            
            # További kulcsok biztonságosan
            "max_pelvic_drop_angle": analysis_result.get("max_pelvic_drop_angle", 0), 
            "max_knee_valgus_angle": analysis_result.get("max_knee_valgus_angle", 0), 
            "side": side_to_analyze,
            
            # 🆕 ÚJ: A generált visszajelzések
            "feedback_list": analysis_result.get("feedback_list", []),
            "skeleton_video_url": skeleton_video_url,
            "worst_frame_snapshot_url": worst_frame_snapshot_url,
            # 🆕 ÚJ: Kalibrációs adatok mentése
            "calibration_used": bool(anthro),
            "general_calibration_factor": round(general_factor, 5),
            "leg_calibration_factor": round(leg_factor, 5),
        }
        
        # 6. PDF riport generálása
        pdf_url = self.generate_report(final_result)
        
        # 7. Job befejezése
        self.complete_job(
            result=final_result,
            pdf_path=pdf_url
        )
        logger.info(f"✅ Egylábon állás elemzés sikeresen befejezve (Job ID: {job.id})")

        return final_result

    def _calculate_sls_metrics(self, all_landmarks: list[dict], is_left_stance: bool, general_factor: float, leg_factor: float) -> tuple[dict, dict]:
        """A stabilitás, medencekontroll és térd/boka stabilitási metrikák kiszámítása."""
        
        # 🆕 KALIBRÁCIÓ KORREKCIÓS TÉNYEZŐ SZÁMÍTÁSA (EGYSZER)
        correction_factor = leg_factor / general_factor if general_factor and general_factor != 0 else leg_factor

        # Metrika gyűjtők
        pelvic_drop_angles = []
        knee_valgus_angles = []
        stance_ankle_sway_corrected = [] # 🆕 Korrigált pontokat fog tárolni
        
        # Landmark nevek a támaszkodó oldalhoz
        side_prefix = "left" if is_left_stance else "right"
        opp_prefix = "right" if is_left_stance else "left"
        
        # A támaszkodó oldal ízületei
        stance_hip = f'{side_prefix}_hip'
        stance_knee = f'{side_prefix}_knee'
        stance_ankle = f'{side_prefix}_ankle'
        stance_foot_index = f'{side_prefix}_foot_index'
        
        # Az ellentétes (szabad) oldal ízületei
        opp_hip = f'{opp_prefix}_hip'

        # 1. Metrikák számítása frame-enként
        for i, frame_data in enumerate(all_landmarks):
            # world_landmarks = frame_data.get('world_landmarks', [])
            
            # --- Alsótest pontok kinyerése és KORREKCIÓJA (F_leg skálázás) ---
            
            # A támaszkodó oldal ízületei
            p_stance_hip = get_landmark_coords(frame_data, stance_hip)
            p_stance_knee = get_landmark_coords(frame_data, stance_knee)
            p_stance_ankle = get_landmark_coords(frame_data, stance_ankle)
            p_stance_foot = get_landmark_coords(frame_data, stance_foot_index)
            
            # Az ellentétes (szabad) oldal ízületei
            p_opp_hip = get_landmark_coords(frame_data, opp_hip) # 🟢 JAVÍTVA       
            
            lower_body_coords = [
                p_stance_hip, p_stance_knee, p_stance_ankle, p_stance_foot, p_opp_hip
            ]

            corrected_coords = []
            for p in lower_body_coords:
                if p is not None:
                    # 🔹 Alkalmazzuk a korrekciós faktort (F_leg / F_general)
                    corrected_coords.append(np.array(p) * correction_factor)
                else:
                    corrected_coords.append(None)
            
            [p_stance_hip, p_stance_knee, p_stance_ankle, p_stance_foot, p_opp_hip] = corrected_coords
            
            # --- 1.1 Medence Dőlés (Pelvic Drop) - KORRIGÁLT pontokkal ---
            if p_stance_hip is not None and p_opp_hip is not None:
                # ... (calculate_horizontal_tilt hívás VÁLTOZATLAN, de a pontok korrigáltak)
                drop_angle = calculate_horizontal_tilt(p_left=p_stance_hip, p_right=p_opp_hip) \
                             if is_left_stance else \
                             calculate_horizontal_tilt(p_left=p_opp_hip, p_right=p_stance_hip)
                pelvic_drop_angles.append(abs(drop_angle))

            # --- 1.2 Térd Valgus (Knee Valgus/Varus) - KORRIGÁLT pontokkal ---
            if p_stance_hip is not None and p_stance_knee is not None and p_stance_ankle is not None:
                # ... (calculate_angle_3d hívás VÁLTOZATLAN, de a pontok korrigáltak)
                knee_angle = calculate_angle_3d(p_stance_hip, p_stance_knee, p_stance_ankle)
                valgus_dev = 180.0 - knee_angle
                knee_valgus_angles.append(max(0.0, valgus_dev))

            # --- 1.3 Stabilitás / Boka Billegés (Ankle Sway) - KORRIGÁLT pontokkal ---
            if p_stance_ankle is not None:
                stance_ankle_sway_corrected.append(p_stance_ankle) # 🆕 Korrigált pontok gyűjtése
            
        # 2. Összegzés / Maximumok és Szórások számítása
        
        # Medencekontroll metrikák
        max_pelvic_drop = np.max(pelvic_drop_angles) if pelvic_drop_angles else 0.0
        
        # Térd-boka metrikák
        max_knee_valgus_dev = np.max(knee_valgus_angles) if knee_valgus_angles else 0.0
        
        # Stabilitás metrikák (A billegés/sway metrikája a szórás)
        sway_points = np.array(stance_ankle_sway_corrected)
        sway_amplitude = 0.0
        if sway_points.size > 0:
            # Csak az X (oldalra) és Z (előre/hátra) mozgás érdekes
            sway_x_z = sway_points[:, [0, 2]]
            sway_amplitude = np.std(sway_x_z) * 100 # Skálázás
            
        # 3. Metrikák becsomagolása
        metrics = {
            "max_pelvic_drop_deg": float(max_pelvic_drop),
            "max_knee_valgus_deg": float(max_knee_valgus_dev),
            "ankle_sway_amplitude": float(sway_amplitude),
            "stance_time_sec": len(all_landmarks) / 30, # Feltételezett 30 FPS
            # Ide kell bejönnie a leginstabilabb frame számításának is (pl. ahol a legnagyobb az eltérés a boka pozíciójában)
        }
        
        # Ideiglenes summary
        video_summary = {
            'worst_frame_index': 0 # Ide kell a valós számítás
        }
        
        # 4. Pontozás és Visszajelzés
        overall_score, scoring_breakdown = self._score_sls(metrics)
        metrics["overall_score"] = overall_score
        feedback = self._generate_feedback(metrics, scoring_breakdown)
        
        analysis_result = {
            # ... (Lásd a következő lépést, a végleges analysis_result)
            "overall_score": overall_score,
            "stability_score": scoring_breakdown.get('Stabilitás', 0),
            "pelvic_control_score": scoring_breakdown.get('Medence kontroll', 0),
            "knee_ankle_score": scoring_breakdown.get('Térd-boka stabilitás', 0),
            "max_pelvic_drop_angle": metrics["max_pelvic_drop_deg"],
            "max_knee_valgus_angle": metrics["max_knee_valgus_deg"],
            "feedback_list": feedback, # A PDF-hez
            "side": side_prefix
        }

        return analysis_result, video_summary
    
    def _score_sls(self, metrics: dict) -> tuple[float, dict]:
        """A biomechanikai metrikák pontozása a 100 pontos skálán az egylábon állás.docx alapján."""

        # 💡 KONSTANSOK az egylábon állás.docx alapján
        MAX_SCORE = 100
        MAX_STABILITY = 40
        MAX_PELVIC_CONTROL = 20
        MAX_KNEE_ANKLE = 20
        MAX_SYMMETRY = 10 # Szimmetria nincs, de a pontot meghagyjuk
        MAX_TIME = 10     # Max Kitartási Idő (ha pl. 30 mp a maximum)
        
        # Metrika értékek
        drop_deg = metrics["max_pelvic_drop_deg"]
        valgus_deg = metrics["max_knee_valgus_deg"]
        sway_amp = metrics["ankle_sway_amplitude"]
        stance_time = metrics["stance_time_sec"]

        # 1. Medence Kontroll Pontozás (Max 20 pont)
        # Feltételezés: 0-5 fok = Kiváló; 5-10 fok = Jó; > 10 fok = Gyenge.
        if drop_deg <= 5.0:
            pelvic_score = MAX_PELVIC_CONTROL * 1.0 # 20 pont
        elif drop_deg <= 10.0:
            pelvic_score = MAX_PELVIC_CONTROL * 0.75 # 15 pont
        else:
            pelvic_score = MAX_PELVIC_CONTROL * 0.25 # 5 pont

        # 2. Térd-Boka Stabilitás Pontozás (Max 20 pont)
        # Feltételezés: Knee Valgus 0-5 fok = Kiváló; > 5 fok = Gyenge.
        if valgus_deg <= 5.0:
            knee_score = MAX_KNEE_ANKLE * 1.0 # 20 pont
        else:
            knee_score = MAX_KNEE_ANKLE * 0.5 # 10 pont
            
        # 3. Stabilitás Pontozás (Max 40 pont)
        # Feltételezés: A boka billegés amplitúdója (sway_amp). Kisebb a jobb.
        # Feltételezés: 0-1.5 a jó, 1.5-3 a közepes, > 3 a gyenge.
        if sway_amp <= 1.5:
            stability_score = MAX_STABILITY * 1.0 # 40 pont
        elif sway_amp <= 3.0:
            stability_score = MAX_STABILITY * 0.6 # 24 pont
        else:
            stability_score = MAX_STABILITY * 0.3 # 12 pont
            
        # 4. Kitartás Idő Pontozás (Max 10 pont)
        # Feltételezés: 20 mp a max. 
        max_target_time = 20.0
        time_score = min(stance_time / max_target_time, 1.0) * MAX_TIME
        
        # 5. Szimmetriaviszony (Max 10 pont) - Nincs adat, átmenetileg 5 pont
        symmetry_score = MAX_SYMMETRY * 0.5 
        
        # Összegzés
        total_score = stability_score + pelvic_score + knee_score + symmetry_score + time_score
        
        scoring_breakdown = {
            'Stabilitás': round(stability_score),
            'Medence kontroll': round(pelvic_score),
            'Térd-boka stabilitás': round(knee_score),
            'Szimetriaviszony': round(symmetry_score),
            'Kitartás idő': round(time_score)
        }
        
        return total_score, scoring_breakdown
    
    def _generate_feedback(self, metrics: dict, scoring: dict) -> list[str]:
        """Kiértékelő visszajelzések generálása a pontozás és metrikák alapján."""
        
        feedback_list = []
        
        # --- Általános Értékelés a Teljes Pontszám alapján ---
        total_score = metrics.get('overall_score', 0) # A _calculate_sls_metrics adja hozzá
        
        if total_score >= 85:
            feedback_list.append("Kiváló neuromuszkuláris stabilitás! Folytassa az egyensúlyi gyakorlatokat a teljesítmény optimalizálásáért.")
        elif total_score >= 70:
            feedback_list.append("Jó teljesítmény, de kisebb korrekciók szükségesek. Fókuszáljon a gyengébb területekre.")
        elif total_score >= 50:
            feedback_list.append("Instabilitás jelei mutatkoznak. Javasolt célzott megelőző program az adott gyengeségekre.")
        else:
            feedback_list.append("Magas sérüléskockázatot és gyenge propriocepciót jelez. Konzultáljon szakemberrel, és kezdjen célzott erősítő programot!")

        # --- Specifikus Hibák és Javaslatok ---
        
        # Medence Kontroll (Pelvic Drop)
        if scoring.get('Medence kontroll', 0) < 15 and metrics["max_pelvic_drop_deg"] > 7.0:
            feedback_list.append("**Csípő lecsap (pelvic drop):** A medence stabilitása gyenge (glute medius deficit). **Javaslat:** oldalhíd, band walks, Cossack squat.")

        # Térd-Boka Stabilitás (Knee Valgus/Sway)
        if scoring.get('Térd-boka stabilitás', 0) < 15 and metrics["max_knee_valgus_deg"] > 5.0:
            feedback_list.append("**Térd befelé esése (Valgus):** Enyhe ACL veszélyt jelezhet. **Javaslat:** egylábas squat progressziók, csípő külső forgató izmok erősítése.")
        
        if scoring.get('Stabilitás', 0) < 20 and metrics["ankle_sway_amplitude"] > 3.0:
            feedback_list.append("**Boka túlzott billegése:** Boka instabilitás vagy sérülés utáni maradvány jele. **Javaslat:** calf raise, balance board, barefoot drills.")

        # Stabilitás (Törzs hintázás/Sway)
        if scoring.get('Stabilitás', 0) < 25:
             feedback_list.append("**Törzs hintázás (főként X/Z tengely mentén):** Core deficitre utal. **Javaslat:** anti-rotációs gyakorlatok (pl. Pallof press), plank variációk.")
             
        # Kitartás Idő
        if scoring.get('Kitartás idő', 0) < 5:
             feedback_list.append(f"**Rövid kitartás idő ({metrics['stance_time_sec']:.1f} mp):** Törekedjen a 20 másodperces kitartásra mindkét lábon.")

        return feedback_list