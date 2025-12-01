import os
import logging

logger = logging.getLogger(__name__)

# --- Cloud Run V2 import megpróbálása ---
try:
    from google.cloud import run_v2
    from google.api_core.exceptions import NotFound
    
    # ✅ Teszt: kliens inicializálás
    _test_client = run_v2.JobsClient()
    logger.info("✅ google-cloud-run import és kliens inicializálás sikeres.")
    
    # Flag hogy elérhető
    CLOUD_RUN_AVAILABLE = True
    
except ImportError as e:
    logger.error(f"❌ google-cloud-run csomag nincs telepítve: {e}")
    run_v2 = None
    NotFound = None
    CLOUD_RUN_AVAILABLE = False
    
except Exception as e:
    logger.error(f"⚠️ google-cloud-run inicializálási hiba: {e}")
    run_v2 = None
    NotFound = None
    CLOUD_RUN_AVAILABLE = False

# Celery fallback
from diagnostics_jobs.tasks import run_diagnostic_job

# --- Környezeti beállítások ---
ENV = os.getenv("ENVIRONMENT", "development").lower()
LOCAL_DEV = ENV in ["development", "local", "dev", "codespaces"]

PROJECT_ID = os.getenv("GS_PROJECT_ID", "digittrain-projekt") 
REGION = os.getenv("GS_LOCATION", "europe-west1")
JOB_NAME = os.getenv("CLOUD_RUN_JOB_NAME", "celery-worker-job")


def enqueue_diagnostic_job(job_id: int):
    """
    Cloud Run Job elindítása (production),
    vagy Celery fallback (development).
    """
    # 1. Lokális fejlesztés: Celery
    if LOCAL_DEV: 
        logger.info(f"⚙️ [LOCAL] Celery task indítása: job_id={job_id}")
        run_diagnostic_job.delay(job_id)
        return
    
    # 2. Production ellenőrzés
    if not CLOUD_RUN_AVAILABLE:
        logger.error("❌ Cloud Run V2 nem elérhető production környezetben!")
        raise RuntimeError(
            "Cloud Run V2 kliens nem elérhető. "
            "Ellenőrizd a függőségeket és a Docker image buildet."
        )
    
    # 3. Cloud Run Job indítása
    try:
        logger.info(f"🚀 Cloud Run Job indítása: {JOB_NAME} (job_id={job_id})")
        
        client = run_v2.JobsClient()
        parent = f"projects/{PROJECT_ID}/locations/{REGION}"
        job_path = f"{parent}/jobs/{JOB_NAME}"
        
        # ✅ Típusok dinamikus lekérése a client-ből
        request_cls = run_v2.RunJobRequest
        
        execution = client.run_job(
            request=request_cls(
                name=job_path,
                overrides=request_cls.Overrides(
                    container_overrides=[
                        request_cls.Overrides.ContainerOverride(
                            name="celery-job-container",
                            args=[
                                "python",
                                "manage.py",
                                "run_job_execution"
                            ],
                            env=[
                                run_v2.EnvVar(
                                    name="JOB_ID",
                                    value=str(job_id)
                                ),
                            ],
                        )
                    ]
                ),
            )
        )
        
        logger.info(f"✅ Cloud Run Job execution elindítva: {execution.name}")
        
    except NotFound:
        logger.error(f"❌ Cloud Run Job nem található: {JOB_NAME}")
        raise
        
    except Exception as e:
        logger.exception(f"❌ Kritikus hiba a Cloud Run Job indításakor: {e}")
        raise