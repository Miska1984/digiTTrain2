# diagnostics_jobs/services/general_diagnostics.py
import statistics
from datetime import datetime

class GeneralDiagnosticsService:
    """
    Általános biometrikus diagnosztika, súly, HRV, alvás, és edzésadatok alapján.
    """

    @staticmethod
    def run_analysis(job):
        result = {
            "type": "general",
            "user": job.user.username,
            "created_at": datetime.utcnow().isoformat(),
        }

        # --- Súly trend elemzés ---
        if job.weight_snapshot:
            try:
                weight_data = job.weight_snapshot
                avg_weight = round(weight_data.weight_value, 1)
                result["avg_weight"] = avg_weight
                result["weight_stability"] = GeneralDiagnosticsService._calculate_weight_stability(weight_data)
            except Exception as e:
                result["weight_error"] = f"Hiba a súlyadat feldolgozásakor: {e}"
        else:
            result["weight_warning"] = "Nincs súlyadat"

        # --- HRV és alvásdiagnosztika ---
        if job.hrv_snapshot:
            try:
                hrv_data = job.hrv_snapshot
                result["avg_hrv"] = hrv_data.avg_hrv or 0
                result["sleep_quality"] = GeneralDiagnosticsService._normalize_sleep(hrv_data.sleep_quality or 0)
                result["recovery_score"] = GeneralDiagnosticsService._calculate_recovery_score(hrv_data)
            except Exception as e:
                result["hrv_error"] = f"Hiba a HRV/alvásadat feldolgozásakor: {e}"
        else:
            result["hrv_warning"] = "Nincs HRV vagy alvásadat"

        # --- Edzésvisszajelzés elemzés ---
        if job.workout_feedback_snapshot:
            try:
                feedback = job.workout_feedback_snapshot
                result["training_load"] = feedback.training_load
                result["fatigue_score"] = feedback.fatigue_level
                result["mood_score"] = feedback.mood_level
                result["overtraining_risk"] = GeneralDiagnosticsService._calculate_overtraining_risk(feedback)
            except Exception as e:
                result["feedback_error"] = f"Hiba az edzésadat feldolgozásakor: {e}"
        else:
            result["feedback_warning"] = "Nincs edzés visszajelzés"

        # --- Összesített kondíciós index ---
        result["fitness_index"] = GeneralDiagnosticsService._aggregate_fitness_score(result)
        result["predicted_injury_risk"] = GeneralDiagnosticsService._predict_injury_risk(result)

        return result

    # --- Segédfüggvények ---
    @staticmethod
    def _calculate_weight_stability(weight_data):
        # Például kiszámítja a súlyingadozást a beállított súlyhoz képest
        stable_range = abs(weight_data.weight_value - weight_data.target_weight)
        return max(0, 100 - stable_range * 5)

    @staticmethod
    def _normalize_sleep(quality):
        return round(min(100, max(0, quality * 10)), 1)

    @staticmethod
    def _calculate_recovery_score(hrv_data):
        hrv = hrv_data.avg_hrv or 0
        sleep = hrv_data.sleep_quality or 0
        return round((hrv * 0.6 + sleep * 0.4), 1)

    @staticmethod
    def _calculate_overtraining_risk(feedback):
        load = feedback.training_load
        fatigue = feedback.fatigue_level
        mood = feedback.mood_level
        risk = load * 0.5 + fatigue * 0.4 - mood * 0.3
        return round(max(0, min(100, risk)), 1)

    @staticmethod
    def _aggregate_fitness_score(data):
        components = []
        for k in ["weight_stability", "recovery_score", "mood_score"]:
            if k in data:
                components.append(data[k])
        return round(statistics.mean(components), 1) if components else None

    @staticmethod
    def _predict_injury_risk(data):
        score = data.get("fitness_index", 50)
        if score >= 80:
            return "Alacsony"
        elif score >= 60:
            return "Közepes"
        else:
            return "Magas"
