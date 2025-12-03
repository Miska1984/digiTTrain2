import os
import logging
from google.cloud import run_v2
from google.api_core.exceptions import NotFound
from diagnostics_jobs.tasks import run_diagnostic_job

logger = logging.getLogger(__name__)

# ======= Alapbeállítások =======
ENV = os.getenv("ENVIRONMENT", "development").lower()
LOCAL_DEV = ENV in ["development", "local", "dev", "codespaces"]

PROJECT_ID = os.getenv("GS_PROJECT_ID", "digittrain-projekt")
REGION = os.getenv("GS_LOCATION", "europe-west1")
JOB_NAME = os.getenv("CLOUD_RUN_JOB_NAME", "celery-worker-job")


def enqueue_diagnostic_job(job_id: int):
    """Cloud Run Job indítása vagy Celery fallback."""
    if LOCAL_DEV:
        logger.info(f"⚙️ [LOCAL] Celery: job_id={job_id}")
        run_diagnostic_job.delay(job_id)
        return

    try:
        logger.info(f"🚀 Cloud Run Job indítása: {JOB_NAME} (job_id={job_id})")

        client = run_v2.JobsClient()
        job_path = f"projects/{PROJECT_ID}/locations/{REGION}/jobs/{JOB_NAME}"

        # ✅ A RunJobRequest-ben az overrides helyes szerkezete:
        request = run_v2.RunJobRequest(
            name=job_path,
            overrides=run_v2.Overrides(
                container_overrides=[
                    run_v2.ContainerOverride(
                        env=[
                            run_v2.EnvVar(
                                name="JOB_ID",
                                value=str(job_id)
                            )
                        ]
                    )
                ]
            )
        )

        # ✅ Job futtatása
        operation = client.run_job(request=request)
        logger.info(f"✅ Cloud Run Job execution indítva (operation: {operation.operation.name})")

        # ✅ Részletes metaadat loggolása
        if hasattr(operation, "metadata") and operation.metadata:
            execution_name = getattr(operation.metadata, "name", None)
            if execution_name:
                logger.info(f"🧩 Execution név: {execution_name}")

    except NotFound:
        logger.error(f"❌ A Cloud Run Job nem található: {JOB_NAME}")
        raise
    except Exception as e:
        logger.exception(f"❌ Job indítási hiba: {e}")
        raise
