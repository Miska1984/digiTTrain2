# diagnostics_jobs/services/base_service.py

from datetime import datetime
import logging 
from django.conf import settings # 🆕 Új import
from django.core.files.storage import default_storage # 🆕 Új import
from django.utils import timezone # 🆕 Új import
import tempfile # 🆕 Új import
import os # 🆕 Új import
from diagnostics_jobs.models import DiagnosticJob 

logger = logging.getLogger(__name__)

class BaseDiagnosticService:
    """Közös alap a diagnosztikai elemzők számára."""

    def __init__(self, job: DiagnosticJob):
        """A szolgáltatás inicializálása a DiagnosticJob objektummal."""
        self.job = job
        logger.info(f"Service inicializálva job_id={self.job.id}")

    @staticmethod
    def log(message):
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

    # ❗ A BaseDiagnosticService-ből kivettük a run_analysis osztályszintű metódust a konstruktor bevezetése miatt.
    def run_analysis(self):
        """Minden diagnosztikai service-nek implementálnia kell."""
        raise NotImplementedError("Implementáld a run_analysis metódust.")