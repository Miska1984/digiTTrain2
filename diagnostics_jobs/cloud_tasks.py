import os
import json
import logging
from datetime import datetime, timedelta, timezone

try:
    from google.cloud import run_v2
    from google.api_core.exceptions import NotFound
    from google.cloud.run_v2.types import RunJobRequest, ContainerOverride
except ImportError:
    run_v2 = None
    RunJobRequest = None
    ContainerOverride = None

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
    # 🚨 KRITIKUS JAVÍTÁS: Csak akkor használjuk a Celery-t/lokális fallback-et, 
    # ha a környezet EGYÉRTELMŰEN lokális.
    if LOCAL_DEV: 
        if run_v2 is None:
            # Ha nincsenek telepítve a google-cloud-run library-k, akkor 
            # feltételezzük, hogy Celery-t használsz, és meghívjuk a .delay-t.
            # DE EZ A CLOUD RUN-BAN NINCS JÓL MŰKÖDÉSRE BÍRVA!
            print(f"⚙️ [LOCAL] Celery task indítása: job_id={job_id}")
            run_diagnostic_job.delay(job_id)
            return
        else:
            # Lokális fejlesztésnél, ha van run_v2, mégis a Celery-t erőszakoljuk
            # a korábbi logikád szerint.
            print(f"⚙️ [LOCAL] Cloud Run Job fallback: job_id={job_id} (Celery-n keresztül)")
            run_diagnostic_job.delay(job_id)
            return
            
    # 🚀 ÉLES KÖRNYEZET (ENVIRONMENT: production) ÉS Cloud Run Job indítása
    if run_v2 is None:
        logger.error("❌ A 'google-cloud-run' függőség hiányzik. Nem tudom elindítani a Cloud Run Jobot!")
        # Itt egy exceptiont dobunk, ami a hívó függvény (views.py) felé fog hibát jelezni (500-as hiba)
        raise RuntimeError("Cloud Run V2 kliens nem elérhető. Ellenőrizd a függőségeket.")


    try:
        logger.info(f"🚀 Cloud Run Job indítása: {JOB_NAME} (job_id={job_id})")

        # Cloud Run API kliens
        client = run_v2.JobsClient()
        parent = f"projects/{PROJECT_ID}/locations/{REGION}"
        job_path = f"{parent}/jobs/{JOB_NAME}"

        # Paraméterek átadása környezeti változóként
        execution = client.run_job(
            name=job_path,
            overrides=run_v2.RunJobRequest.Overrides(
                container_overrides=[
                    ContainerOverride(
                        name="celery-job-container",
                        args=[
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
        logger.error(f"❌ Cloud Run Job nem található: {JOB_NAME}. Ellenőrizd a Cloud Run Jobs listát.")
        raise
    except Exception as e:
        logger.exception(f"❌ Kritikus hiba a Cloud Run Job indításakor: {e}")
        raise