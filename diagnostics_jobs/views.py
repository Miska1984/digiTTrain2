from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .tasks import run_diagnostic_job

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
