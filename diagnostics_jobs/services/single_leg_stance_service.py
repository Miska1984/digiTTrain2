# diagnostics_jobs/services/single_leg_stance_service.py

import logging
import json
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

logger = logging.getLogger(__name__)

class SingleLegStanceAssessmentService(BaseDiagnosticService):
    """
    Az Egylábon Állás teszt (Single-Leg Stance) elemzéséért felelős szolgáltatás.
    Vizsgálja a medence, térd és boka stabilitását (SINGLE_LEG_STANCE_LEFT/RIGHT).
    """

    def run_analysis(self):
        job = self.job
        logger.info(f"Feldolgozás elindítva a job: {job.id} számára")

        # 1. Oldal meghatározása (melyik lábon áll)
        side_to_analyze = "left" if "LEFT" in job.job_type else "right"
        is_left_stance = side_to_analyze == "left"
        
        logger.info(f"📐 Elemzett támaszkodó oldal: {side_to_analyze.upper()}")

        # 2. Videó letöltése és MediaPipe feldolgozás
        local_video_path = self.download_video()
        if not local_video_path:
            self.fail_job("Nem sikerült letölteni a videót.")
            return {}

        # Végigfut a videón és visszaadja a teljes landmark adatokat minden frame-re
        all_landmarks = process_video_with_mediapipe(local_video_path)
        
        if not all_landmarks:
            self.fail_job("Nincs detektálható landmark a videóban.")
            return

        # 3. Biomechanikai számítások (itt a helye a MediaPipe adatok feldolgozásának)
        analysis_result, video_summary = self._calculate_sls_metrics(all_landmarks, is_left_stance)
        
        # 4. Kép/videó előállítás
        skeleton_video_url = self.create_skeleton_video(local_video_path, all_landmarks)
        # Snapshot feltöltése a leginstabilabb frame-ről
        worst_frame_snapshot_url = self.upload_snapshot(
            video_summary.get('worst_frame_index'), 
            f"sls_worst_{side_to_analyze}_{job.id}.jpg", 
            local_video_path
        )


        # 5. Eredmények összegzése a PDF számára
        final_result = {
            "overall_score": analysis_result["overall_score"],
            "stability_score": analysis_result["stability_score"],
            "pelvic_control_score": analysis_result["pelvic_control_score"],
            "knee_ankle_score": analysis_result["knee_ankle_score"],
            "time_score": analysis_result["scoring_breakdown"].get('Kitartás idő', 0),
            "symmetry_score": analysis_result["scoring_breakdown"].get('Szimetriaviszony', 0),
            "max_pelvic_drop_angle": analysis_result["max_pelvic_drop_angle"], 
            "max_knee_valgus_angle": analysis_result["max_knee_valgus_angle"], 
            "side": side_to_analyze,
             # 🆕 ÚJ: A generált visszajelzések
            "feedback_list": analysis_result["feedback_list"],
            "skeleton_video_url": skeleton_video_url,
            "worst_frame_snapshot_url": worst_frame_snapshot_url,
            # ... (további metrikák)
        }
        
        # 6. PDF riport generálása
        pdf_url = self.generate_report(final_result)
        
        # 7. Job befejezése
        self.complete_job(
            result=final_result,
            pdf_path=pdf_url
        )
        logger.info(f"✅ Egylábon állás elemzés sikeresen befejezve (Job ID: {job.id})")

    def _calculate_sls_metrics(self, all_landmarks: list[dict], is_left_stance: bool) -> tuple[dict, dict]:
        """A stabilitás, medencekontroll és térd/boka stabilitási metrikák kiszámítása."""

        # Metrika gyűjtők
        pelvic_drop_angles = []
        knee_valgus_angles = []
        stance_ankle_sway = [] # A bokák billegését méri (instabilitás)
        
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
            world_landmarks = frame_data.get('world_landmarks', [])
            
            # --- 1.1 Medence Dőlés (Pelvic Drop) ---
            # Két csípőpont X-Y-Z koordinátáinak kinyerése
            p_stance_hip = get_landmark_coords(world_landmarks, stance_hip)
            p_opp_hip = get_landmark_coords(world_landmarks, opp_hip)
            
            if p_stance_hip is not None and p_opp_hip is not None:
                # calculate_horizontal_tilt: méri a dőlést a két pont között
                drop_angle = calculate_horizontal_tilt(p_left=p_stance_hip, p_right=p_opp_hip) \
                             if is_left_stance else \
                             calculate_horizontal_tilt(p_left=p_opp_hip, p_right=p_stance_hip)
                pelvic_drop_angles.append(abs(drop_angle)) # Az abszolút értéket tároljuk

            # --- 1.2 Térd Valgus (Knee Valgus/Varus) ---
            # Csípő-Térd-Boka szög (frontális síkban dőlés mérése)
            p_hip = get_landmark_coords(world_landmarks, stance_hip)
            p_knee = get_landmark_coords(world_landmarks, stance_knee)
            p_ankle = get_landmark_coords(world_landmarks, stance_ankle)
            
            if p_hip is not None and p_knee is not None and p_ankle is not None:
                # Kiszámoljuk a belső ízületi szöget
                knee_angle = calculate_angle_3d(p_hip, p_knee, p_ankle)
                # Az ideális egyenes állás ~175-180 fok. A Valgus (befelé esés) a kisebb szög.
                # A 180 fokhoz képesti eltérést tároljuk Valgus-ként.
                valgus_dev = 180.0 - knee_angle
                knee_valgus_angles.append(max(0.0, valgus_dev))

            # --- 1.3 Stabilitás / Boka Billegés (Ankle Sway) ---
            # A boka billegésének mértéke az XZ síkon (oldalirányú mozgás)
            p_ankle = get_landmark_coords(world_landmarks, stance_ankle)
            p_foot = get_landmark_coords(world_landmarks, stance_foot_index)
            
            if p_ankle is not None and p_foot is not None:
                # Használhatjuk a lábfej index (32) és boka (28) pontok mozgását is
                # A legegyszerűbb proxy: Boka X és Z koordinátáinak szórása az időben.
                # A Frame-ek tárolják a boka X, Y, Z pozícióját a world_landmarks-ben.
                stance_ankle_sway.append(p_ankle)
            
        # 2. Összegzés / Maximumok és Szórások számítása
        
        # Medencekontroll metrikák
        max_pelvic_drop = np.max(pelvic_drop_angles) if pelvic_drop_angles else 0.0
        
        # Térd-boka metrikák
        max_knee_valgus_dev = np.max(knee_valgus_angles) if knee_valgus_angles else 0.0
        
        # Stabilitás metrikák (A billegés/sway metrikája a szórás)
        sway_points = np.array(stance_ankle_sway)
        sway_amplitude = 0.0
        if sway_points.size > 0:
            # Csak az X (oldalra) és Z (előre/hátra) mozgás érdekes
            sway_x_z = sway_points[:, [0, 2]]
            # A szórás (standard deviation) a mozgás amplitúdóját méri.
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