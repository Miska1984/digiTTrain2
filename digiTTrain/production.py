# digiTTrain/production.py
import os
import sys
import logging
from .base import *

print(">>> [DEBUG] Production settings loaded <<<", file=sys.stderr)

# ===== ALAPBEÁLLÍTÁSOK =====
DEBUG = False

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')
ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS if h.strip()]
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['digit-train-web-195803356854.europe-west1.run.app']

CSRF_TRUSTED_ORIGINS = [
    'https://digit-train-web-195803356854.europe-west1.run.app',
    'https://digit-train.hu',
    'https://www.digit-train.hu',
]

# ===== ADATBÁZIS =====
CLOUDSQL_CONNECTION_NAME = os.getenv("CLOUDSQL_CONNECTION_NAME")
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASS'),
        'HOST': f"/cloudsql/{CLOUDSQL_CONNECTION_NAME}",
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# ===== GOOGLE CLOUD STORAGE BEÁLLÍTÁSOK =====
GS_BUCKET_NAME = os.environ.get("GS_BUCKET_NAME", "digittrain-media-publikus-miska1984")
GS_PROJECT_ID = os.environ.get("GS_PROJECT_ID", "digittrain-projekt")
GS_LOCATION = os.environ.get("GS_LOCATION", "europe-west1")

USE_GCS_STATIC = os.getenv("USE_GCS_STATIC", "false").lower() == "true"
BUILD_MODE = os.getenv("BUILD_MODE", "false").lower() == "true"

GS_AUTO_CREATE_BUCKET = False
# ✅ KRITIKUS JAVÍTÁS: UBLA kompatibilitás
GS_DEFAULT_ACL = None  # ❌ NE használj "publicRead"-et UBLA-val!
GS_QUERYSTRING_AUTH = False
GS_FILE_OVERWRITE = False
GS_MAX_MEMORY_SIZE = 1024 * 1024 * 5  # 5MB

# ===== STATIKUS / MÉDIA BEÁLLÍTÁSOK =====
if USE_GCS_STATIC:
    # ---- Google Cloud Storage használata ----
    STATIC_URL = f"https://storage.googleapis.com/{GS_BUCKET_NAME}/static/"
    MEDIA_URL = f"https://storage.googleapis.com/{GS_BUCKET_NAME}/"
    STATIC_ROOT = "/app/staticfiles_temp"
    MEDIA_ROOT = "/app/mediafiles_temp"

    from storages.backends import gcloud

    class MediaStorage(gcloud.GoogleCloudStorage):
        bucket_name = GS_BUCKET_NAME
        default_acl = None  # ✅ UBLA kompatibilitás
        querystring_auth = False
        location = ''

        def _save(self, name, content):
            try:
                print(f"Próbálkozás fájl mentésével: {name}")
                print(f"Bucket: {self.bucket_name}")
                result = super()._save(name, content)
                print(f"Sikeres mentés: {result}")
                return result
            except Exception as e:
                print(f"Storage mentési hiba: {str(e)}")
                raise

    class StaticStorage(gcloud.GoogleCloudStorage):
        bucket_name = GS_BUCKET_NAME
        default_acl = None  # ✅ UBLA kompatibilitás
        querystring_auth = False
        location = 'static'

    STORAGES = {
        "default": {"BACKEND": "digiTTrain.production.MediaStorage"},
        "staticfiles": {"BACKEND": "digiTTrain.production.StaticStorage"},
    }

    print(">>> [DEBUG] Using GCS for static and media <<<", file=sys.stderr)

else:
    # ---- Whitenoise + helyi statikus kiszolgálás ----
    STATIC_URL = "/static/"
    MEDIA_URL = "/media/"
    STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
    MEDIA_ROOT = os.path.join(BASE_DIR, "mediafiles")

    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

    print(">>> [DEBUG] Using local static files (Whitenoise) <<<", file=sys.stderr)


# ===== BUILD MODE: csak build idején helyi static használat =====
if BUILD_MODE:
    print(">>> [DEBUG] BUILD MODE aktív – helyi static használat <<<", file=sys.stderr)
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    STATIC_URL = "/static/"
    MEDIA_URL = "/media/"

# ===============================
# 🧩 Kényszerített GCS használat médiára (PDF, képek, videók)
# ===============================
if not BUILD_MODE:
    from storages.backends import gcloud

    class MediaStorage(gcloud.GoogleCloudStorage):
        bucket_name = GS_BUCKET_NAME
        default_acl = None  # ✅ KRITIKUS: UBLA kompatibilitás
        querystring_auth = False
        location = ""

    STORAGES["default"] = {"BACKEND": "digiTTrain.production.MediaStorage"}
    MEDIA_URL = f"https://storage.googleapis.com/{GS_BUCKET_NAME}/"
    MEDIA_ROOT = "/app/mediafiles_temp"

    print(">>> [FORCE] Using GCS for MEDIA files <<<", file=sys.stderr)

# ===== CELERY BEÁLLÍTÁSOK =====
REDIS_HOST = os.getenv('REDIS_HOST', '10.32.84.131')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')

CELERY_BROKER_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/0'
CELERY_RESULT_BACKEND = f'redis://{REDIS_HOST}:{REDIS_PORT}/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 perc

print(f">>> [DEBUG] CELERY_BROKER_URL: {CELERY_BROKER_URL}", file=sys.stderr)
print(f">>> [DEBUG] USE_GCS_STATIC={USE_GCS_STATIC}, BUILD_MODE={BUILD_MODE}", file=sys.stderr)
print(f">>> [DEBUG] Active static backend: {STORAGES['staticfiles']['BACKEND']}", file=sys.stderr)