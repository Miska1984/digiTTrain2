# diagnostics/analysis_views/single_leg_stance_views.py

import os
import json 
import logging
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required 
from django.urls import reverse

from diagnostics_jobs.models import DiagnosticJob
from diagnostics_jobs.tasks import run_diagnostic_job 
from diagnostics.forms import SlsUploadForm 

logger = logging.getLogger(__name__)


# ----------------------------------------------------------
# 🆕 ÚJ SEGÉDFÜGGVÉNY: Egy job létrehozása és ütemezése (SLS-specifikus)
# ----------------------------------------------------------
def _create_and_enqueue_sls_job(user, job_type, video_url, notes):
    """Létrehoz egy DiagnosticJob-ot a megadott paraméterekkel és azonnal ütemezi."""
    job = DiagnosticJob.objects.create(
        user=user,
        job_type=job_type,
        video_url=video_url,
        # A legutóbbi javítás a JobStatus konstansra
        status=DiagnosticJob.JobStatus.PENDING 
    )
    # Celery/Cloud Task indítása
    run_diagnostic_job.delay(job.id)
    return job


# ----------------------------------------------------------
# Fő View Függvény (átalakítva a segédfüggvény használatára)
# ----------------------------------------------------------
@login_required
@require_http_methods(["GET", "POST"])
def single_leg_stance_upload_view(request):
    """
    Megjeleníti a feltöltő oldalt, és kezeli a SINGLE_LEG_STANCE videók feltöltését (Bal és Jobb) JSON payload alapján.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            video_url_left = data.get('video_url_left')
            video_url_right = data.get('video_url_right')
            notes = data.get('notes', '')
            user = request.user

            if not video_url_left or not video_url_right:
                 return JsonResponse({'error': 'Hiányzik a bal vagy jobb oldali videó URL a JSON payload-ban.'}, status=400)
            
            # 2. Job indítása a bal oldalra (SEGÉDFÜGGVÉNYT HASZNÁLVA)
            job_left = _create_and_enqueue_sls_job(
                user, 
                DiagnosticJob.JobType.SINGLE_LEG_STANCE_LEFT, 
                video_url_left, 
                notes
            )

            # 3. Job indítása a jobb oldalra (SEGÉDFÜGGVÉNYT HASZNÁLVA)
            job_right = _create_and_enqueue_sls_job(
                user, 
                DiagnosticJob.JobType.SINGLE_LEG_STANCE_RIGHT, 
                video_url_right, 
                notes
            )

            logger.info(f"💾 Két SLS Job sikeresen létrehozva: #{job_left.id} és #{job_right.id}")

            return JsonResponse({
                'success': True,
                'message': 'Két diagnosztikai feladat sikeresen elindítva.',
                'job_ids': [job_left.id, job_right.id],
                'redirect_url': reverse('diagnostics:athlete_diagnostics') 
            }, status=202) 

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Érvénytelen JSON formátum.'}, status=400)
        except Exception as e:
            logger.error(f"❌ Hiba a SLS job indításnál: {e}", exc_info=True)
            return JsonResponse({'error': f'Belső hiba a job indításakor: {e}'}, status=500)

    # GET kérésre a sablon megjelenítése
    context = {'form': SlsUploadForm()} 
    return render(request, 'diagnostics/single_leg_stance_upload.html', context)