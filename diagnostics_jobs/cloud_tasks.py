import os
import json
import logging
from datetime import datetime, timedelta, timezone

try:
    from google.cloud import run_v2
    from google.api_core.exceptions import NotFound
except ImportError:
    run_v2 = None

try:
    from google.cloud import tasks_v2
    from google.protobuf import timestamp_pb2
except ImportError:
    tasks_v2 = None
    timestamp_pb2 = None

from diagnostics_jobs.tasks import run_diagnostic_job  # fallback lokális

logger = logging.getLogger(__name__)

ENV = os.getenv("ENVIRONMENT", "development").lower()
LOCAL_DEV = ENV in ["development", "local", "dev", "codespaces"]

PROJECT_ID = os.getenv("GS_PROJECT_ID", "digittrain-projekt") 
REGION = os.getenv("GS_LOCATION", "europe-west1")
JOB_NAME = os.getenv("CLOUD_RUN_JOB_NAME", "celery-worker-job")


def enqueue_diagnostic_job(job_id: int):
    """
    Cloud Run Job elindítása (felhőben),
    vagy lokálisan Celery fallback használata.
    """
    if LOCAL_DEV or run_v2 is None:
        # Lokális fallback – simán meghívja a Celery-t
        print(f"⚙️ [LOCAL] Celery task indítása: job_id={job_id}")
        run_diagnostic_job.delay(job_id)
        return

    try:
        logger.info(f"🚀 Cloud Run Job indítása: {JOB_NAME} (job_id={job_id})")

        # Cloud Run API kliens
        client = run_v2.JobsClient()
        parent = f"projects/{PROJECT_ID}/locations/{REGION}"
        job_path = f"{parent}/jobs/{JOB_NAME}"

        # Paraméterek átadása környezeti változóként (runtime env)
        # vagy `args`-ban
        execution = client.run_job(
            name=job_path,
            overrides=run_v2.RunJobRequest.Overrides(
                container_overrides=[
                    run_v2.ContainerOverride(
                        name="celery-job-container",
                        args=[
                            # 🚨 KRITIKUS: EZ A HÁROM ARGUMENTUM KELL
                            "python", 
                            "manage.py", 
                            "run_job_execution" 
                        ],
                        env=[
                            run_v2.EnvVar(name="JOB_ID", value=str(job_id)),
                        ],
                    )
                ]
            ),
        )

        logger.info(f"✅ Cloud Run Job execution elindítva: {execution.name}")

    except NotFound:
        logger.error(f"❌ Cloud Run Job nem található: {JOB_NAME}")
    except Exception as e:
        logger.exception(f"❌ Hiba a Cloud Run Job indításakor: {e}")
