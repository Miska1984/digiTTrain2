# diagnostics_jobs/services/wrestling_diagnostics.py

import random
from .base_service import BaseDiagnosticService

class WrestlingDiagnosticsService(BaseDiagnosticService):

    @classmethod
    def run_analysis(cls, job):
        cls.log(f"Birkózó diagnosztika fut a {job.user.username} felhasználóhoz...")

        # Itt majd mozgáselemzési és biomechanikai minták kerülnek be
        balance_stability = random.randint(60, 100)
        grip_strength_ratio = random.uniform(0.8, 1.2)
        explosiveness_score = random.randint(50, 100)

        cls.log("Birkozó metrikák kiszámítva.")

        result = {
            "type": "wrestling",
            "balance_stability": balance_stability,
            "grip_strength_ratio": round(grip_strength_ratio, 2),
            "explosiveness_score": explosiveness_score,
            "predicted_injury_risk": cls._estimate_injury_risk(balance_stability, explosiveness_score),
        }

        cls.log("Birkozó diagnosztika befejezve.")
        return result

    @staticmethod
    def _estimate_injury_risk(balance, explosiveness):
        """Egyszerű sérüléskockázat becslő logika."""
        if balance < 70 and explosiveness > 85:
            return "Magas"
        elif balance < 80:
            return "Közepes"
        return "Alacsony"
