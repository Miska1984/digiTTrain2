import os
import sys
import logging
from django.core.management.base import BaseCommand
from diagnostics_jobs.tasks import run_diagnostic_job

# GPU elnémítás
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


class Command(BaseCommand):
    help = 'DiagnosticJob végrehajtása a JOB_ID környezeti változó alapján.'

    def handle(self, *args, **options):
        job_id_str = os.getenv('JOB_ID')

        if not job_id_str:
            logger.error("❌ A JOB_ID környezeti változó hiányzik.")
            sys.exit(1)

        try:
            job_id = int(job_id_str)
        except ValueError:
            logger.error(f"❌ Érvénytelen JOB_ID: {job_id_str}")
            sys.exit(1)

        logger.info(f"🚀 [JOB EXECUTION] Indul a Diagnostic Job #{job_id}")

        try:
            run_diagnostic_job(job_id)
            logger.info(f"✅ [JOB EXECUTION] Diagnostic Job #{job_id} sikeresen befejeződött.")
            sys.exit(0)
        except Exception as e:
            logger.critical(f"❌ [JOB EXECUTION] Kritikus hiba #{job_id}: {e}", exc_info=True)
            sys.exit(1)
