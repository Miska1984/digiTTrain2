# diagnostics_jobs/services/general_diagnostics.py

import random
from .base_service import BaseDiagnosticService

class GeneralDiagnosticsService(BaseDiagnosticService):

    @classmethod
    def run_analysis(cls, job):
        cls.log(f"Általános diagnosztika indítása a {job.user.username} felhasználóhoz...")

        # Szimulált biometriai értékek elemzése
        fatigue_score = random.randint(50, 100)
        recovery_index = random.randint(50, 100)
        hydration_level = random.randint(70, 100)

        cls.log(f"Eredmények kiszámítva: fáradtság={fatigue_score}, regeneráció={recovery_index}")

        # Sportspecifikus javaslat
        suggestion = "Kiváló regenerációs állapot" if recovery_index > 80 else "További pihenés javasolt"

        result = {
            "type": "general",
            "fatigue_score": fatigue_score,
            "recovery_index": recovery_index,
            "hydration_level": hydration_level,
            "suggestion": suggestion,
        }

        cls.log("Általános diagnosztika befejezve.")
        return result
