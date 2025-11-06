# diagnostics_jobs/views.py (FRISSÍTETT RÉSZEK)
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.conf import settings
from google.cloud import storage
import json
import uuid
import logging
from datetime import datetime, timedelta


from .models import DiagnosticJob, UserAnthropometryProfile
from .forms import AnthropometryProfileForm, AnthropometryCalibrationForm
from .services.anthropometry_calibration_service import AnthropometryCalibrationService
from .tasks import run_diagnostic_job
from .cloud_tasks import enqueue_diagnostic_job
from biometric_data.models import WeightData, HRVandSleepData, WorkoutFeedback
from diagnostics.utils.gcs_signer import get_storage_client

User = get_user_model()
logger = logging.getLogger(__name__)

@csrf_exempt
def create_diagnostic_job(request):
    """
    Új diagnosztikai feladat létrehozása.
    Automatikusan csatolja a sportoló legfrissebb biometrikus adatait.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST metódus szükséges"}, status=405)

    try:
        data = json.loads(request.body)
        user_id = data.get("user_id")
        sport_type = data.get("sport_type", "general")
        job_type = data.get("job_type", "general")
        video_url = data.get("video_url")

        if not all([user_id, sport_type, job_type, video_url]):
            return JsonResponse({"error": "Hiányzó kötelező mezők"}, status=400)

        user = User.objects.filter(id=user_id).first()
        if not user:
            return JsonResponse({"error": "Felhasználó nem található"}, status=404)

        # 🔹 Legfrissebb biometrikus adatok lekérése
        latest_weight = WeightData.objects.filter(user=user).order_by('-created_at').first()
        latest_hrv = HRVandSleepData.objects.filter(user=user).order_by('-recorded_at').first()
        latest_feedback = WorkoutFeedback.objects.filter(user=user).order_by('-workout_date').first()

        # 🔹 Diagnosztikai feladat létrehozása
        job = DiagnosticJob.objects.create(
            user=user,
            sport_type=sport_type,
            job_type=job_type,
            video_url=video_url,
            weight_snapshot=latest_weight,
            hrv_snapshot=latest_hrv,
            workout_feedback_snapshot=latest_feedback,
        )

        # ✅ KRITIKUS JAVÍTÁS: Feladat ütemezése (Celery/Cloud Tasks)
        try:
            enqueue_diagnostic_job(job.id)
        except Exception as e:
            # Ha az ütemezés sikertelen, jelezzük, de a job létrejött
            return JsonResponse({
                "success": True,
                "job_id": job.id,
                "status": job.status,
                "warning": f"A job létrejött, de az ütemezés sikertelen: {str(e)}",
                "attached_data": {
                    "weight_snapshot": bool(latest_weight),
                    "hrv_snapshot": bool(latest_hrv),
                    "workout_feedback_snapshot": bool(latest_feedback),
                }
            }, status=201)

        return JsonResponse({
            "success": True,
            "job_id": job.id,
            "status": job.status,
            "attached_data": {
                "weight_snapshot": bool(latest_weight),
                "hrv_snapshot": bool(latest_hrv),
                "workout_feedback_snapshot": bool(latest_feedback),
            }
        }, status=201)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def run_job_view(request):
    """
    Manuális job futtatás endpoint (Cloud Tasks használja).
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            job_id = data.get("job_id")
            if not job_id:
                return JsonResponse({"error": "job_id hiányzik"}, status=400)

            # ✅ JAVÍTÁS: Aszinkron hívás .delay()-jel
            run_diagnostic_job.delay(job_id)
            return JsonResponse({"success": True, "job_id": job_id})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "POST metódus szükséges"}, status=405)

# =========================================================================
# 🆕 Job Indítás View (AJAX/POST kérésekhez)
# =========================================================================

@login_required
@require_http_methods(["POST"]) # Csak POST-ot fogad el a feltöltés indításához!
def upload_anthropometry_video(request):
    """
    Antropometriai elemző videó feltöltése és elemzés indítása.
    """
    job_type = DiagnosticJob.JobType.ANTHROPOMETRY_ASSESSMENT

    if request.method == "POST":
        try:
            # POST adatok JSON-ként való olvasása (a frontend AJAX hívásából)
            data = json.loads(request.body)
            gcs_object_name = data.get('video_url')
            
            if not gcs_object_name:
                return JsonResponse({"success": False, "error": "Hiányzó 'video_url' a kérésben."}, status=400)

            try:
                GCS_BUCKET_NAME = settings.GS_BUCKET_NAME
            except AttributeError:
                # Fallback, ha a settings.py-ban nem így hívják a beállítást
                GCS_BUCKET_NAME = settings.GS_STATIC_BUCKET_NAME 
                
            full_video_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{gcs_object_name}"


            # 1. Job létrehozása (PENDING státuszban)
            job = DiagnosticJob.objects.create(
                user=request.user,
                sport_type='general', 
                job_type=job_type,
                video_url=full_video_url,
                status=DiagnosticJob.JobStatus.PENDING
            )
            
            # 2. Job ütemezése Celery/Cloud Tasks-ban
            enqueue_diagnostic_job(job.id) 

            return JsonResponse({
                "success": True, 
                "job_id": job.id,
                "message": "A videó sikeresen feltöltve. Az elemzés elindult a háttérben!"
            }, status=201)
                
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "error": "Hibás JSON formátum."}, status=400)
        except Exception as e:
            # Hiba a Job létrehozásakor/ütemezésekor
            print(f"❌ Hiba történt a Job létrehozásakor/ütemezésekor: {e}")
            return JsonResponse({"success": False, "error": f"Hiba az elemzés indításakor: {e}"}, status=500)
    
    return JsonResponse({"success": False, "error": "Csak POST kérés fogadható el az elemzés indításához."}, status=405)

# ================================================================
# 🧍‍♂️ ANTROPOMETRIAI PROFIL NÉZET
# ================================================================
@login_required
def anthropometry_profile_view(request):
    """Antropometriai adatok megtekintése, kalibráció és manuális frissítés."""
    # 1️⃣ Profil lekérése/létrehozása
    try:
        latest_weight = WeightData.objects.filter(user=request.user).latest('workout_date')
        default_weight = latest_weight.morning_weight
    except WeightData.DoesNotExist:
        default_weight = None

    profile, _ = UserAnthropometryProfile.objects.get_or_create(
        user=request.user,
        defaults={'weight_kg': default_weight}
    )

    # 2️⃣ POST feldolgozás (kalibráció vagy manuális mentés)
    if request.method == "POST":
        # Ha képfeltöltés is van → kalibráció
        if 'front_photo' in request.FILES and 'side_photo' in request.FILES:
            return handle_calibration_upload(request, profile)

        # Egyébként manuális mentés
        form = AnthropometryProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Antropometriai adatok sikeresen frissítve!")
            return redirect(reverse("diagnostics_jobs:anthropometry_profile_view"))
        else:
            messages.error(request, "⚠️ Hibás adatmegadás! Kérlek ellenőrizd a mezőket.")
    else:
        form = AnthropometryProfileForm(instance=profile)

    # 3️⃣ Legutóbbi kalibrációs job lekérése
    latest_anthropometry_job = DiagnosticJob.objects.filter(
        user=request.user,
        job_type=DiagnosticJob.JobType.ANTHROPOMETRY_CALIBRATION
    ).order_by('-created_at').first()

    context = {
        "form": form,
        "profile": profile,
        "latest_anthropometry_job": latest_anthropometry_job,
        "title": "Antropometriai Profil"
    }
    return render(request, "diagnostics_jobs/anthropometry_profile.html", context)


# ================================================================
# 📸 KALIBRÁCIÓ FOTÓ FELTÖLTÉS KEZELŐ
# ================================================================
def handle_calibration_upload(request, profile):
    """Feltölt két fotót, létrehoz egy DiagnosticJob-ot és futtatja a kalibrációt (kettős faktorral)."""
    try:
        calibration_form = AnthropometryCalibrationForm(request.POST, request.FILES)
        if not calibration_form.is_valid():
            for field, errors in calibration_form.errors.items():
                for error in errors:
                    messages.error(request, f"❌ {field}: {error}")
            return redirect(reverse("diagnostics_jobs:anthropometry_profile_view"))

        # 🔹 Felhasználó által megadott értékek
        user_height = float(request.POST.get("user_stated_height_m"))
        user_thigh = float(request.POST.get("user_stated_thigh_cm"))
        user_shin = float(request.POST.get("user_stated_shin_cm"))

        front_photo = request.FILES["front_photo"]
        side_photo = request.FILES["side_photo"]

        # 🔹 Feltöltés GCS-be
        front_gcs_path = upload_photo_to_gcs(front_photo, request.user, "front")
        side_gcs_path = upload_photo_to_gcs(side_photo, request.user, "side")

        # 🔹 Job létrehozása
        job = DiagnosticJob.objects.create(
            user=request.user,
            sport_type="CALIBRATION",
            job_type=DiagnosticJob.JobType.ANTHROPOMETRY_CALIBRATION,
            user_stated_height_m=user_height,
            user_stated_thigh_cm=user_thigh,
            user_stated_shin_cm=user_shin,
            anthropometry_photo_url_front=front_gcs_path,
            anthropometry_photo_url_side=side_gcs_path,
            status=DiagnosticJob.JobStatus.PENDING,
        )

        # 🔹 Kalibráció futtatása
        service = AnthropometryCalibrationService(job.id)
        service.run_analysis(job)

        job.refresh_from_db()

        # 🔹 Eredmény feldolgozás
        if job.status == DiagnosticJob.JobStatus.COMPLETED:
            result = job.result or {}
            confidence = result.get("calibration_confidence", 0)
            main_factor = job.calibration_factor
            leg_factor = job.leg_calibration_factor
            annotated_url = result.get("annotated_image_url")

            # 🔹 Profil frissítése mindkét faktorral
            profile.calibration_factor = main_factor
            if leg_factor:
                profile.leg_calibration_factor = leg_factor
            if annotated_url and not annotated_url.startswith("http"):
                annotated_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{annotated_url}"
            profile.annotated_image_url = annotated_url
            profile.reference_job = job
            profile.save(update_fields=[
                "calibration_factor",
                "annotated_image_url",
                "reference_job",
                "updated_at"
            ] + (["leg_calibration_factor"] if leg_factor else []))

            msg = (
                f"✅ Kalibráció sikeresen befejezve<br>"
                f"Teljes faktor: {main_factor:.4f}<br>"
                f"Láb-specifikus faktor: {f'{leg_factor:.4f}' if leg_factor is not None else '—'}<br>"
                f"Megbízhatóság: {confidence * 100:.0f}%"
            )
            messages.success(request, msg)
        else:
            messages.error(request, f"❌ Kalibráció sikertelen: {job.error_message}")

    except Exception as e:
        logger.exception("Kalibrációs hiba")
        messages.error(request, f"❌ Kritikus hiba: {e}")

    return redirect(reverse("diagnostics_jobs:anthropometry_profile_view"))


# ================================================================
# ☁️ GCS FOTÓ FELTÖLTŐ HELPER
# ================================================================
def upload_photo_to_gcs(photo_file, user, photo_type):
    """
    Kép feltöltése GCS-be, Uniform Bucket Access kompatibilisen.
    Ha a bucket nem publikus, akkor Signed URL-t generál.
    """
    try:
        ext = photo_file.name.split(".")[-1].lower()
        unique_id = uuid.uuid4().hex[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{photo_type}_{timestamp}_{unique_id}.{ext}"
        gcs_path = f"calibration_photos/user_{user.id}/{filename}"

        # 🔹 GCS kliens beolvasása a gcs_signer-ből
        client = get_storage_client()
        bucket = client.bucket(settings.GS_BUCKET_NAME)
        blob = bucket.blob(gcs_path)

        # 🔹 Feltöltés
        blob.upload_from_file(photo_file, content_type=photo_file.content_type, rewind=True)

        # 🔹 URL meghatározás
        # Ha publikus bucket, a public_url működni fog:
        url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{gcs_path}"

        # 🔹 Ha nem publikus, akkor Signed URL (Uniform Bucket Access esetén)
        if not settings.DEBUG:
            try:
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=datetime.utcnow() + timedelta(days=7),
                    method="GET"
                )
            except Exception as e:
                logger.warning(f"Nem sikerült Signed URL-t generálni: {e}")

        logger.info(f"✅ Fotó feltöltve GCS-re: {url}")
        return url

    except Exception as e:
        logger.error(f"❌ GCS feltöltési hiba: {e}", exc_info=True)
        raise RuntimeError(f"Nem sikerült feltölteni a fotót: {e}")


# ================================================================
# 🆕 API ENDPOINT: AJAX-os Kalibráció (Opcionális)
# ================================================================
@login_required
@require_http_methods(["POST"])
@csrf_exempt
def calibrate_anthropometry_api(request):
    """
    API endpoint AJAX kérésekhez (ha a frontend fetch-el hívja).
    """
    try:
        # Validálás
        if 'front_photo' not in request.FILES or 'side_photo' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'Mindkét fotó szükséges!'
            }, status=400)
        
        user_height = request.POST.get('user_stated_height_m')
        if not user_height:
            return JsonResponse({
                'success': False,
                'error': 'Magasság megadása kötelező!'
            }, status=400)
        
        try:
            user_height = float(user_height)
            if user_height < 1.4 or user_height > 2.3:
                raise ValueError("Érvénytelen magasság")
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Érvényes magasság: 1.40 - 2.30 méter'
            }, status=400)
        
        # Feltöltés és Job létrehozás
        front_photo = request.FILES['front_photo']
        side_photo = request.FILES['side_photo']
        
        front_gcs_url = upload_photo_to_gcs(front_photo, request.user, 'front')
        side_gcs_url = upload_photo_to_gcs(side_photo, request.user, 'side')
        
        job = DiagnosticJob.objects.create(
            user=request.user,
            sport_type='CALIBRATION',
            job_type=DiagnosticJob.JobType.ANTHROPOMETRY_CALIBRATION,
            user_stated_height_m=user_height,
            anthropometry_photo_url_front=front_gcs_url,
            anthropometry_photo_url_side=side_gcs_url,
            status=DiagnosticJob.JobStatus.PENDING 
        )
        
        # Szinkron elemzés
        service = AnthropometryCalibrationService(job.id)
        service.run_analysis(job)
        
        job.refresh_from_db()
        
        if job.status == DiagnosticJob.JobStatus.COMPLETED:
            result = job.result or {}
            return JsonResponse({
                'success': True,
                'job_id': job.id,
                'calibration_factor': float(job.calibration_factor),
                'confidence': result.get('calibration_confidence', 0),
                'warnings': result.get('quality_warnings', []),
                'measurements': result.get('measurements', {}),
                'annotated_image_url': result.get('annotated_image_url')
            })
        else:
            return JsonResponse({
                'success': False,
                'job_id': job.id,
                'error': job.error_message or 'Ismeretlen hiba'
            }, status=500)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
