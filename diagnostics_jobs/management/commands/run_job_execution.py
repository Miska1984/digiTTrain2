import os
import sys
import logging
from django.core.management.base import BaseCommand
from diagnostics_jobs.tasks import run_diagnostic_job # A meglévő task függvényed

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

class Command(BaseCommand):
    help = 'A DiagnosticJob végrehajtása a JOB_ID környezeti változó alapján.'

    def handle(self, *args, **options):
        # 1. Betöltjük a JOB_ID-t a Cloud Run Job környezeti változójából
        job_id_str = os.getenv('JOB_ID')
        
        if not job_id_str:
            logger.error("❌ A JOB_ID környezeti változó hiányzik.")
            sys.exit(1) # Kilépés hibával, ha a JOB_ID nincs meg
            
        try:
            job_id = int(job_id_str)
        except ValueError:
            logger.error(f"❌ Érvénytelen JOB_ID: {job_id_str}")
            sys.exit(1)

        logger.info(f"🚀 [JOB EXECUTION] Indul a Diagnostic Job #{job_id}")
        
        # 2. Közvetlenül meghívjuk a task függvényt (nem Celery-n keresztül!)
        try:
            # A run_diagnostic_job(job_id) hívás a teljes elemzést elvégzi
            run_diagnostic_job(job_id)
            logger.info(f"✅ [JOB EXECUTION] Diagnostic Job #{job_id} sikeresen befejeződött.")
            sys.exit(0) # Sikeres kilépés
            
        except Exception as e:
            logger.critical(f"❌ [JOB EXECUTION] Kritikus hiba a job futtatása közben #{job_id}: {e}", exc_info=True)
            sys.exit(1) # Kilépés hibával