# users/debug_views.py
import logging
import os
import sys
from django.http import JsonResponse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings

logger = logging.getLogger(__name__)

def gcs_upload_debug(request):
    return JsonResponse({
        "message": "POST egy fájlt ide a teszteléshez",
        "DJANGO_SETTINGS_MODULE": sys.modules.get("django.conf").settings.__class__.__name__,
        "storage_backend": settings.DEFAULT_FILE_STORAGE,
        "bucket_name": getattr(settings, "GS_BUCKET_NAME", "N/A"),
    })

@csrf_exempt
def debug_settings(request):
    """Debug view a beállítások ellenőrzésére"""
    
    return JsonResponse({
        'environment_var': os.environ.get('ENVIRONMENT', 'Not set'),
        'django_settings_module': os.environ.get('DJANGO_SETTINGS_MODULE', 'Not set'),
        'debug_setting': getattr(settings, 'DEBUG', 'Not set'),
        'databases': str(getattr(settings, 'DATABASES', 'Not set')),
        'default_file_storage': getattr(settings, 'DEFAULT_FILE_STORAGE', 'Not set'),
        'staticfiles_storage': getattr(settings, 'STATICFILES_STORAGE', 'Not set'),
        'gs_bucket_name': getattr(settings, 'GS_BUCKET_NAME', 'Not set'),
        'gs_project_id': getattr(settings, 'GS_PROJECT_ID', 'Not set'),
        'media_url': getattr(settings, 'MEDIA_URL', 'Not set'),
        'static_url': getattr(settings, 'STATIC_URL', 'Not set'),
        'allowed_hosts': getattr(settings, 'ALLOWED_HOSTS', 'Not set'),
        'storage_backend_class': str(default_storage.__class__),
        'all_env_vars': {k: v for k, v in os.environ.items() if k.startswith(('DJANGO', 'ENVIRONMENT', 'GS_', 'DB_'))}
    })

@csrf_exempt
@require_http_methods(["POST", "GET"])
def debug_gcs_upload(request):
    """Debug view a GCS feltöltés tesztelésére"""
    
    if request.method == "GET":
        return JsonResponse({
            'message': 'POST egy fájlt ide a teszteléshez',
            'storage_backend': str(default_storage.__class__),
            'bucket_name': getattr(default_storage, 'bucket_name', 'N/A')
        })
    
    try:
        logger.info("🚀 Debug GCS feltöltés kezdés")
        
        # Teszt fájl létrehozása
        test_content = b"Test file content - " + str(request.POST.get('test', 'default')).encode()
        test_file = ContentFile(test_content)
        test_filename = f"debug/test_{request.POST.get('filename', 'default')}.txt"
        
        logger.info(f"📁 Teszt fájl: {test_filename}")
        logger.info(f"📦 Storage backend: {default_storage.__class__}")
        
        # Fájl mentése
        logger.info("💾 Fájl mentése...")
        saved_name = default_storage.save(test_filename, test_file)
        logger.info(f"✅ Fájl mentve mint: {saved_name}")
        
        # URL generálása
        file_url = default_storage.url(saved_name)
        logger.info(f"🌍 Fájl URL: {file_url}")
        
        # Fájl létezésének ellenőrzése
        file_exists = default_storage.exists(saved_name)
        logger.info(f"🔍 Fájl létezik: {file_exists}")
        
        # Fájl mérete
        try:
            file_size = default_storage.size(saved_name)
            logger.info(f"📏 Fájl méret: {file_size} bájt")
        except Exception as e:
            logger.error(f"❌ Fájl méret lekérése sikertelen: {str(e)}")
            file_size = "Ismeretlen"
        
        # GCS specifikus információk
        gcs_info = {}
        if hasattr(default_storage, 'bucket'):
            try:
                bucket = default_storage.bucket
                gcs_info = {
                    'bucket_name': bucket.name,
                    'bucket_location': bucket.location,
                    'bucket_storage_class': bucket.storage_class
                }
            except Exception as e:
                gcs_info['error'] = str(e)
        
        return JsonResponse({
            'success': True,
            'saved_name': saved_name,
            'file_url': file_url,
            'file_exists': file_exists,
            'file_size': file_size,
            'storage_backend': str(default_storage.__class__),
            'gcs_info': gcs_info,
            'message': 'Fájl sikeresen feltöltve és tesztelve'
        })
        
    except Exception as e:
        logger.error(f"❌ Hiba a debug feltöltés során: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JsonResponse({
            'success': False,
            'error': str(e),
            'storage_backend': str(default_storage.__class__),
            'message': 'Hiba történt a feltöltés során'
        }, status=500)