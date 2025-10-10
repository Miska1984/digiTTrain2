# diagnostics_jobs/api.py
import json
import datetime
from django.http import JsonResponse, HttpResponseBadRequest, Http404
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.conf import settings
from .models import DiagnosticJob
from .tasks import run_diagnostic_job

User = get_user_model()


@csrf_exempt
def create_diagnostic_job(request):
    """
    Új diagnosztikai feladat létrehozása.
    A felhasználó videó URL-t ad meg (GCS-ben tárolva).
    """
    if request.method != "POST":
        return HttpResponseBadRequest("Csak POST metódus engedélyezett.")

    try:
        data = json.loads(request.body)
        user_id = data.get("user_id")
        sport_type = data.get("sport_type", "general")
        job_type = data.get("job_type", "wrestling")
        video_url = data.get("video_url")

        if not (user_id and video_url):
            return HttpResponseBadRequest("user_id és video_url kötelező mezők.")

        user = get_object_or_404(User, id=user_id)

        job = DiagnosticJob.objects.create(
            user=user,
            sport_type=sport_type,
            job_type=job_type,
            video_url=video_url,
            status="pending",
        )

        # Diagnosztika futtatása (most szinkron, később Cloud Task)
        run_diagnostic_job(job.id)

        return JsonResponse({
            "success": True,
            "job_id": job.id,
            "status": job.status,
            "video_url": job.video_url,
        }, status=201)

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def get_job_status(request, job_id):
    """
    Egy adott diagnosztikai job státuszának lekérése.
    """
    job = get_object_or_404(DiagnosticJob, id=job_id)
    return JsonResponse({
        "job_id": job.id,
        "status": job.status,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "error_message": job.error_message,
    })


def get_job_result(request, job_id):
    """
    Diagnosztikai eredmény lekérése (ha már elkészült).
    """
    job = get_object_or_404(DiagnosticJob, id=job_id)

    if job.status != "completed":
        return JsonResponse({
            "job_id": job.id,
            "status": job.status,
            "message": "Az elemzés még nem készült el."
        }, status=202)

    return JsonResponse({
        "job_id": job.id,
        "status": job.status,
        "result": job.result,
    })


@csrf_exempt
def cleanup_old_videos(request):
    """
    30 napnál régebbi videók törlése (csak admin vagy cron futtathatja).
    """
    if request.method != "POST":
        return HttpResponseBadRequest("Csak POST metódus engedélyezett.")

    cutoff = timezone.now() - datetime.timedelta(days=30)
    old_jobs = DiagnosticJob.objects.filter(created_at__lt=cutoff)

    deleted = 0
    for job in old_jobs:
        if job.video_url and job.video_url.startswith("https://storage.googleapis.com/"):
            # A jövőben ide jöhet GCS API törlés
            job.video_url = None
            job.save(update_fields=["video_url"])
            deleted += 1

    return JsonResponse({
        "success": True,
        "deleted_count": deleted,
    })
