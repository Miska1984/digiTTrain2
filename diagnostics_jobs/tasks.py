# diagnostics_jobs/tasks.py
import os
import shutil
import logging
import numpy as np
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.core.files.storage import default_storage

from .models import DiagnosticJob, UserAnthropometryProfile
from diagnostics.pdf_utils import generate_pdf_report 

# 🆕 ÚJ IMPORT: Billing utils
from billing.utils import refund_analysis, get_analysis_balance
from billing.models import UserAnalysisBalance

# Service-ek
from .services.anthropometry_calibration_service import AnthropometryCalibrationService
from .services.squat_assessment import SquatAssessmentService
from .services.posture_assessment import PostureAssessmentService
from .services.shoulder_circumduction_assessment import ShoulderCircumductionService
from .services.vertical_jump_assessment import VerticalJumpAssessmentService
from .services.single_leg_stance_service import SingleLegStanceAssessmentService

logger = logging.getLogger(__name__)

SERVICE_MAP = {
    DiagnosticJob.JobType.ANTHROPOMETRY_CALIBRATION: AnthropometryCalibrationService,
    DiagnosticJob.JobType.SQUAT_ASSESSMENT: SquatAssessmentService,
    DiagnosticJob.JobType.POSTURE_ASSESSMENT: PostureAssessmentService,
    DiagnosticJob.JobType.SHOULDER_CIRCUMDUCTION: ShoulderCircumductionService,
    DiagnosticJob.JobType.VERTICAL_JUMP: VerticalJumpAssessmentService,
    DiagnosticJob.JobType.SINGLE_LEG_STANCE_LEFT: SingleLegStanceAssessmentService,
    DiagnosticJob.JobType.SINGLE_LEG_STANCE_RIGHT: SingleLegStanceAssessmentService,
}


def _convert_numpy_to_python(data):
    """
    Rekurzívan átalakítja a NumPy típusokat (ndarray, np.float, stb.)
    natív Python típusokká (list, float, int), hogy JSON-ba menthető legyen.
    """
    if isinstance(data, dict):
        return {k: _convert_numpy_to_python(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_convert_numpy_to_python(item) for item in data]
    elif isinstance(data, np.ndarray):
        return data.tolist()
    elif isinstance(data, (np.float32, np.float64, np.number)):
        return float(data)
    return data


@shared_task
def run_diagnostic_job(job_id):
    """
    Dinamikus mozgáselemzés feldolgozása, profil frissítés vagy PDF-riport generálás.
    
    🆕 VÁLTOZÁS: 
    - Sikertelen job esetén visszatérítjük az elemzést!
    - FIGYELEM: Az elemzés levonása a view-ban történik (dedicate_analysis)
    """
    pdf_path = None
    job = None
    
    try:
        job = DiagnosticJob.objects.get(id=job_id)
        
        # 🔥 KRITIKUS: Ellenőrizzük, hogy van-e elegendő egyenleg
        # (Ez csak egy biztonsági ellenőrzés, a fő ellenőrzés a view-ban van)
        current_balance = get_analysis_balance(job.user)
        if current_balance < 0:
            error_msg = "❌ Nincs elegendő elemzési egyenleg! Az elemzés már le lett vonva, de valami hiba történt."
            job.mark_as_failed(error_msg)
            logger.error(f"❌ [TASK] Egyenleg hiba job_id={job_id}, user={job.user.username}")

            # ➡️ ÚJ KÓD: VISSZATÉRÍTÉS KRITIKUS HIBA ESETÉN
            try:
                # Egyszerűsített hívás:
                refund_analysis(job) # Csak a job objektumot adjuk át
                logger.info(f"↩️ [BILLING] Elemzés visszatérítve job_id={job_id}")
            except Exception as refund_error:
                logger.error(f"❌ [BILLING] Visszatérítési hiba: {refund_error}")
            
            # ⬅️ Vége az új kódnak
            return
        
        job.mark_as_processing()

        service_class = SERVICE_MAP.get(job.job_type)
        if not service_class:
            raise NotImplementedError(f"Nincs implementált Service a '{job.job_type}' típushoz.")

        logger.info(f"▶️ [TASK] {service_class.__name__} feldolgozás indítása job_id={job.id}")

        # 1️⃣ Elemzés futtatása
        service_instance = service_class(job=job)
        result_data = service_instance.run_analysis()

        # =========================================================================
        # 🆕 2. KÜLÖNLEGES LOGIKA: ANTROPOMETRIAI PROFIL FRISSÍTÉSE
        # =========================================================================
        if job.job_type == DiagnosticJob.JobType.ANTHROPOMETRY_CALIBRATION:
            logger.info(f"💾 [TASK] Antropometriai adatok mentése job_id={job.id}")
            
            try:
                profile = UserAnthropometryProfile.objects.get(user=job.user)
                
                estimated_height = result_data.get("estimated_height_cm")
                if estimated_height:
                    profile.height_cm = estimated_height

                if result_data.get("estimated_shoulder_width_cm"):
                    profile.shoulder_width_cm = result_data["estimated_shoulder_width_cm"]

                profile.save()
                logger.info(f"✅ Profil frissítve! Új magasság: {profile.height_cm} cm")

            except UserAnthropometryProfile.DoesNotExist:
                logger.error(f"❌ Nincs antropometriai profil job_id={job.id}.")

        # 2.5️⃣ Annotált kép feltöltése (ha van)
        if "annotated_image_local_path" in result_data:
            local_path = result_data.pop("annotated_image_local_path")
            target_folder = f"jobs/{job.id}/annotated"
            file_name = os.path.basename(local_path)
            storage_path = os.path.join(target_folder, file_name)

            try:
                logger.info(f"⬆️ Annotált kép feltöltése GCS-re: {storage_path}")

                with open(local_path, "rb") as image_file:
                    path_in_storage = default_storage.save(storage_path, image_file)

                annotated_url = default_storage.url(path_in_storage)
                result_data["annotated_image_url"] = annotated_url
                logger.info(f"🖼 Annotált kép feltöltve: {annotated_url}")

                # Profilhoz is mentsük, ha antropometriai job
                if job.job_type == DiagnosticJob.JobType.ANTHROPOMETRY_CALIBRATION:
                    try:
                        profile = UserAnthropometryProfile.objects.get(user=job.user)
                        profile.annotated_image_url = annotated_url
                        profile.save(update_fields=["annotated_image_url"])
                        logger.info(f"✅ Annotált kép URL elmentve a profilhoz: {annotated_url}")
                    except UserAnthropometryProfile.DoesNotExist:
                        logger.warning(f"⚠️ Profil nem található az annotált kép mentéséhez (user_id={job.user.id})")

                os.remove(local_path)

            except Exception as e:
                logger.warning(f"⚠️ Annotált kép feltöltése sikertelen: {e}")

        # 3️⃣ Skeleton videó feltöltése
        if "skeleton_video_local_path" in result_data:
            local_path = result_data.pop("skeleton_video_local_path")
            target_folder = f"jobs/{job.id}/skeleton"
            file_name = os.path.basename(local_path)
            storage_path = os.path.join(target_folder, file_name)

            try:
                logger.info(f"⬆️ Skeleton videó feltöltése GCS-re: {storage_path}")
                
                with open(local_path, 'rb') as video_file:
                    path_in_storage = default_storage.save(storage_path, video_file)
                
                skeleton_url = default_storage.url(path_in_storage)
                result_data["skeleton_video_url"] = skeleton_url
                logger.info(f"🎥 Skeleton videó feltöltve: {skeleton_url}")
                
                os.remove(local_path)
                
            except Exception as e:
                logger.warning(f"⚠️ Skeleton videó feltöltése sikertelen: {e}")

        # 4️⃣ PDF riport generálása (Csak ha nem Antropometria Elemzés)
        if job.job_type != DiagnosticJob.JobType.ANTHROPOMETRY_CALIBRATION:
            pdf_path = generate_pdf_report(job, result_data) 
            
            if pdf_path:
                logger.info(f"✅ PDF riport elkészült: {pdf_path}")
            else:
                logger.warning("⚠️ PDF riport generálása/feltöltése sikertelen, folytatás PDF URL nélkül.")
        else:
            logger.info("📄 PDF riport kihagyva: Antropometriai Job.")

        # 5️⃣ Mentés
        final_result_data = _convert_numpy_to_python(result_data)      
        job.mark_as_completed(final_result_data, pdf_path=pdf_path)
        logger.info(f"🏁 [TASK] Elemzés sikeresen befejezve job_id={job.id}")
        
        # 🆕 6️⃣ SIKERES JOB: NEM KELL SEMMIT CSINÁLNI
        # Az elemzés már le van vonva a views.py-ban (dedicate_analysis)
        logger.info(f"✅ [BILLING] Elemzés sikeresen befejezve, levonás már megtörtént.")

    except DiagnosticJob.DoesNotExist:
        logger.error(f"❌ [TASK] DiagnosticJob #{job_id} nem található.")
        # Ha a Job nem található, nincs mit visszatéríteni
        
    except NotImplementedError as e:
        error_msg = str(e)
        if job:
            job.mark_as_failed(error_msg)
            logger.error(f"❌ [TASK] Implementációs hiba job_id={job_id}: {e}")
            
            # 🆕 VISSZATÉRÍTÉS: Sikertelen job esetén
            try:
                # Egyszerűsített hívás:
                refund_analysis(job) # Csak a job objektumot adjuk át
                logger.info(f"↩️ [BILLING] Elemzés visszatérítve job_id={job_id}")
            except Exception as refund_error:
                logger.error(f"❌ [BILLING] Visszatérítési hiba: {refund_error}")

    except Exception as e:
        error_msg = f"Kritikus elemzési hiba: {e}"
        if job:
            job.mark_as_failed(error_msg)
            logger.critical(f"❌ [TASK] Kritikus hiba job_id={job_id}: {e}", exc_info=True)
            
            # 🆕 VISSZATÉRÍTÉS: Sikertelen job esetén
            try:
                # Egyszerűsített hívás:
                refund_analysis(job) # Csak a job objektumot adjuk át
                logger.info(f"↩️ [BILLING] Elemzés visszatérítve job_id={job_id}")
            except Exception as refund_error:
                logger.error(f"❌ [BILLING] Visszatérítési hiba: {refund_error}")