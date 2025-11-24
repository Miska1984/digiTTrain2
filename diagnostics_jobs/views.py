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

# 🆕 ÚJ IMPORT: Billing utils
from billing.utils import dedicate_analysis, get_analysis_balance

User = get_user_model()
logger = logging.getLogger(__name__)


@csrf_exempt
def create_diagnostic_job(request):
    """
    Új diagnosztikai feladat létrehozása és ELEMZÉS LEVONÁSA az egyenlegből.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST metódus szükséges"}, status=405)

    user = request.user
    
    try:
        data = json.loads(request.body)
        user_id = data.get("user_id")
        sport_type = data.get("sport_type", "general")
        job_type_code = data.get("job_type")
        
        # 1. Alapvető validáció
        if not job_type_code or job_type_code not in DiagnosticJob.JobType.values:
            return JsonResponse({'success': False, 'error': 'Érvénytelen job_type kód.'}, status=400)
        
        # 🆕 2. ELEMZÉSI EGYENLEG ELLENŐRZÉSE
        current_balance = get_analysis_balance(user)
        
        if current_balance < 1:
            return JsonResponse({
                'success': False, 
                'error': 'INSUFFICIENT_BALANCE',
                'message': 'Nincs elegendő elemzési egyenleged! Vásárolj elemzési csomagot vagy nézz hirdetéseket.',
                'current_balance': current_balance
            }, status=402)  # 402 Payment Required
        
        # 3. DiagnosticJob létrehozása (még PENDING státuszban)
        job = DiagnosticJob.objects.create(
            user=user,
            sport_type=sport_type,
            job_type=job_type_code,
            status=DiagnosticJob.JobStatus.PENDING,
        )

        # 🆕 4. ELEMZÉS LEVONÁSA AZ EGYENLEGBŐL
        success, new_balance = dedicate_analysis(user, job)

        if not success:
            job.status = DiagnosticJob.JobStatus.FAILED 
            job.error_message = f"Nem sikerült levonni az elemzést. Egyenleg: {new_balance} db."
            job.save(update_fields=['status', 'error_message'])
            
            return JsonResponse({
                'success': False, 
                'error': 'DEDUCTION_FAILED',
                'message': job.error_message
            }, status=500)
        
        # 5. Sikeres levonás: Átállítjuk QUEUED-re és elindítjuk
        job.status = DiagnosticJob.JobStatus.QUEUED
        job.save(update_fields=['status'])
        
        # Celery Task ütemezése
        enqueue_diagnostic_job(job.id)
        
        return JsonResponse({
            'success': True,
            'job_id': job.id,
            'message': f"Elemzés elindítva! -1 db elemzés levonva.",
            'remaining_balance': new_balance
        })
            
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Érvénytelen JSON formátum.'}, status=400)
    except Exception as e:
        logger.exception("Hiba a job indításakor")
        
        if 'job' in locals():
            job.status = DiagnosticJob.JobStatus.FAILED
            job.error_message = f'Ismeretlen hiba: {str(e)}'
            job.save(update_fields=['status', 'error_message'])
            
        return JsonResponse({
            'success': False,
            'error': f'Ismeretlen hiba: {type(e).__name__}: {str(e)}'
        }, status=500)


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

            run_diagnostic_job.delay(job_id)
            return JsonResponse({"success": True, "job_id": job_id})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "POST metódus szükséges"}, status=405)


# =========================================================================
# 🆕 Job Indítás View (AJAX/POST kérésekhez) - JAVÍTOTT VERZIÓ
# =========================================================================

@login_required
@require_http_methods(["POST"])
def upload_anthropometry_video(request):
    """
    Antropometriai elemző videó feltöltése és elemzés indítása.
    🆕 EGYENLEG ELLENŐRZÉSSEL!
    """
    job_type = DiagnosticJob.JobType.ANTHROPOMETRY_ASSESSMENT

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            gcs_object_name = data.get('video_url')
            
            if not gcs_object_name:
                return JsonResponse({"success": False, "error": "Hiányzó 'video_url' a kérésben."}, status=400)

            # 🆕 1. EGYENLEG ELLENŐRZÉSE
            current_balance = get_analysis_balance(request.user)
            
            if current_balance < 1:
                return JsonResponse({
                    'success': False, 
                    'error': 'INSUFFICIENT_BALANCE',
                    'message': 'Nincs elegendő elemzési egyenleged!',
                    'current_balance': current_balance
                }, status=402)

            try:
                GCS_BUCKET_NAME = settings.GS_BUCKET_NAME
            except AttributeError:
                GCS_BUCKET_NAME = settings.GS_STATIC_BUCKET_NAME 
                
            full_video_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{gcs_object_name}"

            # 2. Job létrehozása (PENDING státuszban)
            job = DiagnosticJob.objects.create(
                user=request.user,
                sport_type='general', 
                job_type=job_type,
                video_url=full_video_url,
                status=DiagnosticJob.JobStatus.PENDING
            )
            
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

            return JsonResponse({
                "success": True, 
                "job_id": job.id,
                "message": "A videó sikeresen feltöltve. Az elemzés elindult!",
                "remaining_balance": new_balance
            }, status=201)
                
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "error": "Hibás JSON formátum."}, status=400)
        except Exception as e:
            logger.exception("Hiba a Job létrehozásakor")
            return JsonResponse({"success": False, "error": f"Hiba: {e}"}, status=500)
    
    return JsonResponse({"success": False, "error": "Csak POST kérés fogadható el."}, status=405)



# ================================================================
# 🧍‍♂️ ANTROPOMETRIAI PROFIL NÉZET
# ================================================================
@login_required
def anthropometry_profile_view(request):
    """Antropometriai adatok megtekintése, kalibráció és manuális frissítés."""
    
    try:
        latest_weight = WeightData.objects.filter(user=request.user).latest('workout_date')
        default_weight = latest_weight.morning_weight
    except WeightData.DoesNotExist:
        default_weight = None

    profile, _ = UserAnthropometryProfile.objects.get_or_create(
        user=request.user,
        defaults={'weight_kg': default_weight}
    )

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
            messages.error(request, "⚠️ Hibás adatmegadás!")
    else:
        form = AnthropometryProfileForm(instance=profile)

    latest_anthropometry_job = DiagnosticJob.objects.filter(
        user=request.user,
        job_type=DiagnosticJob.JobType.ANTHROPOMETRY_CALIBRATION
    ).order_by('-created_at').first()

    context = {
        "form": form,
        "profile": profile,
        "latest_anthropometry_job": latest_anthropometry_job,
        "title": "Antropometriai Profil",
        # 🆕 Egyenleg hozzáadása
        "analysis_balance": get_analysis_balance(request.user)
    }
    return render(request, "diagnostics_jobs/anthropometry_profile.html", context)


# ================================================================
# 📸 KALIBRÁCIÓ FOTÓ FELTÖLTÉS KEZELŐ - JAVÍTOTT VERZIÓ
# ================================================================
def handle_calibration_upload(request, profile):
    """
    Feltölt két fotót, létrehoz egy DiagnosticJob-ot és futtatja a kalibrációt.
    🆕 EGYENLEG ELLENŐRZÉSSEL!
    """
    try:
        # 🆕 1. EGYENLEG ELLENŐRZÉSE
        current_balance = get_analysis_balance(request.user)
        
        if current_balance < 1:
            messages.error(
                request,
                f"❌ Nincs elegendő elemzési egyenleged! Jelenlegi: {current_balance} db. "
                "Vásárolj elemzési csomagot!"
            )
            return redirect(reverse("diagnostics_jobs:anthropometry_profile_view"))
        
        calibration_form = AnthropometryCalibrationForm(request.POST, request.FILES)
        if not calibration_form.is_valid():
            for field, errors in calibration_form.errors.items():
                for error in errors:
                    messages.error(request, f"❌ {field}: {error}")
            return redirect(reverse("diagnostics_jobs:anthropometry_profile_view"))

        user_height = float(request.POST.get("user_stated_height_m"))
        user_thigh = float(request.POST.get("user_stated_thigh_cm", 0))
        user_shin = float(request.POST.get("user_stated_shin_cm", 0))

        front_photo = request.FILES["front_photo"]
        side_photo = request.FILES["side_photo"]

        front_gcs_path = upload_photo_to_gcs(front_photo, request.user, "front")
        side_gcs_path = upload_photo_to_gcs(side_photo, request.user, "side")

        # 2. Job létrehozása
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

        # 🆕 3. ELEMZÉS LEVONÁSA
        success, new_balance = dedicate_analysis(request.user, job)
        
        if not success:
            job.status = DiagnosticJob.JobStatus.FAILED
            job.error_message = "Nem sikerült levonni az elemzést."
            job.save()
            messages.error(request, f"❌ {job.error_message}")
            return redirect(reverse("diagnostics_jobs:anthropometry_profile_view"))

        # 4. Kalibráció futtatása (SZINKRON!)
        service = AnthropometryCalibrationService(job.id)
        service.run_analysis(job)

        job.refresh_from_db()

        if job.status == DiagnosticJob.JobStatus.COMPLETED:
            result = job.result or {}
            confidence = result.get("calibration_confidence", 0)
            main_factor = job.calibration_factor
            leg_factor = job.leg_calibration_factor
            annotated_url = result.get("annotated_image_url")

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
                f"Megbízhatóság: {confidence * 100:.0f}%<br>"
                f"Fennmaradó egyenleg: {new_balance} db"
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
    """Kép feltöltése GCS-be."""
    try:
        ext = photo_file.name.split(".")[-1].lower()
        unique_id = uuid.uuid4().hex[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{photo_type}_{timestamp}_{unique_id}.{ext}"
        gcs_path = f"calibration_photos/user_{user.id}/{filename}"

        client = get_storage_client()
        bucket = client.bucket(settings.GS_BUCKET_NAME)
        blob = bucket.blob(gcs_path)

        blob.upload_from_file(photo_file, content_type=photo_file.content_type, rewind=True)

        url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{gcs_path}"

        if not settings.DEBUG:
            try:
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=datetime.utcnow() + timedelta(days=7),
                    method="GET"
                )
            except Exception as e:
                logger.warning(f"Signed URL generálási hiba: {e}")

        logger.info(f"✅ Fotó feltöltve: {url}")
        return url

    except Exception as e:
        logger.error(f"❌ GCS feltöltési hiba: {e}", exc_info=True)
        raise RuntimeError(f"Nem sikerült feltölteni a fotót: {e}")


# ================================================================
# 🆕 API ENDPOINT: AJAX-os Kalibráció - JAVÍTOTT VERZIÓ
# ================================================================
@login_required
@require_http_methods(["POST"])
@csrf_exempt
def calibrate_anthropometry_api(request):
    """
    API endpoint AJAX kérésekhez.
    🆕 EGYENLEG ELLENŐRZÉSSEL!
    """
    try:
        # 🆕 1. EGYENLEG ELLENŐRZÉSE
        current_balance = get_analysis_balance(request.user)
        
        if current_balance < 1:
            return JsonResponse({
                'success': False,
                'error': 'INSUFFICIENT_BALANCE',
                'message': 'Nincs elegendő elemzési egyenleged!',
                'current_balance': current_balance
            }, status=402)
        
        # 2. Validálás
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
        
        # 3. Feltöltés és Job létrehozás
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
        
        # 🆕 4. ELEMZÉS LEVONÁSA
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
        
        # 5. Szinkron elemzés
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
                'annotated_image_url': result.get('annotated_image_url'),
                'remaining_balance': new_balance
            })
        else:
            return JsonResponse({
                'success': False,
                'job_id': job.id,
                'error': job.error_message or 'Ismeretlen hiba'
            }, status=500)
            
    except Exception as e:
        logger.exception("API kalibráció hiba")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)