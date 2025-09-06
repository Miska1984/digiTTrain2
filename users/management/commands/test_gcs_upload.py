from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Teszt fájl feltöltése a GCS bucketbe"

    def handle(self, *args, **kwargs):
        # Ellenőrizzük, hogy melyik storage backend van betöltve
        logger.info("Aktív storage backend: %s", default_storage.__class__)

        # Fájl tartalma
        content = ContentFile ("Ez egy teszt GCS feltöltés Django-ból.")

        # Útvonal a bucketben
        file_path = "media/test_upload.txt"

        # Feltöltés
        saved_path = default_storage.save(file_path, content)

        # URL lekérése
        file_url = default_storage.url(saved_path)

        self.stdout.write(self.style.SUCCESS(f"✅ Fájl elmentve: {saved_path}"))
        self.stdout.write(self.style.SUCCESS(f"🌍 Elérhető itt: {file_url}"))
