import random
import time
from datetime import datetime
from django.utils import timezone
from .models import DiagnosticJob
from .services.general_diagnostics import GeneralDiagnosticsService
from .services.wrestling_diagnostics import WrestlingDiagnosticsService
from diagnostics.pdf_utils import generate_pdf_report


def run_diagnostic_job(job_id):
    """
    Mock 'gépi látásos' elemzés — csak fejlesztési környezetben.
    Elemzi a feltöltött videót (valójában random adatot generál),
    majd PDF riportot készít és elmenti az eredményt.
    """
    try:
        job = DiagnosticJob.objects.get(id=job_id)
        job.status = "running"
        job.save(update_fields=["status"])

        # 🔹 Szimulált elemzési idő
        time.sleep(2)

        # 🔹 Mock eredmények (testtartás elemzés)
        analysis_data = {
            "timestamp": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "general_posture",
            "shoulder_angle": round(random.uniform(1.0, 5.0), 1),
            "spine_tilt": round(random.uniform(0.5, 3.0), 1),
            "hip_asymmetry": round(random.uniform(0.5, 2.5), 1),
            "balance_score": random.randint(70, 100),
        }

        # 🔹 Szöveges értékelés
        overall_rating = (
            "Jó" if analysis_data["balance_score"] > 85 and analysis_data["spine_tilt"] < 1.5
            else "Közepes" if analysis_data["balance_score"] > 70
            else "Gyenge"
        )
        analysis_data["overall_rating"] = overall_rating

        # 🔹 PDF generálás
        pdf_url = generate_pdf_report(job, analysis_data)
        analysis_data["report_pdf_url"] = pdf_url

        # 🔹 Eredmény mentése
        job.result = analysis_data
        job.status = "completed"
        job.completed_at = timezone.now()
        job.save(update_fields=["result", "status", "completed_at"])

        return True

    except DiagnosticJob.DoesNotExist:
        print(f"[ERROR] DiagnosticJob {job_id} nem található.")
        return False

    except Exception as e:
        print(f"[ERROR] run_diagnostic_job hiba: {e}")
        job.status = "failed"
        job.save(update_fields=["status"])
        return False