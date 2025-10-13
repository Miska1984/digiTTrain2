from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.contrib.auth import get_user_model
from .tasks import run_diagnostic_job
from .models import DiagnosticJob
from biometric_data.models import WeightData, HRVandSleepData, WorkoutFeedback

User = get_user_model()

@csrf_exempt
def create_diagnostic_job(request):
    """
    Új diagnosztikai feladat létrehozása.
    Automatikusan csatolja a sportoló legfrissebb biometrikus adatait.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST metódus szükséges"}, status=405)

    try:
        data = json.loads(request.body)
        user_id = data.get("user_id")
        sport_type = data.get("sport_type", "general")
        job_type = data.get("job_type", "general")
        video_url = data.get("video_url")

        if not all([user_id, sport_type, job_type, video_url]):
            return JsonResponse({"error": "Hiányzó kötelező mező"}, status=400)

        user = User.objects.filter(id=user_id).first()
        if not user:
            return JsonResponse({"error": "Felhasználó nem található"}, status=404)

        # 🔹 Legfrissebb biometrikus adatok lekérése
        latest_weight = WeightData.objects.filter(user=user).order_by('-created_at').first()
        latest_hrv = HRVandSleepData.objects.filter(user=user).order_by('-recorded_at').first()
        latest_feedback = WorkoutFeedback.objects.filter(user=user).order_by('-workout_date').first()

        # 🔹 Diagnosztikai feladat létrehozása
        job = DiagnosticJob.objects.create(
            user=user,
            sport_type=sport_type,
            job_type=job_type,
            video_url=video_url,
            weight_snapshot=latest_weight,
            hrv_snapshot=latest_hrv,
            workout_feedback_snapshot=latest_feedback,
        )

        return JsonResponse({
            "success": True,
            "job_id": job.id,
            "status": job.status,
            "attached_data": {
                "weight_snapshot": bool(latest_weight),
                "hrv_snapshot": bool(latest_hrv),
                "workout_feedback_snapshot": bool(latest_feedback),
            }
        }, status=201)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def run_job_view(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            job_id = data.get("job_id")
            if not job_id:
                return JsonResponse({"error": "job_id hiányzik"}, status=400)

            run_diagnostic_job(job_id)
            return JsonResponse({"success": True, "job_id": job_id})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "POST metódus szükséges"}, status=405)
