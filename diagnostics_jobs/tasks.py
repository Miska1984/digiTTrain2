import time
from datetime import datetime
from django.utils import timezone
from .models import DiagnosticJob
from .services.general_diagnostics import GeneralDiagnosticsService
from .services.wrestling_diagnostics import WrestlingDiagnosticsService


def run_diagnostic_job(job_id):
    """
    Egyszerű szinkron feldolgozó szimuláció.
    Később Google Cloud Task vagy Cloud Run job fogja ezt futtatni aszinkron.
    """
    try:
        job = DiagnosticJob.objects.get(id=job_id)
        job.status = "running"
        job.save(update_fields=["status"])

        # Fiktív késleltetés a háttérmunka szimulálásához
        time.sleep(3)

        # Service kiválasztása
        if job.job_type == "general":
            result = GeneralDiagnosticsService.run_analysis(job)
        elif job.job_type == "wrestling":
            result = WrestlingDiagnosticsService.run_analysis(job)
        else:
            result = {"error": "Ismeretlen job típus"}

        # Mentés a JSONField-be
        job.result = result
        job.status = "completed"
        job.completed_at = timezone.now()
        job.save(update_fields=["result", "status", "completed_at"])

    except Exception as e:
        job = DiagnosticJob.objects.filter(id=job_id).first()
        if job:
            job.status = "failed"
            job.result = {"error": str(e)}
            job.save(update_fields=["status", "result"])
        print(f"❌ Diagnostic job {job_id} hiba: {e}")
