# diagnostics/analysis_views/posture_views.py - EGYENLEG ELLENŐRZÉSSEL

import os
import json 
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required 
from django.conf import settings

from diagnostics_jobs.models import DiagnosticJob
from diagnostics_jobs.cloud_tasks import enqueue_diagnostic_job
from diagnostics.forms import PostureDiagnosticUploadForm

# 🆕 ÚJ IMPORTOK
from billing.utils import dedicate_analysis, get_analysis_balance


@login_required
def _process_video_upload(request, form_class, job_type, title, sport_type="general"):
    """
    Közös logika a Job létrehozásához, egyenleg ellenőrzéssel és levonással.
    """
    print(f"\n======== {title} Job Létrehozás (GCS URL-lel) ========")

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            gcs_object_key = data.get('video_url', None)
            
            if not gcs_object_key:
                raise ValueError("A feltöltött videó GCS útvonala hiányzik.")

            # 🆕 1. EGYENLEG ELLENŐRZÉSE
            current_balance = get_analysis_balance(request.user)
            
            if current_balance < 1:
                return JsonResponse({
                    'success': False, 
                    'error': 'INSUFFICIENT_BALANCE',
                    'message': 'Nincs elegendő elemzési egyenleged!',
                    'current_balance': current_balance
                }, status=402)

            # Teljes URL képzése
            bucket_base_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/"
            full_video_url = f"{bucket_base_url}{gcs_object_key}"

            print(f"📗 [Job Creation] Teljes URL: {full_video_url}")

            # 2. Job létrehozása (PENDING)
            job = DiagnosticJob.objects.create(
                user=request.user,
                sport_type=sport_type,
                job_type=job_type,
                video_url=full_video_url,
                status=DiagnosticJob.JobStatus.PENDING,
            )
            print(f"✅ Job #{job.id} létrehozva: {job.job_type}")
            
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
            
            try:
                enqueue_diagnostic_job(job.id)
                
                return JsonResponse({
                    "success": True, 
                    "job_id": job.id, 
                    "message": "✅ Videó feltöltve (GCS). Az elemzés elindult!",
                    "remaining_balance": new_balance
                }, status=201)
                
            except Exception as e:
                job.mark_as_failed(f"Hiba az ütemezés közben: {e}")
                print(f"❌ Hiba az ütemezés közben: {e}")
                
                # 🆕 VISSZATÉRÍTÉS automatikusan a tasks.py-ban történik
                
                return JsonResponse({
                    "success": False, 
                    "error": f"Hiba az elemzés indításakor: {e}"
                }, status=500)

        except json.JSONDecodeError:
            return JsonResponse({"success": False, "error": "Hibás JSON formátum."}, status=400)
        except Exception as e:
            print(f"❌ Hiba: {e}")
            return JsonResponse({"success": False, "error": f"Hiba: {e}"}, status=500)
    
    else:  # GET
        form = form_class()
        
        # 🆕 Egyenleg hozzáadása a template-hez
        context = {
            'form': form, 
            'title': title,
            'analysis_balance': get_analysis_balance(request.user)
        }
        return render(request, 'diagnostics/upload_posture_video.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def upload_posture_video(request):
    """Testtartás elemző videó feltöltése és elemzés indítása."""
    return _process_video_upload(
        request, 
        form_class=PostureDiagnosticUploadForm,
        job_type=DiagnosticJob.JobType.POSTURE_ASSESSMENT,
        title="Testtartás Értékelés",
        sport_type="general" 
    )