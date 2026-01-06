import json
import os
import logging
from django.http import JsonResponse, HttpResponseBadRequest, Http404
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods

# Modulok
from diagnostics_jobs.models import DiagnosticJob
from diagnostics_jobs.cloud_tasks import enqueue_diagnostic_job
from diagnostics_jobs.tasks import run_diagnostic_job

# Billing rendszer
from django.db import transaction
from billing.utils import (
    refund_analysis, 
    get_analysis_balance, 
    dedicate_analysis, 
    has_active_subscription
)
from .utils.gcs_signer import generate_signed_upload_url

User = get_user_model()
logger = logging.getLogger(__name__)

# --- API NÉZETEK ---

@login_required
@csrf_exempt 
@require_http_methods(["POST"])
def get_signed_gcs_url(request):
    """
    Visszaad egy aláírt URL-t a feltöltéshez, DE előtte ellenőrzi az egyenleget.
    """
    # --- 1. BILLING ELLENŐRZÉS ---
    balance = get_analysis_balance(request.user)
    if balance <= 0:
        return JsonResponse({
            "success": False, 
            "error": "INSUFFICIENT_BALANCE", 
            "message": "Nincs elég elemzési kereted a feltöltéshez!"
        }, status=403)

    # --- 2. ADATOK BEOLVASÁSA (Eredeti logikád alapján) ---
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"success": False, "error": "Hibás JSON formátum."}, status=400)

    # Paraméterek kinyerése (ahogy az eredetiben volt)
    file_name_from_squat = data.get('file_name')
    file_name_from_other = data.get('filename')
    
    filename = str(file_name_from_squat or file_name_from_other or '').strip()
    content_type = str(data.get('content_type', '')).strip()
    
    if not filename or not content_type:
        return JsonResponse({"success": False, "error": "Hiányzó fájlnév vagy tartalomtípus."}, status=400)

    # --- 3. ALÁÍRÁS GENERÁLÁSA ---
    try:
        # Itt hívjuk a segédfüggvényedet
        result = generate_signed_upload_url(filename, content_type)
        
        # Ha a signer belső hibát dobott
        if not result.get("success"):
            return JsonResponse(result, status=500)

        # ✅ SIKER: Visszaadjuk a TELJES result-ot, ahogy a frontend várja
        # A result tartalma: {'success': True, 'signed_url': '...', 'file_name': '...', 'public_url': '...'}
        return JsonResponse(result, status=200)

    except Exception as e:
        logger.critical(f"❌ Hiba a GCS aláíráskor: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def create_diagnostic_job(request):
    """
    Új diagnosztikai feladat indítása a videó feltöltése után.
    """
    try:
        data = json.loads(request.body)
        
        # 1. BIZTONSÁGI BLOKK (Levonás és mentés)
        with transaction.atomic():
            # Levonjuk az elemzést (itt a dedicate_analysis már az egységeket nézi!)
            success, result_val = dedicate_analysis(request.user)
            
            if not success:
                return JsonResponse({
                    "success": False, 
                    "error": "INSUFFICIENT_BALANCE",
                    "message": "Nincs több elemzési egységed!"
                }, status=403)

            # Létrehozzuk a rekordot PENDING-ben
            job = DiagnosticJob.objects.create(
                user=request.user,
                video_url=data.get("video_url"),
                job_type=data.get("job_type", "MOVEMENT_ASSESSMENT"),
                status=DiagnosticJob.JobStatus.PENDING
            )

        # 2. ÜTEMEZÉS (A tranzakción kívül)
        try:
            if settings.USE_CLOUD_TASKS:
                enqueue_diagnostic_job(job.id)
            else:
                run_diagnostic_job.delay(job.id)
                
            return JsonResponse({
                "success": True, 
                "job_id": job.id, 
                "remaining_balance": result_val
            })

        except Exception as task_error:
            # REFUND: Ha a technika elbukik, visszaadjuk a pontot
            logger.error(f"Feldolgozó indítási hiba: {task_error}")
            refund_analysis(request.user, reason=f"Rendszerhiba az indításkor (Job: {job.id})")
            
            job.status = DiagnosticJob.JobStatus.FAILED
            job.error_message = f"Indítási hiba: {str(task_error)}"
            job.save(update_fields=['status', 'error_message'])
            
            return JsonResponse({
                "success": False, 
                "error": "Ütemezési hiba történt, a kreditet visszakaptad."
            }, status=500)

    except Exception as e:
        logger.exception("Hiba a diagnostics create_job nézetben")
        return JsonResponse({"success": False, "error": "Kritikus rendszerhiba."}, status=500)

@login_required
def run_diagnostic_job_view(request):
    # Ezt a nézetet általában a manuális indításhoz használjuk
    return JsonResponse({"status": "A jobok automatikusan indulnak a feltöltés után."})

@login_required
def job_status(request, job_id):
    job = get_object_or_404(DiagnosticJob, id=job_id, user=request.user)
    return JsonResponse({
        "status": job.status,
        "progress": job.progress,
        "is_finished": job.status in [DiagnosticJob.JobStatus.COMPLETED, DiagnosticJob.JobStatus.FAILED]
    })

# --- LISTÁZÁS ÉS DASHBOARD ---

@login_required
def list_diagnostic_jobs(request):
    jobs = DiagnosticJob.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'diagnostics/job_list.html', {'jobs': jobs})

@login_required
def diagnostics_dashboard(request):
    """
    A sportoló fő diagnosztikai felülete (UI).
    """
    from billing.utils import get_analysis_balance
    
    # 1. Lekérjük az adatokat (fontos a sorrend: legfrissebb felül)
    jobs_to_show = DiagnosticJob.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    # 2. Elemzési egyenleg lekérése
    analysis_balance = get_analysis_balance(request.user)
    
    # 3. Átadás a sablonnak
    return render(request, 'diagnostics/athlete_diagnostics.html', {
        'title': 'Sportoló Diagnosztikai Dashboard',
        'job_list': jobs_to_show,        # 👈 EZ A KULCS! Így a HTML látni fogja
        'analysis_balance': analysis_balance,
    })

@login_required
def sport_diagnostics_list(request):
    has_ml = has_active_subscription(request.user, 'ML_ACCESS')
    # Itt a korábbi logika szerint gyűjtheted a sportokat...
    return render(request, 'diagnostics/sport_list.html', {'has_ml_access': has_ml})