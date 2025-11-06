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
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from diagnostics_jobs.models import DiagnosticJob
from diagnostics_jobs.cloud_tasks import enqueue_diagnostic_job
from diagnostics_jobs.tasks import run_diagnostic_job
from billing.models import UserCreditBalance, AlgorithmPricing, TransactionHistory
from .utils.gcs_signer import generate_signed_upload_url
from django.views.decorators.http import require_http_methods

User = get_user_model()
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------
# 🆕 ÚJ: GCS Signed URL generálása a feltöltéshez
# ----------------------------------------------------------------

@login_required
@csrf_exempt 
@require_http_methods(["POST"])
def get_signed_gcs_url(request):
    """
    Visszaad egy aláírt URL-t a fájl GCS-re való feltöltéséhez a frontend számára.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Érvénytelen metódus."}, status=405)

    # 1. JSON adatok feldolgozása (hibatűrő módon)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.error("GCS Sign hiba: Hibás JSON formátum vagy kódolás.")
        return JsonResponse({"success": False, "error": "Hibás JSON formátum."}, status=400)

    # 2. PARAMÉTEREK KINYERÉSE ÉS TISZTÍTÁSA
    # ❗ KRITIKUS JAVÍTÁS: A frontend 'filename'-t küld, ezt használjuk, és eltávolítjuk a szóközöket.
    file_name_from_squat = data.get('file_name')
    file_name_from_other = data.get('filename')
    
    filename = str(file_name_from_squat or file_name_from_other or '').strip()
    content_type = str(data.get('content_type', '')).strip()
    
    logger.info(f"GCS Sign kérés adatok (tisztított): {{'filename': '{filename}', 'content_type': '{content_type}'}}")
    
    # 3. Kötelező adatok ellenőrzése
    if len(filename) == 0 or len(content_type) == 0:
        logger.error(f"GCS Sign hiba: Hiányzó vagy üres paraméterek. Bejövő adatok: {data}")
        return JsonResponse({"success": False, "error": "Hiányzó fájlnév vagy tartalomtípus."}, status=400)

    # 4. Aláírt URL generálása
    try:
        # A generate_signed_upload_url függvény a 'filename'-t várja (ami az útvonal kulcsa lesz)
        result = generate_signed_upload_url(filename, content_type)
        
        if not result.get("success"):
            logger.error(f"GCS aláírás hiba a signer-ben: {result.get('error')}")
            # Belső szerverhiba esetén 500-at adunk vissza
            return JsonResponse({"success": False, "error": result.get("error", "Ismeretlen GCS hiba a signerben.")}, status=500)

        # Sikeres válasz
        logger.info(f"✅ GCS aláírt URL sikeresen generálva: {result.get('file_name')}")
        return JsonResponse(result, status=200)

    except FileNotFoundError as e:
        logger.error(f"GCS Service Account hiba: {e}")
        return JsonResponse({"success": False, "error": "Konfigurációs hiba: GCS kulcs nem található."}, status=500)
    except Exception as e:
        logger.critical(f"❌ Váratlan hiba a GCS aláíráskor: {e}", exc_info=True)
        return JsonResponse({"success": False, "error": "Váratlan szerverhiba az URL generálásakor."}, status=500)


# -----------------------------------------------------------
# API VÉGPONTOK (Változatlanul hagyva a kényelem kedvéért)
# -----------------------------------------------------------

@csrf_exempt
def create_diagnostic_job(request):
    """
    Új diagnosztikai feladat létrehozása (API hívás).
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST metódus szükséges"}, status=405)

    try:
        data = json.loads(request.body)
        user_id = data.get("user_id")
        sport_type = data.get("sport_type", "general")
        job_type = data.get("job_type", "general")
        gcs_object_key = data.get("video_url")
        notes = data.get("notes", "")
        
        # Kredit ellenőrzés és levonás logikája (a feltöltött fájl alapján)
        try:
            # Feltételezés: Az AlgorithmPricing modell tartalmazza a get_from_job_type metódust
            algorithm_type = AlgorithmPricing.AlgorithmType.get_from_job_type(job_type)
            pricing = AlgorithmPricing.objects.get(algorithm_type=algorithm_type)
            
            if not UserCreditBalance.can_afford(user_id, pricing.credit_cost):
                return JsonResponse({"success": False, "error": "Nincs elegendő kredit a művelethez."}, status=403)
                
            UserCreditBalance.deduct_credits(user_id, pricing.credit_cost, f"{job_type} elemzés indítása")

        except AlgorithmPricing.DoesNotExist:
            # Ezt a birkózás miatt vesszük ki, ha a sport_type nincs még beárazva
            if job_type == DiagnosticJob.JobType.WRESTLING:
                 pass # Ideiglenes engedélyezés, amíg a birkózás kikerül a rendszerből
            else:
                return JsonResponse({"success": False, "error": f"Nincs ár beállítva az algoritmushoz: {job_type}"}, status=400)
        except Exception as e:
            return JsonResponse({"success": False, "error": f"Hiba a kredit kezelés során: {str(e)}"}, status=500)

        if not all([user_id, sport_type, job_type, gcs_object_key]): # 🟢 Ellenőrzés gcs_object_key-re
            return JsonResponse({"success": False, "error": "Hiányzó kötelező mező (user_id, job_type, video_url/GCS kulcs)"}, status=400)

        user = User.objects.filter(id=user_id).first()
        if not user:
             return JsonResponse({"success": False, "error": "A felhasználó nem található"}, status=404)

        GCS_BUCKET_NAME = settings.GS_BUCKET_NAME
        full_video_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{gcs_object_key}"

        job = DiagnosticJob.objects.create(
            user=user,
            sport_type=sport_type,
            job_type=job_type,
            video_url=full_video_url, # ⬅️ EZT AZ ABSZOLÚT URL-T KELL MENTENI!
            notes=notes,
            status=DiagnosticJob.JobStatus.PENDING,
        )

        # Aszinkron task indítása
        try:
            if settings.ENABLE_CLOUD_TASKS:
                enqueue_diagnostic_job(job.id)
            else:
                run_diagnostic_job(job.id)

        except Exception as e:
            job.mark_as_failed(f"Hiba az indításkor: {str(e)}")
            return JsonResponse({"success": False, "error": f"Hiba a feladat indításakor: {str(e)}"}, status=500)


        return JsonResponse({
            "success": True, 
            "message": "A diagnosztikai feladat elküldve feldolgozásra.",
            "job_id": job.id,
            "status": job.status,
            "job_type": job.job_type,
        }, status=201)

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Érvénytelen JSON formátum"}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": f"Ismeretlen hiba: {str(e)}"}, status=500)
        
# -----------------------------------------------------------

@csrf_exempt
def run_diagnostic_job_view(request):
    """
    HTTP hívás a job indításához (pl. Cloud Task-ból vagy lokális teszteléshez).
    """
    if request.method != "POST":
        return HttpResponseBadRequest("Csak POST metódus engedélyezett.")

    try:
        data = json.loads(request.body)
        job_id = data.get("job_id")
        
        if not job_id:
            return HttpResponseBadRequest("Hiányzó 'job_id' mező.")

        job = get_object_or_404(DiagnosticJob, id=job_id)
        
        run_diagnostic_job(job.id)

        return JsonResponse({"success": True, "message": f"Diagnostic Job #{job_id} elindítva."})
    
    except Http404: 
        return JsonResponse({"success": False, "error": f"Diagnostic Job #{job_id} nem található."}, status=404)
    except Exception as e:
        return JsonResponse({"success": False, "error": f"Hiba a feladat futtatásakor: {str(e)}"}, status=500)
        
# -----------------------------------------------------------

@login_required
def job_status(request, job_id):
    """
    Visszaadja egy diagnosztikai feladat aktuális állapotát (AJAX híváshoz).
    """
    try:
        job = DiagnosticJob.objects.get(id=job_id)
        
        # A felhasználói jogosultságok ellenőrzése (ha szükséges)
        # ...

        return JsonResponse({
            "job_id": job.id,
            "status": job.status,
            "status_display": job.get_status_display(),
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "error_message": job.error_message,
            "video_url": job.video_url,
            "job_type": job.job_type,
            "pdf_path": job.pdf_path, 
            "result": job.result,
        })

    except DiagnosticJob.DoesNotExist:
        return JsonResponse({"error": f"Diagnostic Job #{job_id} nem található."}, status=404)
        
# -----------------------------------------------------------

@login_required
def list_diagnostic_jobs(request):
    """
    Az aktuális felhasználó vagy az általa edzett sportolók diagnosztikai feladatainak listája (JSON/AJAX).
    """
    # 💡 Ideális esetben a jogosultsági logika itt van
    jobs = DiagnosticJob.objects.filter(user=request.user).order_by('-created_at')

    data = [{
        "id": job.id,
        "created_at": job.created_at,
        "job_type": job.get_job_type_display(),
        "sport_type": job.sport_type,
        "status": job.status,
        "status_display": job.get_status_display(),
        "pdf_path": job.pdf_path,
        "result": job.result,
        "notes": job.notes,
    } for job in jobs]

    return JsonResponse({"jobs": data})


# -----------------------------------------------------------
# FELHASZNÁLÓI INTERFÉSZ VIEWS
# -----------------------------------------------------------

# ❌ ELAVULT FELTÖLTŐ VIEWS (pl. upload_wrestling_video, upload_general_video) - TÖRÖLVE!
# Ezek már átkerültek a dedikált fájlokba, mint a squat_posture_views.py.


@login_required
def diagnostics_dashboard(request):
    """
    A sportoló fő diagnosztikai felülete (UI).
    """
    # Lekérjük a bejelentkezett felhasználó összes diagnosztikai feladatát
    job_list = DiagnosticJob.objects.filter(
        user=request.user
    ).order_by('-created_at')  # Legújabb legyen elől
    
    return render(request, 'diagnostics/athlete_diagnostics.html', {
        'title': 'Sportoló Diagnosztikai Dashboard',
        'job_list': job_list,  # ✅ EZ HIÁNYZOTT!
    })

# -----------------------------------------------------------

@login_required
def sport_diagnostics_list(request):
    """
    Listázza azokat a sportspecifikus elemzéseket, amelyekre a felhasználónak van jogosultsága.
    """
    # ❌ TÖRÖLVE: 'wrestling' elemzés, mert ezt kivezettük
    SPORT_ANALYSES = {
        'football': {'name': 'Labdarúgás: Rúgástechnika', 'url_name': 'diagnostics:upload_football_kick_video', 'icon': '⚽', 'description': 'Rúgás biomechanikai elemzése, sérüléskockázat felmérése.'},
        'handball': {'name': 'Kézilabda: Dobástechnika', 'url_name': 'diagnostics:upload_handball_throw_video', 'icon': '🤾', 'description': 'Vállmobilitás és dobómozgás láncának vizsgálata.'},
        'judo': {'name': 'Judo: Eséstechnika', 'url_name': 'diagnostics:upload_judo_fall_video', 'icon': '🥋', 'description': 'Esés közbeni ízületi pozíciók és szimmetria elemzése.'},
    }
    
    sports_with_diagnostics = []
    
    user_roles = request.user.user_roles.filter(status='approved').select_related('sport').distinct()
    
    for role in user_roles:
        if role.sport:
            sport_slug = getattr(role.sport, 'slug', role.sport.name.lower().replace(' ', '_'))
            
            if sport_slug in SPORT_ANALYSES:
                sports_with_diagnostics.append(SPORT_ANALYSES[sport_slug])

    unique_sports = {s['url_name']: s for s in sports_with_diagnostics}.values()

    return render(request, 'diagnostics/sport_diagnostics_list.html', {
        'sports_with_diagnostics': unique_sports,
        'title': 'Sportspecifikus Elemzések',
    })


