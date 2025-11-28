import os
import logging
from google.cloud import run_v2
from google.api_core.exceptions import NotFound
from google.cloud.run_v2.types import ContainerOverride
from diagnostics_jobs.tasks import run_diagnostic_job # fallback lokális

logger = logging.getLogger(__name__)

# --- Környezeti beállítások betöltése ---
ENV = os.getenv("ENVIRONMENT", "development").lower()
# Az a cél, hogy csak a 'development', 'local', 'dev', 'codespaces' fusson lokálisan
LOCAL_DEV = ENV in ["development", "local", "dev", "codespaces"]

PROJECT_ID = os.getenv("GS_PROJECT_ID", "digittrain-projekt") 
REGION = os.getenv("GS_LOCATION", "europe-west1")
JOB_NAME = os.getenv("CLOUD_RUN_JOB_NAME", "celery-worker-job")

def enqueue_diagnostic_job(job_id: int):
    """
    Cloud Run Job elindítása (felhőben),
    vagy lokálisan Celery fallback használata.
    """
    # 1. Lokális fallback: Celery hívása (fejlesztés)
    # A LOCAL_DEV ellenőrzés elegendő.
    if LOCAL_DEV: 
        print(f"⚙️ [LOCAL] Celery task indítása: job_id={job_id}")
        # A Celery hívás a .delay()-jel aszinkron elindítja a jobot
        run_diagnostic_job.delay(job_id) 
        return
            
    # 2. Éles környezet: Cloud Run Job indítása
    
    # Biztosítjuk, hogy a google-cloud-run modul elérhető legyen éles környezetben.
    if run_v2 is None:
        logger.error("❌ A 'google-cloud-run' függőség hiányzik a production image-ben!")
        # Exception dobása: ezzel 500-as hibát generálunk a views.py-ban, 
        # ami a levonás visszatérítéséhez vezet.
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
                            # Ez a parancs fog elindulni a Cloud Run Job konténerben
                            "python", 
                            "manage.py", 
                            "run_job_execution" 
                        ],
                        env=[
                            # Ez adja át a JOB_ID-t a manage.py parancsnak
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