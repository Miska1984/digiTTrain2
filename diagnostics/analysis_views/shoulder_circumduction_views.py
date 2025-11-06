# diagnostics/analysis_views/shoulder_circumduction_views.py

import json 
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required 
from django.conf import settings

from diagnostics_jobs.models import DiagnosticJob
from diagnostics_jobs.cloud_tasks import enqueue_diagnostic_job
from diagnostics.forms import ShoulderCircumductionUploadForm # ❗ Ezt a Formot még létre kell hozni!
from diagnostics.analysis_views.squat_views import _process_video_upload


# ----------------------------------------------------------
# Segédfüggvény: Elemző Job létrehozása és indítása (GCS)
# ----------------------------------------------------------
@login_required
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
            gcs_object_key = data.get('video_url')
            notes = data.get('notes', '')

            if not gcs_object_key:
                return JsonResponse({"success": False, "error": "Hiányzó GCS videó URL."}, status=400)

            # 1. Abszolút URL létrehozása
            bucket_base_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/"
            full_video_url = f"{bucket_base_url}{gcs_object_key}"

            print(f"🔗 [Job Creation] GCS Objektum Kulcs: {gcs_object_key}")
            print(f"🔗 [Job Creation] Képzett TELJES URL: {full_video_url}")

            # 2. Job létrehozása
            job = DiagnosticJob.objects.create(
                user=request.user,
                job_type=job_type,
                video_url=full_video_url, 
                
                sport_type=sport_type,
                
            )
            print(f"✅ Job #{job.id} sikeresen létrehozva. Típus: {job_type}")

            # 3. Job ütemezése Cloud Task-ként
            try:
                # A Job típust adja át, hogy a cloud_tasks.py tudja, melyik service-t hívja:
                enqueue_diagnostic_job(job.id) 
                
                job.mark_as_queued()
                print(f"✅ Job #{job.id} sikeresen ütemezve.")

                return JsonResponse({
                    "success": True, 
                    "job_id": job.id, 
                    "message": f"Job #{job.id} létrehozva és ütemezve. Videó elmentve (GCS). Az elemzés elindult a háttérben!"
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
    
        # Rendereljük a feltöltő template-et
        return render(request, 'diagnostics/upload_shoulder_circumduction_video.html', { # ❗ Ezt a template-et is létre kell hozni!
            'form': form, 
            'title': title
        })


# ----------------------------------------------------------
# 1. Vállkörzés Elemzés View (Publikus)
# ----------------------------------------------------------

@login_required
@require_http_methods(["GET", "POST"])
def upload_shoulder_circumduction_video(request):
    """
    Vállkörzés mozgáselemző videó feltöltése és elemzés indítása.
    """
    
    # A közös logikát hívjuk a Squat view-ból, de a saját paramétereinkkel
    return _process_video_upload(
        request, 
        form_class=ShoulderCircumductionUploadForm,
        job_type=DiagnosticJob.JobType.SHOULDER_CIRCUMDUCTION,
        title="Vállkörzés Biomechanika Elemzés",
        sport_type="general" 
    )
