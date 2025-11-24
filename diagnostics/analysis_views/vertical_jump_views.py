# diagnostics/analysis_views/vertical_jump_views.py - EGYENLEG ELLENŐRZÉSSEL

import os
import json 
import logging
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required 
from django.urls import reverse
from django.conf import settings

from diagnostics_jobs.models import DiagnosticJob
from diagnostics_jobs.cloud_tasks import enqueue_diagnostic_job
from diagnostics.forms import VerticalJumpDiagnosticUploadForm 

# 🆕 ÚJ IMPORTOK
from billing.utils import dedicate_analysis, get_analysis_balance

logger = logging.getLogger(__name__)


def _process_video_upload(request, form_class, job_type, title, sport_type="general"):
    """
    Közös logika a Job létrehozásához, egyenleg ellenőrzéssel és levonással.
    """
    logger.info(f"\n======== {title} Job Létrehozás (GCS URL-lel) JobType: {job_type} ========")

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            
            # Form validálása
            form = form_class({'video_url': data.get('video_url')})
            
            if form.is_valid():
                video_url = data.get('video_url')
                
                if not video_url:
                    return JsonResponse({"success": False, "error": "Hiányzó video_url a feltöltés után."}, status=400)
                
                # 🆕 1. EGYENLEG ELLENŐRZÉSE
                current_balance = get_analysis_balance(request.user)
                
                if current_balance < 1:
                    return JsonResponse({
                        'success': False, 
                        'error': 'INSUFFICIENT_BALANCE',
                        'message': 'Nincs elegendő elemzési egyenleged!',
                        'current_balance': current_balance
                    }, status=402)
                
                # 2. Job létrehozása (PENDING)
                job = DiagnosticJob.objects.create(
                    user=request.user,
                    job_type=job_type,
                    status=DiagnosticJob.JobStatus.PENDING,
                    video_url=video_url,
                    sport_type=sport_type,
                )
                
                logger.info(f"💾 Job #{job.id} sikeresen létrehozva. Típus: {job_type}")

                # 🆕 3. ELEMZÉS LEVONÁSA
                success, new_balance = dedicate_analysis(request.user, job)
                
                if not success:
                    job.status = DiagnosticJob.JobStatus.FAILED
                    job.error_message = "Nem sikerült levonni az elemzést."
                    job.save()
                    return JsonResponse({
                        'success': False,
                        'error': 'DEDUCTION_FAILED',
                        'message': job.error_message
                    }, status=500)

                # 4. Job ütemezése
                job.status = DiagnosticJob.JobStatus.QUEUED
                job.save()
                
                enqueue_diagnostic_job(job.id)
                logger.info(f"⏳ Job #{job.id} ütemezve (Cloud Task/Celery).")

                # Siker esetén visszatérés JSON-nel
                return JsonResponse({
                    "success": True, 
                    "job_id": job.id, 
                    "redirect_url": reverse('diagnostics:athlete_diagnostics'),
                    "remaining_balance": new_balance
                })

            # Form hibák kezelése
            errors = dict(form.errors)
            logger.warning(f"❌ Form validációs hiba: {errors}")
            return JsonResponse({"success": False, "error": f"Validációs hiba: {errors}"}, status=400)

        except Exception as e:
            logger.error(f"❌ Kritikus hiba a Job létrehozásakor/ütemezésekor: {e}", exc_info=True)
            return JsonResponse({"success": False, "error": f"Hiba az elemzés indításakor: {e}"}, status=500)
    
    else:  # GET request (űrlap megjelenítése)
        form = form_class()
        
        # 🆕 Egyenleg hozzáadása a template-hez
        context = {
            'form': form, 
            'title': title,
            'analysis_balance': get_analysis_balance(request.user)
        }
        return render(request, 'diagnostics/upload_vertical_jump_video.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def upload_vertical_jump_video(request):
    """
    Helyből Magassági Ugrás elemző videó feltöltése és elemzés indítása.
    """
    return _process_video_upload(
        request, 
        form_class=VerticalJumpDiagnosticUploadForm, 
        job_type=DiagnosticJob.JobType.VERTICAL_JUMP, 
        title="Helyből Magassági Ugrás Biomechanika (Vertical Jump)",
        sport_type="general" 
    )