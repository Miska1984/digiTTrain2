# diagnostics/analysis_views/vertical_jump_views.py

import os
import json 
import logging
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required 
from django.urls import reverse # Szükséges a redirect URL-hez

from diagnostics_jobs.models import DiagnosticJob
from diagnostics_jobs.cloud_tasks import enqueue_diagnostic_job
# ❗ Importáljuk az új formot
from diagnostics.forms import VerticalJumpDiagnosticUploadForm 

logger = logging.getLogger(__name__)

# ----------------------------------------------------------
# Segédfüggvény: Elemző Job létrehozása és indítása (GCS)
# (Másolva a squat_views.py-ból, hogy a fájl önállóan működjön)
# ----------------------------------------------------------
def _process_video_upload(request, form_class, job_type, title, sport_type="general"):
    """
    Közös logika a Job létrehozásához, miután a frontend közvetlenül a GCS-re töltött fel.
    A POST kérésben JSON-ként érkező video_url-t használja.
    """
    logger.info(f"\n======== {title} Job Létrehozás (GCS URL-lel) JobType: {job_type} ========")

    if request.method == "POST":
        try:
            # POST adatok JSON-ként való olvasása (a frontend AJAX hívásából)
            data = json.loads(request.body)
            
            # A form validálása a nem-JSON adatokra (pl. notes)
            # A JS-ből érkező 'video_url' mezőt is hozzáadjuk a validáláshoz
            form = form_class({'video_url': data.get('video_url')})
            
            if form.is_valid():
                video_url = data.get('video_url')
                
                
                if not video_url:
                    return JsonResponse({"success": False, "error": "Hiányzó video_url a feltöltés után."}, status=400)
                
                # 1. Job létrehozása adatbázisban
                job = DiagnosticJob.objects.create(
                    user=request.user,
                    job_type=job_type,
                    status=DiagnosticJob.JobStatus.PENDING,
                    video_url=video_url, # A GCS public/signed URL
                    sport_type=sport_type,
                    # Nincs szükség a `video_file` mezőre, mert a GCS-t használjuk
                )
                
                logger.info(f"💾 Job #{job.id} sikeresen létrehozva. Típus: {job_type}")

                # 2. Celery/Cloud Task ütemezése
                enqueue_diagnostic_job(job.id) # Vagy: run_diagnostic_job.delay(job.id)
                logger.info(f"⏳ Job #{job.id} ütemezve (Cloud Task/Celery).")

                # Siker esetén visszatérés JSON-nel (ezt várja a JS)
                return JsonResponse({
                    "success": True, 
                    "job_id": job.id, 
                    "redirect_url": reverse('diagnostics:athlete_diagnostics')
                })

            # Form hibák kezelése
            errors = dict(form.errors)
            logger.warning(f"❌ Form validációs hiba: {errors}")
            return JsonResponse({"success": False, "error": f"Validációs hiba: {errors}"}, status=400)

        except Exception as e:
            # Általános hiba a Job létrehozásakor vagy ütemezésekor
            logger.error(f"❌ Kritikus hiba a Job létrehozásakor/ütemezésekor: {e}", exc_info=True)
            return JsonResponse({"success": False, "error": f"Hiba az elemzés indításakor: {e}"}, status=500)
    
    else:  # GET request (űrlap megjelenítése)
        form = form_class()
    
        # Rendereljük a feltöltő template-et
        return render(request, 'diagnostics/upload_vertical_jump_video.html', {
            'form': form, 
            'title': title
        })
        
# ----------------------------------------------------------
# 2. Vertical Jump Elemzés View
# ----------------------------------------------------------

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