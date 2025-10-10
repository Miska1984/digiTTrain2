import os
import json
from datetime import datetime, timedelta, timezone

# Csak akkor próbáljuk importálni a Google Cloud modult, ha elérhető
try:
    from google.cloud import tasks_v2
    from google.protobuf import timestamp_pb2
except ImportError:
    tasks_v2 = None
    timestamp_pb2 = None

# Fejlesztői környezet jelölése
LOCAL_DEV = os.getenv("ENVIRONMENT", "development") == "development"

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "digittrain-projekt")
QUEUE_ID = os.getenv("GCLOUD_TASK_QUEUE", "diagnostic-job-queue")
LOCATION = os.getenv("GCP_REGION", "europe-west1")
CLOUD_RUN_URL = os.getenv(
    "CLOUD_RUN_URL",
    "https://digit-train-web-195803356854.europe-west1.run.app"
)


def enqueue_diagnostic_job(job_id: int):
    """
    Google Cloud Task létrehozása, vagy fejlesztői környezetben helyi fallback.
    """
    # --- FEJLESZTŐI / LOKÁLIS FUTÁS ---
    if tasks_v2 is None or LOCAL_DEV:
        print(f"⚙️ Local fallback: running job {job_id} synchronously.")
        from diagnostics_jobs.tasks import run_diagnostic_job
        run_diagnostic_job(job_id)
        print(f"✅ Local diagnostic job {job_id} completed successfully.")
        return

    # --- FELHŐS FUTÁS ---
    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(PROJECT_ID, LOCATION, QUEUE_ID)

    task_payload = {"job_id": job_id}
    task_data = json.dumps(task_payload).encode()

    # 0–5 óra közötti időpont
    delay_hours = 5
    run_time = datetime.now(timezone.utc) + timedelta(
        seconds=int(delay_hours * 3600 * 0.5)
    )

    timestamp = timestamp_pb2.Timestamp()
    timestamp.FromDatetime(run_time)

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": f"{CLOUD_RUN_URL}/diagnostics/run-job/",
            "headers": {"Content-Type": "application/json"},
            "body": task_data,
        },
        "schedule_time": timestamp,
    }

    response = client.create_task(request={"parent": parent, "task": task})
    print(f"✅ Cloud Task created for job_id={job_id} → {response.name}")
    return response.name
