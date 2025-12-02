import os
import logging

logger = logging.getLogger(__name__)

# --- Cloud Run import ---
try:
    from google.cloud import run_v2
    from google.api_core.exceptions import NotFound
    
    # Teszt
    _ = run_v2.JobsClient()
    logger.info("✅ google-cloud-run elérhető.")
    
except Exception as e:
    logger.error(f"❌ google-cloud-run hiba: {e}")
    run_v2 = None
    NotFound = Exception

from diagnostics_jobs.tasks import run_diagnostic_job

ENV = os.getenv("ENVIRONMENT", "development").lower()
LOCAL_DEV = ENV in ["development", "local", "dev", "codespaces"]

PROJECT_ID = os.getenv("GS_PROJECT_ID", "digittrain-projekt") 
REGION = os.getenv("GS_LOCATION", "europe-west1")
JOB_NAME = os.getenv("CLOUD_RUN_JOB_NAME", "celery-worker-job")


def enqueue_diagnostic_job(job_id: int):
    """Cloud Run Job indítása vagy Celery fallback."""
    
    # Lokális fejlesztés
    if LOCAL_DEV:
        logger.info(f"⚙️ [LOCAL] Celery: job_id={job_id}")
        run_diagnostic_job.delay(job_id)
        return
    
    # Production: Cloud Run V2 ellenőrzés
    if run_v2 is None:
        logger.error("❌ google-cloud-run nem elérhető!")
        raise RuntimeError("Cloud Run V2 kliens hiányzik.")
    
    try:
        logger.info(f"🚀 Cloud Run Job: {JOB_NAME} (job_id={job_id})")
        
        client = run_v2.JobsClient()
        job_path = f"projects/{PROJECT_ID}/locations/{REGION}/jobs/{JOB_NAME}"
        
        # ✅ RunJobRequest objektum használata
        request = run_v2.RunJobRequest(
            name=job_path,
            overrides=run_v2.RunJobRequest.Overrides(
                container_overrides=[
                    run_v2.RunJobRequest.Overrides.ContainerOverride(
                        name="celery-job-container",
                        command=["python"],
                        args=["manage.py", "run_job_execution"],
                        env=[
                            run_v2.EnvVar(name="JOB_ID", value=str(job_id))
                        ],
                    )
                ]
            ),
        )
        
        # ✅ KRITIKUS: run_job() egy Operation objektumot ad vissza
        operation = client.run_job(request=request)
        
        # ✅ Az execution neve az operation metadata-ból kérhető le
        # De NEM VÁRJUK MEG az operation befejezését (mert aszinkron futtatás)
        logger.info(f"✅ Cloud Run Job execution indítva (operation: {operation.operation.name})")
        
        # Opcionálisan: execution név lekérése (ha a metadata tartalmazza)
        if hasattr(operation, 'metadata') and operation.metadata:
            execution_name = getattr(operation.metadata, 'name', 'N/A')
            logger.info(f"   Execution név: {execution_name}")
        
    except NotFound:
        logger.error(f"❌ Job nem található: {JOB_NAME}")
        raise
    except Exception as e:
        logger.exception(f"❌ Job indítási hiba: {e}")
        raise