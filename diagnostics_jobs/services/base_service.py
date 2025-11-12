# diagnostics_jobs/services/base_service.py

from datetime import datetime
import logging 
from django.conf import settings # 🆕 Új import
from django.core.files.storage import default_storage # 🆕 Új import
from django.utils import timezone # 🆕 Új import
import tempfile # 🆕 Új import
import os # 🆕 Új import
from diagnostics_jobs.models import DiagnosticJob 
from diagnostics.utils.snapshot_manager import upload_file_to_gcs
from diagnostics import pdf_utils

logger = logging.getLogger(__name__)

class BaseDiagnosticService:
    """Közös alap a diagnosztikai elemzők számára."""

    def __init__(self, job: DiagnosticJob):
        """A szolgáltatás inicializálása a DiagnosticJob objektummal."""
        self.job = job
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"Service inicializálva job_id={job.id}")
        

    def log(self, message, level='info'):
        """
        Központi logolási metódus, ami a self.logger-t használja.
        """
        if level == 'info':
            self.logger.info(message)
        elif level == 'warning':
            self.logger.warning(message)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧩 {message}")

    # =========================================================================
    # 🆕 ÚJ ALAPFÜGGVÉNY: Videó letöltése (A hiányzó metódus!)
    # =========================================================================
    def download_video(self):
        """Letölti a Jobhoz tartozó videót a GCS-ből ideiglenes fájlba."""
        logger.info(f"⬇️ Videó letöltése: {self.job.video_url}")
        
        try:
            # 🟢 JAVÍTVA: A GS_MEDIA_URL helyett a GS_BUCKET_NAME-t használjuk 
            # a GCS elérési út kinyeréséhez, hogy a 'videos/uploads/...' részt megkapjuk.
            
            # A GCS elérési út alapjának rekonstruálása
            gcs_prefix = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/"
            
            # Kicseréljük a teljes GCS prefixet üres stringre, így megmarad a bucket-beli útvonal.
            if not self.job.video_url.startswith(gcs_prefix):
                 raise ValueError(f"A videó URL ({self.job.video_url}) nem egyezik a GCS prefix-szel: {gcs_prefix}")

            video_name = self.job.video_url.replace(gcs_prefix, "")
            
            logger.debug(f"Kinyert GCS elérési út (key): {video_name}") # Segítség a debuggoláshoz
            
            # Ideiglenes fájl létrehozása
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            local_path = tmp_file.name
            
        except Exception as e:
            logger.error(f"❌ Hiba a videó letöltésénél (Job ID: {self.job.id}): {e}", exc_info=True)
            self.fail_job(f"Videó letöltési hiba: {e}")
            return None

    # =========================================================================
    # 🆕 ÚJ ALAPFÜGGVÉNY: Job sikertelen állapotba helyezése
    # =========================================================================
    def fail_job(self, error_message: str):
        """A Job állapotát FAILED-re állítja és menti a hibát."""
        self.job.mark_as_failed(error_message)
        logger.error(f"❌ Job FAILED (ID: {self.job.id}): {error_message}")
        
    # =========================================================================
    # 🆕 ÚJ ALAPFÜGGVÉNY: Job sikeres állapotba helyezése (a service-ek végén)
    # =========================================================================
    def complete_job(self, result: dict, pdf_path: str = None):
        """A Job állapotát COMPLETED-re állítja, menti az eredményeket és a PDF utat."""
        self.job.mark_as_completed(result, pdf_path=pdf_path)
        logger.info(f"✅ Job COMPLETED (ID: {self.job.id}).")
        
        # Tisztítás: Lokális videó törlése, ha még létezik.
        if hasattr(self, '_local_video_path') and os.path.exists(self._local_video_path):
             os.remove(self._local_video_path)
             logger.debug(f"🗑 Tisztítás: Törölve a lokális videó: {self._local_video_path}")
    
    # =========================================================================
    # 🆕 ÚJ ALAPFÜGGVÉNY: PDF Riport Generálása
    # =========================================================================
    def generate_report(self, result_data: dict) -> str:
        self.log("▶️ Jelentés generálás elindítva...", 'info')

        # ❗ A PDF generáló logika hívása 
        try:
            # 🟢 ÚJ KÓD: A PDF generálása és a VALÓS lokális útvonal kinyerése
            # A template_path-ot feltételezzük, hogy a származtatott service tudja, vagy itt hívja meg a generálást:
            
            # Példa: Ezt hívja meg, ami a PDF-et legenerálja!
            local_pdf_path = self._create_pdf_from_html_template(
                template_name="single_leg_stance_details.html",
                context=result_data,
                job_id=self.job.id 
            )
            self.log(f"📄 PDF generálva a lokális útvonalra: {local_pdf_path}", 'info')
            
        except AttributeError:
            # Ez a hiba akkor jön, ha a _create_pdf_from_html_template nincs implementálva a Base-ben vagy a SingleLegStanceService-ben
            self.log("❌ HIBA: A PDF generáló (pl. _create_pdf_from_html_template) metódus hiányzik vagy hibás!", 'error')
            return None
            
        except Exception as e:
            self.log(f"❌ PDF GENERÁLÁSI HIBA: {e}", 'error')
            return None


        # ---------------------------------------------------------------------
        # 🟢 KRITIKUS LÉPÉS: Feltöltés a GCS-re
        # ---------------------------------------------------------------------
        
        # 1. Ellenőrzés: Megtalálható-e a FÁJL a lemezén?
        if not local_pdf_path or not os.path.exists(local_pdf_path):
            self.log(f"❌ Fájl nem található a feltöltéshez: {local_pdf_path}", 'error')
            return None # SIKERTELEN VISSZATÉRÉS!

        # 2. GCS célútvonal meghatározása
        # TIPP: Használja a job_type-ot a job.id mellett a jobb azonosítás érdekében.
        report_filename = f"report_job_{self.job.id}_{self.job.job_type.lower()}.pdf" 
        gcs_destination = f"diagnostics/reports/{report_filename}"
        
        # 3. Feltöltés a GCS-re
        pdf_url = upload_file_to_gcs(
            local_file_path=local_pdf_path,
            gcs_destination=gcs_destination
        )
        
        # 4. Tisztítás (a GCS feltöltés után)
        if os.path.exists(local_pdf_path):
            os.remove(local_pdf_path) 
            self.log(f"🗑 Lokális PDF törölve: {local_pdf_path}", 'debug')

        # 5. Visszatérés
        if not pdf_url:
            self.log("❌ Jelentés feltöltése GCS-re SIKERTELEN. Üres URL-lel tér vissza.", 'error')
            
        return pdf_utils.generate_pdf_report(self.job, result_data)

    # ❗ A BaseDiagnosticService-ből kivettük a run_analysis osztályszintű metódust a konstruktor bevezetése miatt.
    def run_analysis(self):
        """Minden diagnosztikai service-nek implementálnia kell."""
        raise NotImplementedError("A run_analysis() metódust implementálni kell a leszármazott osztályokban.")