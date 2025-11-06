# diagnostics/utils/video_handler.py
import os
from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import timezone
from datetime import datetime
from django.contrib.auth import get_user_model

# Feltételezünk egy anonim User-t, ha request.user nem elérhető, de a view-ban login_required van
User = get_user_model()


def handle_uploaded_video(uploaded_file, user_id: int):
    """
    Kezeli a feltöltött videót: fájlrendszerre menti a MEDIA_ROOT-on belül, 
    és generálja az adatbázisba menthető URL-t.
    
    :param uploaded_file: Django UploadedFile objektum (request.FILES['video'])
    :param user_id: A feltöltést végző felhasználó ID-ja a fájlnévhez
    :return: (video_url, file_path) tuple
    """
    
    # Fájlnév generálása
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Tiszta, biztonságos fájlnév (csak a kiterjesztést tartjuk meg)
    _, ext = os.path.splitext(uploaded_file.name)
    
    # Elérési út a MEDIA_ROOT-on belül: pl. uploads/video_123_20251020_161538.mp4
    # A user_id-t is beletesszük a nevébe a könnyebb azonosítás érdekében
    safe_filename = f"video_{user_id}_{timestamp}{ext.lower()}"
    file_storage_path = os.path.join('uploads', safe_filename)
    
    # 1. Mentés a default storage-ba
    try:
        # A save() metódus megnyitja és eltárolja a fájlt, és visszaadja a tárolóban lévő útvonalat
        path_in_storage = default_storage.save(file_storage_path, uploaded_file)
        
        # 2. Fizikai elérési út a Django Service-ek számára (csak ha FileSystemStorage van)
        # Ez elengedhetetlen a helyi MediaPipe futtatásához!
        file_path = os.path.join(settings.MEDIA_ROOT, path_in_storage)
        
        # 3. Nyilvános URL az adatbázis számára (pl. /media/uploads/video_...)
        video_url = default_storage.url(path_in_storage)

        print(f"💾 [VideoHandler] Fájl mentve. URL: {video_url}, Path: {file_path}")
        return video_url, file_path

    except Exception as e:
        print(f"❌ [VideoHandler] Hiba a feltöltéskor: {e}")
        raise