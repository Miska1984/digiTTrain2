import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model
from diagnostics_jobs.models import DiagnosticJob
from diagnostics_jobs.cloud_tasks import enqueue_diagnostic_job
from diagnostics_jobs.tasks import run_diagnostic_job

User = get_user_model()


@csrf_exempt
def create_diagnostic_job(request):
    """
    Sportoló videót tölt fel és elemzést kér.
    A rendszer nem azonnal, hanem 5 órán belül futtatja le a feldolgozást
    (Google Cloud Tasks ütemezéssel).
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST metódus szükséges"}, status=405)

    try:
        data = json.loads(request.body)

        user_id = data.get("user_id")
        sport_type = data.get("sport_type", "general")
        job_type = data.get("job_type", "general")
        video_url = data.get("video_url")

        if not all([user_id, sport_type, job_type, video_url]):
            return JsonResponse({"success": False, "error": "Hiányzó kötelező mező"}, status=400)

        user = User.objects.filter(id=user_id).first()
        if not user:
            return JsonResponse({"success": False, "error": "Felhasználó nem található"}, status=404)

        # Létrehozzuk az új diagnosztikai feladatot
        job = DiagnosticJob.objects.create(
            user=user,
            sport_type=sport_type,
            job_type=job_type,
            video_url=video_url,
        )

        # Feladat ütemezése (nem azonnali futtatás)
        try:
            task_name = enqueue_diagnostic_job(job.id)
            msg = f"Feladat ütemezve: {task_name}"
        except Exception as e:
            msg = f"Helyi fejlesztés: Task nem ütemezhető ({e})"

        return JsonResponse({
            "success": True,
            "job_id": job.id,
            "status": job.status,
            "video_url": job.video_url,
            "message": msg,
        })

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@csrf_exempt
def run_diagnostic_job_view(request):
    """Cloud Task vagy lokális hívás a diagnosztikai job lefuttatására."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        payload = json.loads(request.body)
        job_id = payload.get("job_id")
        if not job_id:
            return JsonResponse({"error": "Missing job_id"}, status=400)

        job = DiagnosticJob.objects.get(id=job_id)
        run_diagnostic_job(job_id)

        job.refresh_from_db()
        return JsonResponse({
            "success": True,
            "job_id": job.id,
            "status": job.status,
            "result": job.result
        })

    except DiagnosticJob.DoesNotExist:
        return JsonResponse({"error": "Job not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    