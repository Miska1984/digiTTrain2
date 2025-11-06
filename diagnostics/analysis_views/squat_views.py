# diagnostics/analysis_views/squat_views.py - GCS Kompatibilis Változat (Javított, Abszolút URL-lel)

import os
import json # Szükséges a JSON adatok olvasásához
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required 
from django.conf import settings # 🆕 Új import a GS_BUCKET_NAME eléréséhez

from diagnostics_jobs.models import DiagnosticJob
from diagnostics_jobs.cloud_tasks import enqueue_diagnostic_job
from diagnostics.forms import SquatDiagnosticUploadForm
from diagnostics.utils.video_handler import handle_uploaded_video # Nem kell a GCS miatt

# ----------------------------------------------------------
# Segédfüggvény: Elemző Job létrehozása és indítása (GCS)
# ----------------------------------------------------------
def _process_video_upload(request, form_class, job_type, title, sport_type="general"):
    """
    Közös logika a Job létrehozásához, miután a frontend közvetlenül a GCS-re töltött fel.
    A POST kérésben JSON-ként érkező video_url-t használja.
    """
    print(f"\n======== {title} Job Létrehozás (GCS URL-lel) ========")

    if request.method == "POST":
        try:
            # POST adatok JSON-ként való olvasása (a frontend AJAX hívásából)
            data = json.loads(request.body)

            print(f"🔗 [DEBUG] Fogadott JSON adat: {data}")

            # A gcs_object_name csak a relatív GCS útvonal (pl.: videos/uploads/...):
            gcs_object_key = data.get('video_url') 
            
            if not gcs_object_key:
                raise ValueError("A feltöltött videó GCS útvonala (video_url) hiányzik a kérésben. Ellenőrizd a frontend JSON kulcsát.")

            # ✅ JAVÍTÁS: A TELJES ABSZOLÚT URL KÉPZÉSE!
            # A settings.MEDIA_URL (pl. https://.../media/dev/ ) és a relatív útvonal összefűzése.
            bucket_base_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/"
            full_video_url = f"{bucket_base_url}{gcs_object_key}"

            print(f"🔗 [Job Creation] GCS Objektum Kulcs: {gcs_object_key}")
            print(f"🔗 [Job Creation] Képzett TELJES URL: {full_video_url}")

            notes = data.get('notes', '...')

            # 1. DiagnosticJob létrehozása
            job = DiagnosticJob.objects.create(
                user=request.user,
                sport_type=sport_type,
                job_type=job_type,
                # 🚨 A JAVÍTOTT, TELJES URL mentése a video_url mezőbe!
                video_url=full_video_url, 
            )  # A 'notes' mező továbbra is kihagyva!
        
            print(f"✅ Job #{job.id} létrehozva: {job.job_type}")
            
            # 2. Elemzés indítása (GCP Cloud Task / Helyi Celery)
            try:
                enqueue_diagnostic_job(job.id)
                
                # SIKER ESETÉN MÁR JSON-T AD VISSZA
                return JsonResponse({
                    "success": True, 
                    "job_id": job.id, 
                    "message": "✅ Videó feltöltve (GCS). Az elemzés elindult a háttérben!"
                }, status=201)
                
            except Exception as e:
                # Ha az ütemezés sikertelen
                job.mark_as_failed(f"Hiba az ütemezés közben: {e}")
                print(f"❌ Hiba történt az ütemezés közben: {e}")
                return JsonResponse({
                    "success": False, 
                    "error": f"Hiba az elemzés indításakor: {e}"
                }, status=500)

        except json.JSONDecodeError:
            return JsonResponse({"success": False, "error": "Hibás JSON formátum."}, status=400)
        except Exception as e:
            print(f"❌ Hiba történt a Job létrehozásakor/ütemezésekor: {e}")
            return JsonResponse({"success": False, "error": f"Hiba az elemzés indításakor: {e}"}, status=500)
    
    else:  # GET request (űrlap megjelenítése)
        form = form_class()
    
        # Rendereljük a squat feltöltő template-et
        return render(request, 'diagnostics/upload_squat_video.html', {
            'form': form, 
            'title': title
        })

# ----------------------------------------------------------
# 1. Guggolás Elemzés View (Publikus)
# ----------------------------------------------------------

@login_required
@require_http_methods(["GET", "POST"])
def upload_squat_video(request):
    """
    Guggolás mozgáselemző videó feltöltése és elemzés indítása.
    """
    return _process_video_upload(
        request, 
        form_class=SquatDiagnosticUploadForm,
        job_type=DiagnosticJob.JobType.SQUAT_ASSESSMENT,
        title="Guggolás Értékelés",
        sport_type="general" 
    )