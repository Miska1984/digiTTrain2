# diagnostics_jobs/services/base_service.py

from datetime import datetime

class BaseDiagnosticService:
    """Közös alap a diagnosztikai elemzők számára."""

    @staticmethod
    def log(message):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧩 {message}")

    @classmethod
    def run_analysis(cls, job):
        """Minden diagnosztikai service-nek implementálnia kell."""
        raise NotImplementedError("Implementáld a run_analysis metódust.")
