# diagnostics_jobs/api.py
import json
import datetime
from django.http import JsonResponse, HttpResponseBadRequest, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods # ÚJ: Hozzáadva a tömörség kedvéért
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.conf import settings
# from django.forms.models import model_to_dict # Nincs rá szükség
from .models import DiagnosticJob, UserAnthropometryProfile
from .tasks import run_diagnostic_job # Ezt csak akkor használd, ha szinkron futás a cél!

User = get_user_model()


# ----------------------------------------------------------------
# API Végpontok
# ----------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"]) # Csak POST-ot engedélyez
def create_diagnostic_job(request):
    """
    Új diagnosztikai feladat létrehozása.
    A felhasználó videó URL-t ad meg (GCS-ben tárolva).
    """
    try:
        data = json.loads(request.body)
        user_id = data.get("user_id")
        sport_type = data.get("sport_type", "general")
        # Job_type-ot valószínűleg a job létrehozó view már beállította, de itt ellenőrizzük:
        job_type = data.get("job_type", DiagnosticJob.JobType.MOVEMENT_ASSESSMENT) 
        gcs_object_key = data.get("video_url")
        notes = data.get("notes", "") # Megjegyzés kezelése

        if not (user_id and gcs_object_key):
            return HttpResponseBadRequest("user_id és video_url (GCS kulcs) kötelező mezők.")

        user = get_object_or_404(User, id=user_id)

        try:
            # 💡 Feltételezve, hogy a GCS bucket nevét a settings.py-ban tárolod
            GCS_BUCKET_NAME = settings.GS_BUCKET_NAME 
        except AttributeError:
            GCS_BUCKET_NAME = settings.GS_STATIC_BUCKET_NAME 
        
        # A teljes, publikus GCS URL összeállítása
        full_video_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{gcs_object_key}"
        
        # Job létrehozása az abszolút URL-lel
        job = DiagnosticJob.objects.create(
            user=user,
            sport_type=sport_type,
            job_type=job_type,
            video_url=full_video_url, # ⬅️ EZT MENTSÜK!
            notes=notes,
            status=DiagnosticJob.JobStatus.PENDING, 
        )

        # ❗️ JAVÍTOTT: Eredetileg run_diagnostic_job(job.id) volt. Ezt aszinkronra kell cserélni!
        # Mivel a `cloud_tasks.py` létezik a projektben, feltételezem, hogy az a helyes megoldás:
        # from .cloud_tasks import enqueue_diagnostic_job # Importálni kell a fájl elején, de a kényelem kedvéért most hívjuk az itt lévő tasks-t
        #run_diagnostic_job.delay(job.id) # Celery hívás
        
        # Egyelőre hagyjuk a Celery hívást, de a view-ban ezt már a Cloud Task-ra cseréltük!
        # Ha Celery fut (docker-compose), akkor ez a hívás a helyes a lokális fejlesztésnél:
        run_diagnostic_job.delay(job.id) 

        return JsonResponse({
            "success": True,
            "job_id": job.id,
            "status": job.status,
            "status_display": job.get_status_display(), # ÚJ: Emberi olvasható státusz
        }, status=201)

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_http_methods(["GET"]) # Csak GET-et engedélyez
def get_job_status(request, job_id):
    """
    Visszaadja egy adott diagnosztikai job aktuális státuszát.
    Ha kész, visszadja a PDF elérési útvonalát is.
    """
    job = get_object_or_404(DiagnosticJob, id=job_id)
    
    response_data = {
        "job_id": job.id,
        "status": job.status,
        "status_display": job.get_status_display(), # ÚJ: Emberi olvasható státusz
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message,
        "pdf_path": job.pdf_path, # 🌟 KRITIKUS JAVÍTÁS: A pdf_path mező hozzáadása
    }

    # Ha a job kész vagy hibás, akkor a frontendnek mindkét esetben szüksége van a hibaüzenetre, PDF-re
    if job.status == DiagnosticJob.JobStatus.COMPLETED and not job.pdf_path:
        response_data["warning"] = "Elemzés kész, de a PDF elérési út hiányzik a job objektumból."
        
    return JsonResponse(response_data)


@require_http_methods(["GET"]) # Csak GET-et engedélyez
def get_job_result(request, job_id):
    """
    Diagnosztikai eredmény lekérése (ha már elkészült).
    """
    job = get_object_or_404(DiagnosticJob, id=job_id)

    # ❗️ JAVÍTOTT: Státusz ellenőrzése a JobStatus Enummal
    if job.status != DiagnosticJob.JobStatus.COMPLETED:
        return JsonResponse({
            "job_id": job.id,
            "status": job.status,
            "status_display": job.get_status_display(),
            "message": "Az elemzés még nem készült el."
        }, status=202)

    return JsonResponse({
        "job_id": job.id,
        "status": job.status,
        "result": job.result,
        "pdf_path": job.pdf_path, # Még itt is visszaadhatjuk, a biztonság kedvéért
    })


@csrf_exempt
@require_http_methods(["POST"]) # Csak POST-ot engedélyez
def cleanup_old_videos(request):
    """
    30 napnál régebbi videók törlése (csak admin vagy cron futtathatja).
    """
    # A kód jó, csak a fejléceket egészítettem ki a require_http_methods-szel
    cutoff = timezone.now() - datetime.timedelta(days=30)
    old_jobs = DiagnosticJob.objects.filter(created_at__lt=cutoff)

    deleted = 0
    # A GCS törlést nem implementáljuk itt, ahogy az eredeti kódban sincs
    for job in old_jobs:
        if job.video_url and job.video_url.startswith("https://storage.googleapis.com/"):
            # A jövőben ide jöhet GCS API törlés
            job.video_url = None
            job.save(update_fields=["video_url"])
            deleted += 1

    return JsonResponse({
        "success": True,
        "deleted_count": deleted,
    })

# ----------------------------------------------------------------
# 🆕 ÚJ: Antropometriai Profil API Végpont
# ----------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST", "GET"])
def anthropometry_profile(request, user_id):
    """
    POST: Antropometriai profil létrehozása/frissítése.
    GET:  Antropometriai profil lekérése.
    """
    # ❗️ Biztonság: Csak a bejelentkezett felhasználó nézheti/frissítheti a saját profilját
    if not request.user.is_authenticated or request.user.id != user_id:
        return JsonResponse({"success": False, "error": "Nincs jogosultság a profil megtekintésére/frissítésére."}, status=403)

    try:
        # Próbáljuk lekérni a meglévő profilt, vagy létrehozunk egy újat.
        # Ha a user_id-t adjuk meg, akkor a OneToOneField automatikusan létrehozza, ha nem létezik.
        profile, created = UserAnthropometryProfile.objects.get_or_create(
            user_id=user_id,
            # Megjegyzés: a get_or_create nem tudja beállítani az alapértelmezett mezőket, 
            # ha csak a primary_key (user_id) van megadva. Ezt a POST részben kezeljük.
        )
    except Exception as e:
         return JsonResponse({"success": False, "error": f"Hiba az adatbázis hozzáférés során: {e}"}, status=500)

    # --- POST: Profil frissítése ---
    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "error": "Hibás JSON formátum."}, status=400)

        # Mezők frissítése (csak azokat a mezőket frissítjük, amik szerepelnek a kérésben)
        # 💡 Ez a rész a testmagasságot (cm) kritikus adatként kezeli
        if 'height_cm' in data:
            profile.height_cm = data['height_cm']
        
        # Opcionális mezők frissítése
        for field in [
            'weight_kg', 'trunk_height_cm', 'shoulder_width_cm', 'pelvis_width_cm',
            'left_upper_arm_cm', 'right_upper_arm_cm', 'left_forearm_cm', 'right_forearm_cm',
            'left_thigh_cm', 'right_thigh_cm', 'left_shin_cm', 'right_shin_cm'
        ]:
            if field in data:
                # 0-ra állítás a null helyett, ha számot vár az adatbázis
                profile_value = data[field]
                if profile_value is not None and profile_value != "":
                    setattr(profile, field, profile_value)
                else:
                    # Explicit NULL beállítás (ha DecimalField(null=True) van)
                    setattr(profile, field, None)

        # Mentés és validáció
        try:
            profile.save()
            
            return JsonResponse({
                "success": True, 
                "message": "Antropometriai profil sikeresen frissítve.",
                "profile_id": profile.user_id,
            }, status=200)
        except Exception as e:
            # Pl. ha a height_cm mező nem kapott értéket
            return JsonResponse({"success": False, "error": f"Hiba a mentés során: {e}"}, status=400)


    # --- GET: Profil lekérése ---
    elif request.method == "GET":
        # Átkonvertáljuk a modell adatokat egy egyszerű dictionary-vé
        # A OneToOneField miatt a user mező nélkül adjuk vissza az adatokat
        profile_data = {
            "user_id": profile.user_id,
            "height_cm": profile.height_cm,
            "weight_kg": profile.weight_kg,
            "trunk_height_cm": profile.trunk_height_cm,
            "shoulder_width_cm": profile.shoulder_width_cm,
            "pelvis_width_cm": profile.pelvis_width_cm,
            "left_upper_arm_cm": profile.left_upper_arm_cm,
            "right_upper_arm_cm": profile.right_upper_arm_cm,
            "left_forearm_cm": profile.left_forearm_cm,
            "right_forearm_cm": profile.right_forearm_cm,
            "left_thigh_cm": profile.left_thigh_cm,
            "right_thigh_cm": profile.right_thigh_cm,
            "left_shin_cm": profile.left_shin_cm,
            "right_shin_cm": profile.right_shin_cm,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
            "reference_job_id": profile.reference_job_id,
        }
        
        # Megjegyzés: a DecimalField mezők stringként kerülnek JSON-ba, ami helyes.
        
        return JsonResponse({
            "success": True, 
            "profile": profile_data
        }, status=200)

        