# diagnostics/analysis_views/single_leg_stance_views.py - EGYENLEG ELLENŐRZÉSSEL

import os
import json 
import logging
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required 
from django.urls import reverse
from django.conf import settings

from diagnostics_jobs.models import DiagnosticJob
from diagnostics_jobs.tasks import run_diagnostic_job 
from diagnostics.forms import SlsUploadForm 

# 🆕 ÚJ IMPORTOK
from billing.utils import dedicate_analysis, get_analysis_balance

logger = logging.getLogger(__name__)


def _create_and_enqueue_sls_job(user, job_type, video_url, notes):
    """
    Létrehoz egy DiagnosticJob-ot a megadott paraméterekkel és azonnal ütemezi.
    🆕 EGYENLEG LEVONÁSSAL!
    """
    # 1. Job létrehozása (PENDING)
    job = DiagnosticJob.objects.create(
        user=user,
        job_type=job_type,
        video_url=video_url,
        status=DiagnosticJob.JobStatus.PENDING 
    )
    
    # 🆕 2. ELEMZÉS LEVONÁSA
    success, new_balance = dedicate_analysis(user, job)
    
    if not success:
        job.status = DiagnosticJob.JobStatus.FAILED
        job.error_message = "Nem sikerült levonni az elemzést."
        job.save()
        raise ValueError(f"Egyenleg levonás sikertelen: {job.error_message}")
    
    # 3. Job ütemezése
    job.status = DiagnosticJob.JobStatus.QUEUED
    job.save()
    
    # Celery/Cloud Task indítása
    run_diagnostic_job.delay(job.id)
    
    return job, new_balance


@login_required
@require_http_methods(["GET", "POST"])
def single_leg_stance_upload_view(request):
    """
    Megjeleníti a feltöltő oldalt, és kezeli a SINGLE_LEG_STANCE videók feltöltését (Bal és Jobb).
    🆕 EGYENLEG ELLENŐRZÉSSEL!
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
            
            # 🆕 1. EGYENLEG ELLENŐRZÉSE (2 elemzésre van szükség!)
            current_balance = get_analysis_balance(user)
            
            if current_balance < 2:
                return JsonResponse({
                    'success': False, 
                    'error': 'INSUFFICIENT_BALANCE',
                    'message': f'Nincs elegendő elemzési egyenleged! Szükséges: 2 db, Jelenlegi: {current_balance} db',
                    'current_balance': current_balance
                }, status=402)
            
            # 2. Job indítása a bal oldalra (EGYENLEG LEVONÁSSAL)
            try:
                job_left, balance_after_left = _create_and_enqueue_sls_job(
                    user, 
                    DiagnosticJob.JobType.SINGLE_LEG_STANCE_LEFT, 
                    video_url_left, 
                    notes
                )
            except ValueError as e:
                return JsonResponse({
                    'success': False,
                    'error': 'DEDUCTION_FAILED',
                    'message': str(e)
                }, status=500)

            # 3. Job indítása a jobb oldalra (EGYENLEG LEVONÁSSAL)
            try:
                job_right, balance_after_right = _create_and_enqueue_sls_job(
                    user, 
                    DiagnosticJob.JobType.SINGLE_LEG_STANCE_RIGHT, 
                    video_url_right, 
                    notes
                )
            except ValueError as e:
                # Ha a második levonás sikertelen, az első job már lefutott
                # A visszatérítés automatikusan történik a tasks.py-ban, ha a job failed lesz
                return JsonResponse({
                    'success': False,
                    'error': 'DEDUCTION_FAILED',
                    'message': str(e)
                }, status=500)

            logger.info(f"💾 Két SLS Job sikeresen létrehozva: #{job_left.id} és #{job_right.id}")

            return JsonResponse({
                'success': True,
                'message': 'Két diagnosztikai feladat sikeresen elindítva.',
                'job_ids': [job_left.id, job_right.id],
                'redirect_url': reverse('diagnostics:athlete_diagnostics'),
                'remaining_balance': balance_after_right
            }, status=202) 

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Érvénytelen JSON formátum.'}, status=400)
        except Exception as e:
            logger.error(f"❌ Hiba a SLS job indításnál: {e}", exc_info=True)
            return JsonResponse({'error': f'Belső hiba a job indításakor: {e}'}, status=500)

    # GET kérésre a sablon megjelenítése
    context = {
        'form': SlsUploadForm(),
        # 🆕 Egyenleg hozzáadása
        'analysis_balance': get_analysis_balance(request.user)
    }
    return render(request, 'diagnostics/single_leg_stance_upload.html', context)