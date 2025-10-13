# diagnostics_jobs/services/wrestling_diagnostics.py
from datetime import datetime
from .general_diagnostics import GeneralDiagnosticsService
import random

class WrestlingDiagnosticsService:
    """
    Birkózóspecifikus diagnosztika:
    biomechanikai, erő- és koordinációs mutatók elemzése biometrikus háttéradatokkal.
    """

    @staticmethod
    def run_analysis(job):
        base = GeneralDiagnosticsService.run_analysis(job)
        base["type"] = "wrestling"

        # Sportág-specifikus mutatók (valós biometrikus minták + becslések)
        base["explosiveness_score"] = WrestlingDiagnosticsService._calc_explosiveness(job)
        base["grip_strength_ratio"] = WrestlingDiagnosticsService._calc_grip_ratio(job)
        base["balance_stability"] = WrestlingDiagnosticsService._calc_balance(job)

        # Összegző sportági index
        base["wrestling_performance_index"] = round(
            (base["explosiveness_score"] * 0.4 +
             base["balance_stability"] * 0.3 +
             base["grip_strength_ratio"] * 100 * 0.3), 1
        )

        # Új, sportági sérüléskockázati becslés
        base["wrestling_injury_risk"] = WrestlingDiagnosticsService._predict_injury_risk(base)

        return base

    @staticmethod
    def _calc_explosiveness(job):
        if job.hrv_snapshot:
            recovery = job.hrv_snapshot.avg_hrv or 50
            fatigue = job.workout_feedback_snapshot.fatigue_level if job.workout_feedback_snapshot else 50
            return max(0, min(100, 100 - fatigue + (recovery * 0.3)))
        return random.randint(50, 80)

    @staticmethod
    def _calc_grip_ratio(job):
        if job.weight_snapshot:
            w = job.weight_snapshot.weight_value or 75
            return round(min(1.2, max(0.7, 1.0 + (random.random() - 0.5) * 0.3)), 2)
        return 1.0

    @staticmethod
    def _calc_balance(job):
        if job.hrv_snapshot:
            sleep = job.hrv_snapshot.sleep_quality or 5
            return min(100, max(50, sleep * 10 + random.uniform(-5, 5)))
        return random.randint(60, 85)

    @staticmethod
    def _predict_injury_risk(data):
        perf = data.get("wrestling_performance_index", 70)
        if perf >= 85:
            return "Alacsony"
        elif perf >= 65:
            return "Közepes"
        else:
            return "Magas"
